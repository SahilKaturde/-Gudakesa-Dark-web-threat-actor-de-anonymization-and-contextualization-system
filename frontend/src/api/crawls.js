const CRAWL_BASE = (
    import.meta.env.VITE_CRAWL_API_URL || "http://127.0.0.1:8001"
).replace(/\/+$/, "");

/**
 * POST /crawls
 * Trigger a new crawl. Passes domain_id + JWT so FastAPI can
 * push results into database automatically.
 */
export async function triggerCrawl(onionUrl, domainId, jwt = "", depth = 1, maxPages = 50) {
    const res = await fetch(`${CRAWL_BASE}/crawls`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            url:        onionUrl,
            domain_id:  domainId,
            django_jwt: jwt,
            depth,
            max_pages:  maxPages,
        }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Crawl trigger failed: ${res.status}`);
    }
    return res.json();
}

/** GET /crawls - List all crawls. */
export async function getAllCrawls() {
    const res = await fetch(`${CRAWL_BASE}/crawls`);
    if (!res.ok) throw new Error("Failed to fetch crawls list");
    return res.json();
}

/**
 * GET /crawls/{crawl_id} - Poll status.
 * status values: "running" | "completed" | "failed" | "cancelled"
 */
export async function getCrawlStatus(crawlId) {
    const res = await fetch(`${CRAWL_BASE}/crawls/${crawlId}`);
    if (!res.ok) throw new Error(`Crawl ${crawlId} not found`);
    return res.json();
}

/** DELETE /crawls/{crawl_id} - Kill a running crawl. */
export async function stopCrawl(crawlId) {
    const res = await fetch(`${CRAWL_BASE}/crawls/${crawlId}`, { method: "DELETE" });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to stop crawl: ${res.status}`);
    }
    return res.json();
}

/** GET /crawls/{crawl_id}/pages - Get raw scraped pages from crawler */
export async function getCrawlPages(crawlId) {
    const res = await fetch(`${CRAWL_BASE}/crawls/${crawlId}/pages`);
    if (!res.ok) throw new Error("Failed to fetch crawl pages");
    return res.json();
}

/** POST /crawls/{crawl_id}/ingest - Ingest pages into DB */
export async function ingestCrawl(crawlId, domainId, jwt = "") {
    const res = await fetch(`${CRAWL_BASE}/crawls/${crawlId}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain_id: domainId, jwt }),
    });
    if (!res.ok) throw new Error("Failed to ingest crawl");
    return res.json();
}
