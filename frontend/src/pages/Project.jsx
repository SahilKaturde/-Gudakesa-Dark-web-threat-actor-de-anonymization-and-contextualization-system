import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getProjects } from "../api/projects";
import {
    triggerCrawl,
    getCrawlStatus,
    stopCrawl,
} from "../api/crawls";
import api from "../api/axiosInstance";
import { useAuth } from "../context/AuthContext";

/* ─────────────────────────────────────────────
   Helper: format bytes to human-readable
   ───────────────────────────────────────────── */
function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/* ═══════════════════════════════════════════════
   SCRAPED PAGES MODAL
   ═══════════════════════════════════════════════ */
const ScrapedPagesModal = ({ domainId, domainName, onClose }) => {
    const [pages, setPages] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [expandedId, setExpandedId] = useState(null);

    const navigate = useNavigate();

    useEffect(() => {
        if (!domainId) return;
        setLoading(true);
        api.get(`/domains/${domainId}/pages/`)
            .then((res) => setPages(res.data))
            .catch((err) => console.error("Failed to load pages:", err))
            .finally(() => setLoading(false));
    }, [domainId]);

    const filtered = pages.filter(
        (p) =>
            p.page_name.toLowerCase().includes(search.toLowerCase()) ||
            p.page_url.toLowerCase().includes(search.toLowerCase())
    );

    const totalTextSize = pages.reduce(
        (sum, p) => sum + (p.content_length || 0),
        0
    );

    const handleOpenPlayground = () => {
        navigate(`/playground/${domainId}`, {
            state: {
                domainId,
                domainName,
                pages,
            },
        });
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="relative mx-4 flex max-h-[85vh] w-full max-w-3xl flex-col border-2 border-black bg-white shadow-[6px_6px_0_0_#000]">
                {/* Header */}
                <div className="flex items-center justify-between border-b-2 border-black px-6 py-4">
                    <div className="min-w-0">
                        <h3 className="text-lg font-bold">
                            📄 Scraped TXT Data
                        </h3>
                        <p className="mt-1 truncate font-mono text-[10px] text-neutral-500">
                            {domainName}
                        </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                        <button
                            onClick={handleOpenPlayground}
                            className="border-2 border-black bg-black px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-[2px_2px_0_0_#000] transition-all hover:bg-neutral-800 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none cursor-pointer"
                        >
                            ⚡ Playground
                        </button>

                        <button
                            onClick={onClose}
                            className="flex h-8 w-8 items-center justify-center border-2 border-black text-sm font-bold hover:bg-black hover:text-white cursor-pointer"
                        >
                            ✕
                        </button>
                    </div>
                </div>

                {/* Stats bar */}
                <div className="flex gap-6 border-b border-neutral-200 px-6 py-3 text-xs">
                    <span>
                        <strong>{pages.length}</strong> pages saved
                    </span>
                    <span>
                        <strong>{formatBytes(totalTextSize)}</strong> total text
                    </span>
                </div>

                {/* Search */}
                <div className="px-6 py-3">
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search pages..."
                        className="w-full border-2 border-black px-3 py-2 text-sm focus:outline-none"
                    />
                </div>

                {/* Pages list */}
                <div className="flex-1 overflow-y-auto px-6 pb-6">
                    {loading ? (
                        <div className="py-12 text-center text-sm text-neutral-400">
                            Loading pages...
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="py-12 text-center text-sm text-neutral-400">
                            {pages.length === 0
                                ? "No scraped pages yet."
                                : "No results match your search."}
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {filtered.map((page) => (
                                <div
                                    key={page.page_id}
                                    className="border-2 border-black"
                                >
                                    <button
                                        onClick={() =>
                                            setExpandedId(
                                                expandedId === page.page_id
                                                    ? null
                                                    : page.page_id
                                            )
                                        }
                                        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-neutral-50 cursor-pointer"
                                    >
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate text-sm font-bold">
                                                {page.page_name}
                                            </p>
                                            <p className="mt-0.5 truncate font-mono text-[10px] text-neutral-400">
                                                {page.page_url}
                                            </p>
                                        </div>
                                        <span className="ml-3 shrink-0 text-xs text-neutral-400">
                                            {expandedId === page.page_id
                                                ? "▲"
                                                : "▼"}
                                        </span>
                                    </button>

                                    {expandedId === page.page_id && (
                                        <div className="border-t-2 border-black bg-black px-4 py-4">
                                            <div className="mb-3 flex items-center justify-between">
                                                <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                                                    Extracted Text —{" "}
                                                    {formatBytes(
                                                        page.content_length || 0
                                                    )}
                                                </span>
                                                <button
                                                    onClick={() => {
                                                        navigator.clipboard.writeText(
                                                            page.page_text
                                                        );
                                                    }}
                                                    className="border border-white px-2 py-0.5 text-[10px] font-bold text-white hover:bg-white hover:text-black cursor-pointer"
                                                >
                                                    Copy TXT
                                                </button>
                                            </div>
                                            <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-white">
                                                {page.page_text}
                                            </pre>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

/* ═══════════════════════════════════════════════
   MAIN PROJECT PAGE
   ═══════════════════════════════════════════════ */
const Project = () => {
    const { projectId } = useParams();
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const [project, setProject] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // Domain list
    const [domains, setDomains] = useState([]);

    // Add domain form
    const [newOnionUrl, setNewOnionUrl] = useState("");
    const [addingDomain, setAddingDomain] = useState(false);

    // Crawl state per domain: { [domainId]: { crawlId, status, elapsed, error } }
    const [crawlStates, setCrawlStates] = useState({});
    const pollRefs = useRef({});

    // Scraped pages modal
    const [inspectDomain, setInspectDomain] = useState(null);

    /* ── Load project ── */
    useEffect(() => {
        const loadProject = async () => {
            try {
                setLoading(true);
                setError("");
                const projects = await getProjects();
                const found = projects.find(
                    (p) => p.project_id === projectId
                );
                if (!found) {
                    setError("Project not found.");
                    return;
                }
                setProject(found);
            } catch (err) {
                console.error(err);
                setError("Unable to load this project.");
            } finally {
                setLoading(false);
            }
        };
        loadProject();
    }, [projectId]);

    /* ── Load domains ── */
    const loadDomains = useCallback(async () => {
        try {
            const res = await api.get(
                `/projects/${projectId}/domains/`
            );
            setDomains(res.data);
        } catch (err) {
            console.error("Failed to load domains:", err);
        }
    }, [projectId]);

    useEffect(() => {
        if (project) loadDomains();
    }, [project, loadDomains]);

    /* ── Cleanup polling on unmount ── */
    useEffect(() => {
        return () => {
            Object.values(pollRefs.current).forEach(clearInterval);
        };
    }, []);

    /* ── Add onion domain ── */
    const handleAddDomain = async (e) => {
        e.preventDefault();
        if (!newOnionUrl.trim()) return;

        setAddingDomain(true);
        try {
            await api.post(`/projects/${projectId}/domains/`, {
                domain_name: newOnionUrl.trim(),
            });
            setNewOnionUrl("");
            await loadDomains();
        } catch (err) {
            console.error("Failed to add domain:", err);
            alert(
                err.response?.data?.domain_name?.[0] ||
                    "Failed to add domain."
            );
        } finally {
            setAddingDomain(false);
        }
    };

    /* ── Start crawl ── */
    const handleCrawl = async (domain) => {
        const domainId = domain.domain_id;
        try {
            setCrawlStates((prev) => ({
                ...prev,
                [domainId]: {
                    status: "starting",
                    elapsed: 0,
                    error: null,
                },
            }));

            const jwt =
                localStorage.getItem("access_token") || "";

            const data = await triggerCrawl(
                domain.domain_name,
                domainId,
                jwt,
                1,
                50
            );

            const crawlId = data.crawl_id;

            setCrawlStates((prev) => ({
                ...prev,
                [domainId]: {
                    crawlId,
                    status: "running",
                    elapsed: 0,
                    error: null,
                },
            }));

            // Poll every 2 seconds
            const startTime = Date.now();
            pollRefs.current[domainId] = setInterval(async () => {
                try {
                    const s = await getCrawlStatus(crawlId);
                    const elapsed = Math.round(
                        (Date.now() - startTime) / 1000
                    );

                    if (
                        s.status === "completed" ||
                        s.status === "failed" ||
                        s.status === "cancelled"
                    ) {
                        clearInterval(pollRefs.current[domainId]);
                        delete pollRefs.current[domainId];

                        setCrawlStates((prev) => ({
                            ...prev,
                            [domainId]: {
                                ...prev[domainId],
                                status: s.status,
                                elapsed,
                                pagesScraped:
                                    s.pages_scraped || 0,
                            },
                        }));

                        // Refresh domains to get updated pages_count
                        await loadDomains();
                    } else {
                        setCrawlStates((prev) => ({
                            ...prev,
                            [domainId]: {
                                ...prev[domainId],
                                status: "running",
                                elapsed,
                                pagesScraped:
                                    s.pages_scraped || 0,
                            },
                        }));
                    }
                } catch {
                    // Polling error — keep going
                }
            }, 2000);
        } catch (err) {
            console.error("Crawl failed:", err);
            setCrawlStates((prev) => ({
                ...prev,
                [domainId]: {
                    status: "failed",
                    error: err.message,
                    elapsed: 0,
                },
            }));
        }
    };

    /* ── Stop crawl ── */
    const handleStopCrawl = async (domainId) => {
        const state = crawlStates[domainId];
        if (!state?.crawlId) return;

        try {
            await stopCrawl(state.crawlId);
            clearInterval(pollRefs.current[domainId]);
            delete pollRefs.current[domainId];

            setCrawlStates((prev) => ({
                ...prev,
                [domainId]: {
                    ...prev[domainId],
                    status: "cancelled",
                },
            }));
            await loadDomains();
        } catch (err) {
            console.error("Failed to stop crawl:", err);
        }
    };

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    /* ── Render: Loading ── */
    if (loading) {
        return (
            <div className="min-h-screen bg-white text-black">
                <header className="border-b-2 border-black bg-white">
                    <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
                        <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center bg-black text-xs font-black text-white">
                                G
                            </div>
                            <span className="text-sm font-bold tracking-tight">
                                GUDAKESA
                            </span>
                        </div>
                    </div>
                </header>
                <main className="mx-auto max-w-5xl px-6 py-16">
                    <div className="animate-pulse">
                        <div className="h-3 w-24 bg-neutral-200" />
                        <div className="mt-5 h-12 w-80 bg-neutral-200" />
                        <div className="mt-4 h-4 w-64 bg-neutral-100" />
                        <div className="mt-12 grid gap-5 sm:grid-cols-3">
                            {[1, 2, 3].map((item) => (
                                <div
                                    key={item}
                                    className="h-32 border-2 border-neutral-200 bg-neutral-50"
                                />
                            ))}
                        </div>
                    </div>
                </main>
            </div>
        );
    }

    /* ── Render: Error ── */
    if (error || !project) {
        return (
            <div className="min-h-screen bg-white text-black">
                <header className="border-b-2 border-black bg-white">
                    <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
                        <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center bg-black text-xs font-black text-white">
                                G
                            </div>
                            <span className="text-sm font-bold tracking-tight">
                                GUDAKESA
                            </span>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="border-2 border-black bg-white px-3.5 py-1.5 text-xs font-bold shadow-[2px_2px_0_0_#000] transition-all hover:bg-black hover:text-white hover:shadow-none cursor-pointer"
                        >
                            Logout
                        </button>
                    </div>
                </header>
                <main className="mx-auto max-w-5xl px-6 py-16">
                    <button
                        onClick={() => navigate("/")}
                        className="mb-10 text-xs font-bold uppercase tracking-wider text-neutral-500 hover:text-black cursor-pointer"
                    >
                        ← Back to Projects
                    </button>
                    <div className="border-2 border-black p-10 text-center">
                        <h1 className="text-xl font-bold">
                            {error || "Project not found."}
                        </h1>
                        <button
                            onClick={() => navigate("/")}
                            className="mt-6 border-2 border-black bg-black px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-white shadow-[3px_3px_0_0_#000] hover:bg-neutral-800 cursor-pointer"
                        >
                            Back to Projects
                        </button>
                    </div>
                </main>
            </div>
        );
    }

    /* ── Dates ── */
    const createdDate = new Date(project.created_at).toLocaleDateString(
        undefined,
        { year: "numeric", month: "long", day: "numeric" }
    );
    const createdTime = new Date(project.created_at).toLocaleTimeString(
        undefined,
        { hour: "2-digit", minute: "2-digit" }
    );

    /* ── Render: Main ── */
    return (
        <div className="min-h-screen bg-white text-black">
            {/* Scraped Pages Modal */}
            {inspectDomain && (
                <ScrapedPagesModal
                    domainId={inspectDomain.domain_id}
                    domainName={inspectDomain.domain_name}
                    onClose={() => setInspectDomain(null)}
                />
            )}

            {/* HEADER */}
            <header className="border-b-2 border-black bg-white">
                <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
                    <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center bg-black text-xs font-black text-white">
                            G
                        </div>
                        <span className="text-sm font-bold tracking-tight">
                            GUDAKESA
                        </span>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="hidden text-xs text-neutral-500 sm:block">
                            {user?.username}
                        </span>
                        <button
                            onClick={handleLogout}
                            className="border-2 border-black bg-white px-3.5 py-1.5 text-xs font-bold shadow-[2px_2px_0_0_#000] transition-all hover:bg-black hover:text-white hover:shadow-none cursor-pointer"
                        >
                            Logout
                        </button>
                    </div>
                </div>
            </header>

            {/* MAIN */}
            <main className="mx-auto max-w-5xl px-6 py-12">
                {/* BACK */}
                <button
                    onClick={() => navigate("/")}
                    className="mb-10 text-xs font-bold uppercase tracking-wider text-neutral-500 transition-colors hover:text-black cursor-pointer"
                >
                    ← Back to Projects
                </button>

                {/* PROJECT HEADER */}
                <section>
                    <div className="mb-5 flex items-center gap-2">
                        <span className="h-2 w-2 bg-black" />
                        <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-neutral-500">
                            Project
                        </span>
                    </div>
                    <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
                        <div>
                            <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
                                {project.project_title}
                            </h1>
                            <p className="mt-4 font-mono text-[10px] uppercase tracking-wider text-neutral-400 break-all">
                                {project.project_id}
                            </p>
                        </div>
                        <div className="shrink-0">
                            <span className="border-2 border-black px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider">
                                Active
                            </span>
                        </div>
                    </div>
                </section>

                {/* DIVIDER */}
                <div className="my-10 border-t-2 border-black" />

                {/* PROJECT INFORMATION */}
                <section>
                    <div className="mb-6">
                        <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-neutral-400">
                            Project Information
                        </p>
                    </div>
                    <div className="grid gap-5 sm:grid-cols-3">
                        <div className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_0_#000]">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                                Project ID
                            </p>
                            <p className="mt-4 break-all font-mono text-xs font-medium leading-relaxed">
                                {project.project_id}
                            </p>
                        </div>
                        <div className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_0_#000]">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                                Created
                            </p>
                            <p className="mt-4 text-sm font-bold">
                                {createdDate}
                            </p>
                            <p className="mt-1 font-mono text-[10px] text-neutral-400">
                                {createdTime}
                            </p>
                        </div>
                        <div className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_0_#000]">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                                Owner
                            </p>
                            <p className="mt-4 text-sm font-bold">
                                {user?.username}
                            </p>
                            <p className="mt-1 text-[10px] text-neutral-400">
                                Authenticated user
                            </p>
                        </div>
                    </div>
                </section>

                {/* ═══════════════════════════════════════
                   ONION TARGETS + CRAWLER
                   ═══════════════════════════════════════ */}
                <section className="mt-12">
                    <div className="mb-6 flex items-end justify-between">
                        <div>
                            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-neutral-400">
                                Dark Web Intelligence
                            </p>
                            <h2 className="mt-2 text-xl font-bold">
                                Onion Targets
                            </h2>
                        </div>
                    </div>

                    {/* Add Onion Link Form */}
                    <form
                        onSubmit={handleAddDomain}
                        className="mb-8 flex gap-3"
                    >
                        <input
                            type="text"
                            value={newOnionUrl}
                            onChange={(e) =>
                                setNewOnionUrl(e.target.value)
                            }
                            placeholder="http://example.onion"
                            className="flex-1 border-2 border-black px-4 py-2.5 text-sm font-mono focus:outline-none"
                        />
                        <button
                            type="submit"
                            disabled={addingDomain}
                            className="border-2 border-black bg-black px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-white shadow-[3px_3px_0_0_#000] transition-all hover:bg-neutral-800 hover:shadow-none disabled:opacity-50 cursor-pointer"
                        >
                            {addingDomain
                                ? "Adding..."
                                : "+ Add Onion Target"}
                        </button>
                    </form>

                    {/* Domain Cards */}
                    {domains.length === 0 ? (
                        <div className="border-2 border-dashed border-neutral-300 px-6 py-20 text-center">
                            <div className="mx-auto flex h-10 w-10 items-center justify-center border-2 border-black bg-white text-sm font-bold shadow-[2px_2px_0_0_#000]">
                                🧅
                            </div>
                            <h3 className="mt-5 text-base font-bold">
                                No onion targets yet
                            </h3>
                            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-neutral-500">
                                Add a .onion URL above to start crawling dark
                                web pages. Scraped text data will be stored
                                directly in your database.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {domains.map((domain) => {
                                const cs =
                                    crawlStates[domain.domain_id] || {};
                                const isRunning =
                                    cs.status === "running" ||
                                    cs.status === "starting";

                                return (
                                    <div
                                        key={domain.domain_id}
                                        className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_0_#000]"
                                    >
                                        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                                            {/* Domain info */}
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-3">
                                                    <span className="shrink-0 border border-black px-1.5 py-0.5 text-[10px] font-bold">
                                                        #{domain.domain_index}
                                                    </span>
                                                    <p className="truncate font-mono text-sm font-bold">
                                                        {domain.domain_name}
                                                    </p>
                                                </div>

                                                <div className="mt-2 flex flex-wrap items-center gap-4 text-[10px] text-neutral-400">
                                                    <span>
                                                        ID:{" "}
                                                        {domain.domain_id.slice(
                                                            0,
                                                            8
                                                        )}
                                                        ...
                                                    </span>
                                                    <span>
                                                        {domain.pages_count || 0}{" "}
                                                        pages saved
                                                    </span>

                                                    {/* Live status badge */}
                                                    {isRunning && (
                                                        <span className="inline-flex items-center gap-1 text-orange-600">
                                                            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-orange-500" />
                                                            Crawling ·{" "}
                                                            {cs.elapsed || 0}s
                                                            {cs.pagesScraped
                                                                ? ` · ${cs.pagesScraped} pages`
                                                                : ""}
                                                        </span>
                                                    )}
                                                    {cs.status ===
                                                        "completed" && (
                                                        <span className="text-green-600">
                                                            ✓ Completed
                                                            {cs.pagesScraped
                                                                ? ` · ${cs.pagesScraped} pages`
                                                                : ""}
                                                        </span>
                                                    )}
                                                    {cs.status ===
                                                        "failed" && (
                                                        <span className="text-red-600">
                                                            ✗ Failed
                                                            {cs.error
                                                                ? ` — ${cs.error}`
                                                                : ""}
                                                        </span>
                                                    )}
                                                    {cs.status ===
                                                        "cancelled" && (
                                                        <span className="text-neutral-500">
                                                            ■ Stopped
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Action buttons */}
                                            <div className="flex shrink-0 gap-2">
                                                {isRunning ? (
                                                    <button
                                                        onClick={() =>
                                                            handleStopCrawl(
                                                                domain.domain_id
                                                            )
                                                        }
                                                        className="border-2 border-red-600 px-3 py-1.5 text-[10px] font-bold uppercase text-red-600 hover:bg-red-600 hover:text-white cursor-pointer"
                                                    >
                                                        ■ Stop
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() =>
                                                            handleCrawl(domain)
                                                        }
                                                        className="border-2 border-black bg-black px-3 py-1.5 text-[10px] font-bold uppercase text-white hover:bg-neutral-800 cursor-pointer"
                                                    >
                                                        {cs.status
                                                            ? "↻ Re-crawl"
                                                            : "▶ Crawl"}
                                                    </button>
                                                )}

                                                <button
                                                    onClick={() =>
                                                        setInspectDomain(domain)
                                                    }
                                                    className="border-2 border-black px-3 py-1.5 text-[10px] font-bold uppercase hover:bg-black hover:text-white cursor-pointer"
                                                >
                                                    📄 Inspect TXT
                                                </button>

                                                <button
                                                    onClick={() =>
                                                        navigate(`/playground/${domain.domain_id}`, {
                                                            state: {
                                                                domainId: domain.domain_id,
                                                                domainName: domain.domain_name,
                                                            },
                                                        })
                                                    }
                                                    className="border-2 border-black bg-black px-3 py-1.5 text-[10px] font-bold uppercase text-white shadow-[2px_2px_0_0_#000] hover:bg-neutral-800 cursor-pointer"
                                                >
                                                    ⚡ Playground
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </section>
            </main>
        </div>
    );
};

export default Project;