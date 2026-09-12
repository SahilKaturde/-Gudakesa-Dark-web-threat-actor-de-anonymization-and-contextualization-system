"""
Persistent memory for GUDAKESA chat.

SQLite-backed message store with:
  - Per-session conversation history
  - Cross-session semantic recall (Gemini text-embedding-004)
  - Hard 200 MB cap with automatic oldest-first pruning

Env:
    GOOGLE_API_KEY      — for embeddings (optional; store works without)
    GUDAKESA_MEM_MB     — override size cap (default 200)
    GUDAKESA_EMBED      — "0" disables embedding entirely
"""
import os
import array
import sqlite3
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(_DB_DIR, "gudakesa_memory.db")

MAX_DB_BYTES = int(os.getenv("GUDAKESA_MEM_MB", "200")) * 1024 * 1024
EMBED_ENABLED = os.getenv("GUDAKESA_EMBED", "1") != "0"

EMBED_MODEL = "models/text-embedding-004"
EMBED_DIM = 768

_write_lock = threading.Lock()
_write_count = 0
_embedder = None
_embedder_tried = False


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------
def _get_embedder():
    """Lazy-load GoogleGenerativeAIEmbeddings. Returns None if unavailable."""
    global _embedder, _embedder_tried
    if _embedder_tried:
        return _embedder
    _embedder_tried = True

    if not EMBED_ENABLED:
        return None

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        _embedder = GoogleGenerativeAIEmbeddings(
            model=EMBED_MODEL,
            google_api_key=api_key,
        )
        return _embedder
    except Exception as e:
        print(f"[Memory] Embedder init failed: {str(e)[:160]}")
        return None


def _embed(text: str) -> Optional[List[float]]:
    """Embed a single string. Returns None on any failure."""
    emb = _get_embedder()
    if not emb:
        return None
    try:
        vec = emb.embed_query(text[:8000])
        return list(vec) if vec else None
    except Exception as e:
        print(f"[Memory] Embed failed: {str(e)[:160]}")
        return None


def _vec_to_blob(vec: List[float]) -> bytes:
    return array.array("f", vec).tobytes()


def _blob_to_vec(blob: bytes) -> List[float]:
    a = array.array("f")
    a.frombytes(blob)
    return list(a)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def _conn() -> sqlite3.Connection:
    os.makedirs(_DB_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def init_memory_db() -> None:
    """Create tables if missing. Safe to call multiple times."""
    with _write_lock:
        c = _conn()
        try:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    embedding   BLOB,
                    created_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_messages_created
                    ON messages(created_at);

                CREATE TABLE IF NOT EXISTS facts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_facts_session
                    ON facts(session_id, key);
                """
            )
            c.commit()
        finally:
            c.close()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _maybe_prune() -> None:
    global _write_count
    _write_count += 1
    if _write_count % 50 == 0:
        enforce_size_limit()


def enforce_size_limit() -> None:
    """
    If the DB exceeds MAX_DB_BYTES, delete oldest messages in batches
    until it's under 90% of the cap.
    """
    try:
        size = os.path.getsize(DB_PATH)
    except OSError:
        return
    if size <= MAX_DB_BYTES:
        return

    target = int(MAX_DB_BYTES * 0.9)
    print(f"[Memory] DB at {size // (1024*1024)} MB > "
          f"{MAX_DB_BYTES // (1024*1024)} MB — pruning to {target // (1024*1024)} MB")

    c = _conn()
    try:
        for _ in range(500):  # hard stop after 500 batches
            if size <= target:
                break
            c.execute(
                "DELETE FROM messages WHERE id IN "
                "(SELECT id FROM messages ORDER BY id ASC LIMIT 500)"
            )
            c.execute(
                "DELETE FROM facts WHERE id IN "
                "(SELECT id FROM facts ORDER BY id ASC LIMIT 500)"
            )
            c.commit()
            try:
                size = os.path.getsize(DB_PATH)
            except OSError:
                return
        try:
            c.execute("VACUUM")
        except Exception:
            pass
    finally:
        c.close()


def store_message(
    session_id: str,
    role: str,
    content: str,
    embed: bool = True,
) -> None:
    """Persist one message. Silently no-ops on any failure."""
    if not session_id or not content:
        return

    blob = None
    if embed:
        vec = _embed(content)
        if vec:
            blob = _vec_to_blob(vec)

    with _write_lock:
        try:
            c = _conn()
            try:
                c.execute(
                    "INSERT INTO messages(session_id, role, content, embedding, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (session_id, role, content, blob, _now()),
                )
                c.commit()
            finally:
                c.close()
            _maybe_prune()
        except Exception as e:
            print(f"[Memory] Store failed: {str(e)[:160]}")


def store_fact(session_id: str, key: str, value: str) -> None:
    """Save a structured fact (IOC, alias, etc.) for a session."""
    if not session_id or not key or not value:
        return
    with _write_lock:
        try:
            c = _conn()
            try:
                c.execute(
                    "INSERT INTO facts(session_id, key, value, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (session_id, key, value, _now()),
                )
                c.commit()
            finally:
                c.close()
        except Exception as e:
            print(f"[Memory] store_fact failed: {str(e)[:160]}")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def get_session_history(
    session_id: str,
    limit: int = 40,
) -> List[Dict]:
    """Return recent messages for a session, oldest first."""
    if not session_id:
        return []
    try:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        finally:
            c.close()
        return [
            {"sender": r["role"], "text": r["content"], "ts": r["created_at"]}
            for r in reversed(rows)
        ]
    except Exception as e:
        print(f"[Memory] History read failed: {str(e)[:160]}")
        return []


def search_similar(
    query: str,
    exclude_session: Optional[str] = None,
    top_k: int = 5,
    scan_limit: int = 5000,
    min_score: float = 0.55,
) -> List[Dict]:
    """
    Return top_k past messages most semantically similar to `query`,
    excluding a given session if provided. Uses cosine similarity.
    """
    if not query or not EMBED_ENABLED:
        return []

    q_vec = _embed(query)
    if not q_vec:
        return []

    try:
        c = _conn()
        try:
            if exclude_session:
                rows = c.execute(
                    "SELECT session_id, role, content, embedding, created_at "
                    "FROM messages WHERE embedding IS NOT NULL "
                    "AND session_id != ? "
                    "ORDER BY id DESC LIMIT ?",
                    (exclude_session, scan_limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT session_id, role, content, embedding, created_at "
                    "FROM messages WHERE embedding IS NOT NULL "
                    "ORDER BY id DESC LIMIT ?",
                    (scan_limit,),
                ).fetchall()
        finally:
            c.close()
    except Exception as e:
        print(f"[Memory] Similar search failed: {str(e)[:160]}")
        return []

    scored: List[Tuple[float, Dict]] = []
    for r in rows:
        try:
            v = _blob_to_vec(r["embedding"])
        except Exception:
            continue
        score = _cosine(q_vec, v)
        if score >= min_score:
            scored.append((score, {
                "sender": r["role"],
                "text": r["content"],
                "session_id": r["session_id"],
                "ts": r["created_at"],
                "score": round(score, 3),
            }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def get_memory_stats() -> Dict:
    """Return size + row counts. Handy for /api/v1/memory/status."""
    try:
        size_bytes = os.path.getsize(DB_PATH)
    except OSError:
        size_bytes = 0
    stats = {
        "db_path": DB_PATH,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "max_mb": MAX_DB_BYTES // (1024 * 1024),
        "usage_pct": round(100.0 * size_bytes / MAX_DB_BYTES, 2) if MAX_DB_BYTES else 0.0,
        "messages": 0,
        "sessions": 0,
        "facts": 0,
        "embed_enabled": EMBED_ENABLED and _get_embedder() is not None,
    }
    try:
        c = _conn()
        try:
            stats["messages"] = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            stats["sessions"] = c.execute(
                "SELECT COUNT(DISTINCT session_id) FROM messages"
            ).fetchone()[0]
            stats["facts"] = c.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        finally:
            c.close()
    except Exception:
        pass
    return stats