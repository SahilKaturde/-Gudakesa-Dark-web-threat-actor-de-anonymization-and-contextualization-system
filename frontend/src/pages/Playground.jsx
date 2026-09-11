import React, { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import api from "../api/axiosInstance";
import { useAuth } from "../context/AuthContext";

function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

const Playground = () => {
    const { domainId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const { user, logout } = useAuth();

    // Data states
    const [domainName, setDomainName] = useState(location.state?.domainName || "");
    const [pages, setPages] = useState(location.state?.pages || []);
    const [loading, setLoading] = useState(!location.state?.pages);
    const [error, setError] = useState("");

    // UI states
    const [selectedPageId, setSelectedPageId] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [aiPanelOpen, setAiPanelOpen] = useState(false);
    const [sidebarSearch, setSidebarSearch] = useState("");
    const [docSearch, setDocSearch] = useState("");
    const [showLineNumbers, setShowLineNumbers] = useState(true);
    const [viewMode, setViewMode] = useState("standard"); // "standard" | "code" | "plain"
    const [copied, setCopied] = useState(false);

    // AI Agent Interaction State
    const [aiInput, setAiInput] = useState("");
    const [aiMessages, setAiMessages] = useState([
        {
            sender: "agent",
            text: "Hello! I am your Gudakesa AI Threat Agent. Ready to analyze scraped dark web documents, summarize content, or extract onion entities.",
        },
    ]);

    // Fetch pages if not passed via location state
    useEffect(() => {
        if (!domainId) return;

        const fetchDomainAndPages = async () => {
            try {
                setLoading(true);
                const res = await api.get(`/domains/${domainId}/pages/`);
                setPages(res.data);
                if (res.data.length > 0) {
                    setSelectedPageId(res.data[0].page_id);
                    if (!domainName && res.data[0].page_url) {
                        try {
                            const u = new URL(res.data[0].page_url);
                            setDomainName(u.hostname);
                        } catch {
                            setDomainName(domainId);
                        }
                    }
                }
            } catch (err) {
                console.error("Failed to load playground documents:", err);
                setError("Failed to load scraped documents for this target.");
            } finally {
                setLoading(false);
            }
        };

        if (!location.state?.pages || location.state.pages.length === 0) {
            fetchDomainAndPages();
        } else {
            if (location.state.pages.length > 0) {
                setSelectedPageId(location.state.pages[0].page_id);
            }
            setLoading(false);
        }
    }, [domainId, location.state, domainName]);

    // Filter pages for sliding door menu
    const filteredPages = useMemo(() => {
        if (!sidebarSearch.trim()) return pages;
        const q = sidebarSearch.toLowerCase();
        return pages.filter(
            (p) =>
                (p.page_name && p.page_name.toLowerCase().includes(q)) ||
                (p.page_url && p.page_url.toLowerCase().includes(q))
        );
    }, [pages, sidebarSearch]);

    // Active page document — returns null when the window is closed
    const activePage = useMemo(() => {
        if (selectedPageId === null) return null;
        return pages.find((p) => p.page_id === selectedPageId) || null;
    }, [pages, selectedPageId]);

    // Calculate document statistics
    const activeDocStats = useMemo(() => {
        if (!activePage || !activePage.page_text)
            return { words: 0, chars: 0, lines: 0, readTimeMinutes: 1, lineArray: [] };
        const text = activePage.page_text;
        const lines = text.split("\n");
        const words = text.trim() ? text.trim().split(/\s+/).length : 0;
        const readTimeMinutes = Math.max(1, Math.ceil(words / 200));
        return {
            words,
            chars: text.length,
            lines: lines.length,
            readTimeMinutes,
            lineArray: lines,
        };
    }, [activePage]);

    // Copy to clipboard
    const handleCopy = () => {
        if (!activePage?.page_text) return;
        navigator.clipboard.writeText(activePage.page_text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    // Download text file
    const handleDownload = () => {
        if (!activePage) return;
        const element = document.createElement("a");
        const file = new Blob([activePage.page_text || ""], { type: "text/plain" });
        element.href = URL.createObjectURL(file);
        element.download = `${(activePage.page_name || "document").replace(
            /[^a-z0-9]/gi,
            "_"
        )}.txt`;
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    };

    // AI Agent Handler
    const handleSendAiPrompt = (textToSend) => {
        const prompt = textToSend || aiInput;
        if (!prompt.trim()) return;

        const userMsg = { sender: "user", text: prompt };
        setAiMessages((prev) => [...prev, userMsg]);
        setAiInput("");

        setTimeout(() => {
            let reply = "AI analysis complete. ";
            if (prompt.toLowerCase().includes("summarize")) {
                reply = `Summary: Contains ${activeDocStats.lines} lines and ${activeDocStats.words} words scraped from target ${activePage?.page_url || "onion site"}.`;
            } else if (prompt.toLowerCase().includes("entity") || prompt.toLowerCase().includes("extract")) {
                reply = "Entity Extraction: Scanned document text. Extracted 1 target URL and clean unstructured plaintext.";
            } else {
                reply = `Logged threat intelligence analysis for "${activePage?.page_name || "Document"}". Ready for future LLM integration.`;
            }
            setAiMessages((prev) => [...prev, { sender: "agent", text: reply }]);
        }, 500);
    };

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    return (
        <div className="flex h-screen w-screen flex-col overflow-hidden bg-white text-neutral-900 font-sans antialiased selection:bg-neutral-900 selection:text-white">
            {/* ═══════════════════════════════════════════════
               TOP NAVIGATION BAR (PURE WHITE BASE)
               ═══════════════════════════════════════════════ */}
            <header className="flex h-14 shrink-0 items-center justify-between border-b border-neutral-200 bg-white px-5 z-40 shadow-xs">
                <div className="flex items-center gap-4">
                    {/* Back Button */}
                    <button
                        onClick={() => navigate(-1)}
                        className="flex items-center gap-1.5 rounded border border-neutral-300 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-700 transition-colors hover:bg-neutral-100 hover:text-neutral-950 cursor-pointer"
                    >
                        <span>← Back</span>
                    </button>

                    <div className="h-4 w-px bg-neutral-200 hidden sm:block" />

                    {/* Logo & Title */}
                    <div className="flex items-center gap-2.5">
                        <div className="flex h-6 w-6 items-center justify-center rounded bg-neutral-900 text-white font-bold text-xs">
                            P
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-bold tracking-wider uppercase text-neutral-900">
                                Intel Playground
                            </span>
                            {domainName && (
                                <span className="font-mono text-[11px] text-neutral-600 border border-neutral-200 bg-neutral-50 px-2 py-0.5 rounded truncate max-w-[180px]">
                                    {domainName}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* View Switcher Controls (Standard / Structured / Plain) */}
                <div className="flex items-center gap-3">
                    <div className="flex items-center rounded border border-neutral-200 bg-neutral-100 p-0.5">
                        <button
                            onClick={() => setViewMode("standard")}
                            className={`px-3 py-1 text-xs font-semibold rounded transition-all cursor-pointer ${
                                viewMode === "standard"
                                    ? "bg-white text-neutral-900 shadow-sm"
                                    : "text-neutral-600 hover:text-neutral-950"
                            }`}
                            title="Normal Still Screen View"
                        >
                            🖥️ Standard
                        </button>
                        <button
                            onClick={() => setViewMode("code")}
                            className={`px-3 py-1 text-xs font-semibold rounded transition-all cursor-pointer ${
                                viewMode === "code"
                                    ? "bg-white text-neutral-900 shadow-sm"
                                    : "text-neutral-600 hover:text-neutral-950"
                            }`}
                            title="Structured Code View"
                        >
                            💻 Structured
                        </button>
                        <button
                            onClick={() => setViewMode("plain")}
                            className={`px-3 py-1 text-xs font-semibold rounded transition-all cursor-pointer ${
                                viewMode === "plain"
                                    ? "bg-white text-neutral-900 shadow-sm"
                                    : "text-neutral-600 hover:text-neutral-950"
                            }`}
                            title="Plain Reader View"
                        >
                            📄 Plain
                        </button>
                    </div>

                    {/* Sliding Drawer Toggle */}
                    <button
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        className={`flex items-center gap-2 rounded border px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                            sidebarOpen
                                ? "border-neutral-300 bg-neutral-100 text-neutral-800 hover:bg-neutral-200"
                                : "border-neutral-900 bg-neutral-900 text-white hover:bg-neutral-800"
                        }`}
                    >
                        <span>{sidebarOpen ? "◄ Drawer" : "► Drawer"}</span>
                        <span className="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-[10px] text-neutral-800">
                            {pages.length}
                        </span>
                    </button>

                    {/* AI Agent Panel Toggle */}
                    <button
                        onClick={() => setAiPanelOpen(!aiPanelOpen)}
                        className={`flex items-center gap-1.5 rounded border px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                            aiPanelOpen
                                ? "border-neutral-900 bg-neutral-900 text-white shadow-sm"
                                : "border-neutral-300 bg-white text-neutral-800 hover:bg-neutral-100"
                        }`}
                    >
                        <span>🤖 AI Agent</span>
                    </button>

                    <button
                        onClick={handleLogout}
                        className="rounded border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 cursor-pointer"
                    >
                        Logout
                    </button>
                </div>
            </header>

            {/* ═══════════════════════════════════════════════
               MAIN BODY LAYOUT (WHITE BASE)
               ═══════════════════════════════════════════════ */}
            <div className="relative flex flex-1 overflow-hidden bg-neutral-50">
                {/* ─────────────────────────────────────────────
                   LEFT SLIDING DOOR MENU (DRAWER - WHITE)
                   ───────────────────────────────────────────── */}
                <aside
                    className={`absolute top-0 bottom-0 left-0 z-30 flex w-80 flex-col border-r border-neutral-200 bg-white text-neutral-900 transition-all duration-300 ease-in-out md:relative ${
                        sidebarOpen
                            ? "translate-x-0"
                            : "-translate-x-full md:-ml-80"
                    }`}
                >
                    <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3 bg-neutral-50">
                        <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-800">
                            Documents Drawer ({pages.length})
                        </h2>
                        <span className="font-mono text-[10px] text-neutral-500">
                            {filteredPages.length} filtered
                        </span>
                    </div>

                    <div className="border-b border-neutral-200 p-3 bg-white">
                        <input
                            type="text"
                            value={sidebarSearch}
                            onChange={(e) => setSidebarSearch(e.target.value)}
                            placeholder="Filter documents..."
                            className="w-full rounded border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs font-sans text-neutral-900 placeholder-neutral-400 focus:border-neutral-400 focus:bg-white focus:outline-none"
                        />
                    </div>

                    <div className="flex-1 overflow-y-auto p-2 space-y-1">
                        {loading ? (
                            <div className="p-8 text-center text-xs text-neutral-400">
                                Loading documents...
                            </div>
                        ) : filteredPages.length === 0 ? (
                            <div className="p-8 text-center text-xs text-neutral-400">
                                No matching documents.
                            </div>
                        ) : (
                            filteredPages.map((page, idx) => {
                                const isSelected = activePage?.page_id === page.page_id;
                                return (
                                    <button
                                        key={page.page_id}
                                        onClick={() => setSelectedPageId(page.page_id)}
                                        className={`flex w-full text-left p-3 rounded transition-colors cursor-pointer border ${
                                            isSelected
                                                ? "border-neutral-900 bg-neutral-900 text-white shadow-xs"
                                                : "border-transparent hover:bg-neutral-100 text-neutral-700"
                                        }`}
                                    >
                                        <div
                                            className={`mr-3 flex h-6 w-6 shrink-0 items-center justify-center rounded border font-mono text-[10px] font-bold ${
                                                isSelected
                                                    ? "border-neutral-700 bg-white text-neutral-950"
                                                    : "border-neutral-200 bg-neutral-100 text-neutral-500"
                                            }`}
                                        >
                                            {idx + 1}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className={`truncate text-xs font-semibold ${
                                                isSelected ? "text-white" : "text-neutral-900"
                                            }`}>
                                                {page.page_name || "Untitled Document"}
                                            </p>
                                            <p className={`mt-1 truncate font-mono text-[10px] ${
                                                isSelected ? "text-neutral-300" : "text-neutral-400"
                                            }`}>
                                                {page.page_url}
                                            </p>
                                            <div className={`mt-1.5 flex items-center justify-between font-mono text-[9px] ${
                                                isSelected ? "text-neutral-300" : "text-neutral-400"
                                            }`}>
                                                <span>{formatBytes(page.content_length)}</span>
                                                {page.created_at && (
                                                    <span>
                                                        {new Date(page.created_at).toLocaleTimeString([], {
                                                            hour: "2-digit",
                                                            minute: "2-digit",
                                                        })}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </button>
                                );
                            })
                        )}
                    </div>

                    <div className="flex items-center justify-between border-t border-neutral-200 bg-neutral-50 p-3 font-mono text-[10px] text-neutral-500">
                        <span>COUNT: <strong className="text-neutral-900">{pages.length}</strong></span>
                        <span>
                            TOTAL:{" "}
                            <strong className="text-neutral-900">
                                {formatBytes(
                                    pages.reduce((acc, p) => acc + (p.content_length || 0), 0)
                                )}
                            </strong>
                        </span>
                    </div>
                </aside>

                {/* ─────────────────────────────────────────────
                   CENTER MAIN WORKSPACE (WHITE BASE)
                   ───────────────────────────────────────────── */}
                <main className="flex flex-1 flex-col overflow-hidden bg-white text-neutral-900">
                    {loading ? (
                        <div className="flex h-full flex-col items-center justify-center">
                            <div className="h-6 w-6 animate-spin rounded-full border-2 border-neutral-900 border-t-transparent" />
                            <p className="mt-4 font-mono text-xs text-neutral-400">
                                Loading Document...
                            </p>
                        </div>
                    ) : error ? (
                        <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                            <div className="max-w-md rounded border border-neutral-200 bg-white p-8 text-neutral-800 shadow-sm">
                                <h3 className="text-base font-bold text-neutral-900">Error</h3>
                                <p className="mt-2 text-xs font-mono text-neutral-500">{error}</p>
                                <button
                                    onClick={() => navigate(-1)}
                                    className="mt-6 rounded border border-neutral-300 bg-neutral-100 px-4 py-2 text-xs font-semibold text-neutral-900 hover:bg-neutral-200 cursor-pointer"
                                >
                                    Return to Project
                                </button>
                            </div>
                        </div>
                    ) : !activePage ? (
                        /* ── BLANK WHITE SCREEN (document window closed) ── */
                        <div className="flex-1 bg-white" />
                    ) : (
                        <>
                            {/* DOCUMENT ACTION TOOLBAR */}
                            <div className="flex flex-wrap items-center justify-between border-b border-neutral-200 bg-white px-6 py-3 gap-4">
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-3">
                                        <h1 className="truncate text-sm font-bold text-neutral-900 uppercase tracking-wide">
                                            {activePage.page_name || "Untitled Document"}
                                        </h1>
                                        <span className="rounded border border-neutral-200 bg-neutral-100 px-2 py-0.5 font-mono text-[10px] text-neutral-600 font-semibold">
                                            {formatBytes(activePage.content_length)}
                                        </span>
                                    </div>
                                    <a
                                        href={activePage.page_url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="mt-0.5 block truncate font-mono text-xs text-neutral-500 hover:text-neutral-950 transition-colors"
                                    >
                                        {activePage.page_url}
                                    </a>
                                </div>

                                <div className="flex flex-wrap items-center gap-2">
                                    <input
                                        type="text"
                                        value={docSearch}
                                        onChange={(e) => setDocSearch(e.target.value)}
                                        placeholder="Find in text..."
                                        className="w-40 rounded border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs font-sans text-neutral-900 placeholder-neutral-400 focus:border-neutral-400 focus:bg-white focus:outline-none"
                                    />

                                    {viewMode === "code" && (
                                        <button
                                            onClick={() => setShowLineNumbers(!showLineNumbers)}
                                            className={`rounded border px-3 py-1.5 text-xs font-mono font-medium transition-colors cursor-pointer ${
                                                showLineNumbers
                                                    ? "border-neutral-900 bg-neutral-900 text-white"
                                                    : "border-neutral-200 bg-white text-neutral-600 hover:text-neutral-950"
                                            }`}
                                        >
                                            # Lines
                                        </button>
                                    )}

                                    <button
                                        onClick={handleCopy}
                                        className="rounded border border-neutral-300 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-800 hover:bg-neutral-100 transition-colors cursor-pointer"
                                    >
                                        {copied ? "✓ Copied" : "📋 Copy"}
                                    </button>

                                    <button
                                        onClick={handleDownload}
                                        className="rounded border border-neutral-900 bg-neutral-900 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-neutral-800 transition-colors cursor-pointer shadow-xs"
                                    >
                                        💾 Download .TXT
                                    </button>

                                    <button
                                        onClick={() => setSelectedPageId(null)}
                                        className="rounded border border-neutral-300 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:border-neutral-900 hover:text-neutral-950 hover:bg-neutral-100 transition-colors cursor-pointer ml-1"
                                        title="Close active document window"
                                    >
                                        ✕ Close Document
                                    </button>
                                </div>
                            </div>

                            {/* STATS STRIP */}
                            <div className="flex items-center justify-between border-b border-neutral-200 bg-neutral-50 px-6 py-2 font-mono text-[11px] text-neutral-500">
                                <div className="flex items-center gap-6">
                                    <span>LINES: <strong className="text-neutral-900">{activeDocStats.lines}</strong></span>
                                    <span>WORDS: <strong className="text-neutral-900">{activeDocStats.words}</strong></span>
                                    <span>CHARS: <strong className="text-neutral-900">{activeDocStats.chars}</strong></span>
                                    <span>READ TIME: <strong className="text-neutral-900">~{activeDocStats.readTimeMinutes} min</strong></span>
                                </div>
                                {docSearch && (
                                    <span className="text-neutral-900 font-semibold text-[10px]">
                                        Filtering lines matching: "{docSearch}"
                                    </span>
                                )}
                            </div>

                            {/* ─────────────────────────────────────────────
                                VIEW MODE DISPLAY (WHITE BASE)
                                ───────────────────────────────────────────── */}
                            {viewMode === "plain" ? (
                                /* 1. PLAIN PAPER READER MODE */
                                <div className="flex-1 overflow-auto bg-neutral-100 p-8">
                                    <div className="mx-auto max-w-3xl min-h-full rounded border border-neutral-200 bg-white p-10 text-neutral-900 shadow-md">
                                        <div className="mb-6 border-b border-neutral-200 pb-4">
                                            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                                                Plain Reader Document
                                            </span>
                                            <h2 className="mt-1 text-xl font-bold tracking-tight text-neutral-900 font-sans">
                                                {activePage.page_name || "Untitled Document"}
                                            </h2>
                                            <p className="mt-1 font-mono text-xs text-neutral-500 break-all">
                                                {activePage.page_url}
                                            </p>
                                        </div>

                                        <div className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-words text-neutral-800">
                                            {docSearch.trim() !== "" ? (
                                                activeDocStats.lineArray
                                                    .filter((l) => l.toLowerCase().includes(docSearch.toLowerCase()))
                                                    .join("\n") || <span className="italic text-neutral-400">No matching lines.</span>
                                            ) : (
                                                activePage.page_text || <span className="italic text-neutral-400">[ Document is empty ]</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ) : viewMode === "code" ? (
                                /* 2. STRUCTURED CODE VIEW MODE */
                                <div className="flex-1 overflow-auto bg-white p-6 font-mono text-xs leading-relaxed selection:bg-neutral-200">
                                    {activeDocStats.lineArray && activeDocStats.lineArray.length > 0 ? (
                                        <div className="table w-full border-collapse">
                                            {activeDocStats.lineArray.map((line, idx) => {
                                                const lineNumber = idx + 1;
                                                const matchesSearch =
                                                    docSearch.trim() !== "" &&
                                                    line.toLowerCase().includes(docSearch.toLowerCase());

                                                if (docSearch.trim() !== "" && !matchesSearch) {
                                                    return null;
                                                }

                                                return (
                                                    <div
                                                        key={idx}
                                                        className={`table-row hover:bg-neutral-50 transition-colors ${
                                                            matchesSearch ? "bg-yellow-50 font-medium" : ""
                                                        }`}
                                                    >
                                                        {showLineNumbers && (
                                                            <div className="table-cell w-12 border-r border-neutral-200 pr-4 text-right font-mono text-neutral-400 bg-neutral-50/50 select-none">
                                                                {lineNumber}
                                                            </div>
                                                        )}
                                                        <div className="table-cell whitespace-pre-wrap break-words pl-4 py-0.5 text-neutral-800">
                                                            {line || "\u00A0"}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="text-neutral-400 italic">
                                            [ Document is empty ]
                                        </div>
                                    )}
                                </div>
                            ) : (
                                /* 3. NORMAL STILL SCREEN MODE (WHITE STILL CANVAS) */
                                <div className="flex-1 overflow-hidden flex flex-col bg-neutral-100/70 p-6">
                                    <div className="flex-1 flex flex-col rounded border border-neutral-200 bg-white shadow-sm overflow-hidden">
                                        {/* Still Screen Header */}
                                        <div className="flex items-center justify-between border-b border-neutral-200 bg-neutral-50 px-6 py-3 text-xs">
                                            <div className="flex items-center gap-2">
                                                <span className="h-2 w-2 rounded-full bg-neutral-900" />
                                                <span className="font-bold uppercase tracking-wider text-neutral-800">
                                                    Normal Still Screen View
                                                </span>
                                            </div>
                                            <span className="font-mono text-[10px] text-neutral-400">
                                                Static Reader Window
                                            </span>
                                        </div>

                                        {/* Still Screen Fixed Content Box */}
                                        <div className="flex-1 overflow-y-auto p-6 font-mono text-xs leading-relaxed text-neutral-800">
                                            {docSearch.trim() !== "" ? (
                                                activeDocStats.lineArray
                                                    .filter((l) => l.toLowerCase().includes(docSearch.toLowerCase()))
                                                    .map((line, idx) => (
                                                        <div key={idx} className="py-0.5 border-b border-neutral-100">
                                                            {line || "\u00A0"}
                                                        </div>
                                                    ))
                                            ) : (
                                                <pre className="whitespace-pre-wrap break-words font-mono text-xs text-neutral-800">
                                                    {activePage.page_text || "[ Empty Document ]"}
                                                </pre>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </main>

                {/* ─────────────────────────────────────────────
                   RIGHT AI AGENT PANEL (WHITE DRAWER)
                   ───────────────────────────────────────────── */}
                <aside
                    className={`absolute top-0 bottom-0 right-0 z-30 flex w-88 flex-col border-l border-neutral-200 bg-white text-neutral-900 transition-all duration-300 ease-in-out md:relative ${
                        aiPanelOpen
                            ? "translate-x-0"
                            : "translate-x-full md:-mr-88"
                    }`}
                >
                    {/* AI Agent Header */}
                    <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3 bg-neutral-50">
                        <div className="flex items-center gap-2">
                            <span className="text-sm">🤖</span>
                            <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-900">
                                AI Threat Agent
                            </h2>
                        </div>
                        <button
                            onClick={() => setAiPanelOpen(false)}
                            className="text-neutral-400 hover:text-neutral-900 cursor-pointer"
                        >
                            ✕
                        </button>
                    </div>

                    {/* Quick AI Actions */}
                    <div className="border-b border-neutral-200 p-3 bg-white flex flex-wrap gap-1.5">
                        <button
                            onClick={() => handleSendAiPrompt("Summarize Document")}
                            className="rounded border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] font-semibold text-neutral-700 hover:bg-neutral-100 hover:text-neutral-950 transition-colors cursor-pointer"
                        >
                            ⚡ Summarize Document
                        </button>
                        <button
                            onClick={() => handleSendAiPrompt("Extract Entities")}
                            className="rounded border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] font-semibold text-neutral-700 hover:bg-neutral-100 hover:text-neutral-950 transition-colors cursor-pointer"
                        >
                            🔍 Extract Entities
                        </button>
                        <button
                            onClick={() => handleSendAiPrompt("Check Threat Level")}
                            className="rounded border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] font-semibold text-neutral-700 hover:bg-neutral-100 hover:text-neutral-950 transition-colors cursor-pointer"
                        >
                            🛡️ Threat Assessment
                        </button>
                    </div>

                    {/* AI Messages Chat Window */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-3 font-sans text-xs bg-neutral-50/50">
                        {aiMessages.map((msg, idx) => (
                            <div
                                key={idx}
                                className={`flex flex-col ${
                                    msg.sender === "user" ? "items-end" : "items-start"
                                }`}
                            >
                                <span className="mb-1 font-mono text-[9px] uppercase tracking-wider text-neutral-400">
                                    {msg.sender === "user" ? "You" : "Gudakesa AI"}
                                </span>
                                <div
                                    className={`rounded p-3 text-xs leading-relaxed max-w-[90%] border ${
                                        msg.sender === "user"
                                            ? "border-neutral-900 bg-neutral-900 text-white shadow-xs"
                                            : "border-neutral-200 bg-white text-neutral-800 shadow-xs"
                                    }`}
                                >
                                    {msg.text}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* AI Input Input Box */}
                    <div className="border-t border-neutral-200 p-3 bg-white flex gap-2">
                        <input
                            type="text"
                            value={aiInput}
                            onChange={(e) => setAiInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleSendAiPrompt()}
                            placeholder="Ask AI agent about document..."
                            className="flex-1 rounded border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs text-neutral-900 placeholder-neutral-400 focus:border-neutral-400 focus:bg-white focus:outline-none"
                        />
                        <button
                            onClick={() => handleSendAiPrompt()}
                            className="rounded border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-neutral-800 transition-colors cursor-pointer"
                        >
                            Send
                        </button>
                    </div>
                </aside>
            </div>
        </div>
    );
};

export default Playground;