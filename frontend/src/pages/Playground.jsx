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

const AI_SERVICE_URL = "http://127.0.0.1:8002";

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
    const [featuresDrawerOpen, setFeaturesDrawerOpen] = useState(false);
    const [sidebarSearch, setSidebarSearch] = useState("");
    const [docSearch, setDocSearch] = useState("");
    const [showLineNumbers, setShowLineNumbers] = useState(true);
    const [viewMode, setViewMode] = useState("standard"); // "standard" | "code" | "plain"
    const [copied, setCopied] = useState(false);

    // AI Feature Extraction States
    const [extractedFeatures, setExtractedFeatures] = useState([]);
    const [extracting, setExtracting] = useState(false);
    const [extractionMessage, setExtractionMessage] = useState("");
    const [featureFilter, setFeatureFilter] = useState("all");
    const [featureSearch, setFeatureSearch] = useState("");
    const [copiedFeatureId, setCopiedFeatureId] = useState(null);

    // AI Chat States
    const [aiInput, setAiInput] = useState("");
    const [aiSending, setAiSending] = useState(false);
    const [aiMessages, setAiMessages] = useState([
        {
            sender: "agent",
            text: "Hello! I am your GUDAKESA AI Threat Intelligence Agent. I can analyze scraped dark web documents, answer questions about extracted indicators, and generate visualizations. What would you like to investigate?",
        },
    ]);

    // Graph & Report States
    const [graphLoading, setGraphLoading] = useState(false);
    const [reportLoading, setReportLoading] = useState(false);
    const [reportData, setReportData] = useState(null);
    const [showReport, setShowReport] = useState(false);

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

    // Active page document
    const activePage = useMemo(() => {
        if (selectedPageId === null) return null;
        return pages.find((p) => p.page_id === selectedPageId) || null;
    }, [pages, selectedPageId]);

    // Fetch existing extracted features whenever activePage changes
    useEffect(() => {
        if (!activePage || !activePage.page_id) {
            setExtractedFeatures([]);
            return;
        }

        const fetchFeatures = async () => {
            try {
                const res = await fetch(`${AI_SERVICE_URL}/api/v1/features?page_id=${activePage.page_id}`);
                if (res.ok) {
                    const data = await res.json();
                    setExtractedFeatures(data);
                }
            } catch (err) {
                console.log("Failed to fetch features from AI service, falling back to Django API");
                try {
                    const djangoRes = await api.get(`/features/?page=${activePage.page_id}`);
                    setExtractedFeatures(djangoRes.data);
                } catch (e) {
                    console.error("Failed to fetch features:", e);
                }
            }
        };

        fetchFeatures();
    }, [activePage]);

    // Handler to trigger AI Feature Extraction
    const handleExtractFeatures = async () => {
        if (!activePage) return;

        setExtracting(true);
        setExtractionMessage("Initializing LangGraph feature extraction agent...");
        setFeaturesDrawerOpen(true); // Open the extracted features drawer immediately

        try {
            const response = await fetch(`${AI_SERVICE_URL}/api/v1/extract-features`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    domain_id: domainId,
                    page_id: activePage.page_id,
                    page_text: activePage.page_text || "",
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP Error ${response.status}`);
            }

            const data = await response.json();
            setExtractedFeatures(data.features || []);
            setExtractionMessage(`Successfully extracted ${data.extracted_count || 0} threat features!`);
        } catch (err) {
            console.error("Feature Extraction failed:", err);
            setExtractionMessage("Extraction failed. Please check AI service backend.");
        } finally {
            setExtracting(false);
        }
    };

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

    // Filter extracted features for right drawer
    const filteredExtractedFeatures = useMemo(() => {
        return extractedFeatures.filter((item) => {
            const matchesCategory =
                featureFilter === "all" ||
                item.feature_type.toLowerCase() === featureFilter.toLowerCase();
            const matchesSearch =
                !featureSearch.trim() ||
                item.feature_value.toLowerCase().includes(featureSearch.toLowerCase()) ||
                (item.context && item.context.toLowerCase().includes(featureSearch.toLowerCase())) ||
                (item.description && item.description.toLowerCase().includes(featureSearch.toLowerCase()));
            return matchesCategory && matchesSearch;
        });
    }, [extractedFeatures, featureFilter, featureSearch]);

    // Copy to clipboard handlers
    const handleCopy = () => {
        if (!activePage?.page_text) return;
        navigator.clipboard.writeText(activePage.page_text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleCopyFeatureVal = (val, id) => {
        navigator.clipboard.writeText(val);
        setCopiedFeatureId(id);
        setTimeout(() => setCopiedFeatureId(null), 2000);
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

    // Real AI Chat handler — calls backend (OpenRouter → Ollama → fallback)
    const handleSendAiPrompt = async (textToSend) => {
        const prompt = (textToSend || aiInput).trim();
        if (!prompt) return;

        const userMsg = { sender: "user", text: prompt };
        setAiMessages((prev) => [...prev, userMsg]);
        setAiInput("");
        setAiSending(true);

        try {
            const res = await fetch(`${AI_SERVICE_URL}/api/v1/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: prompt,
                    page_text: activePage?.page_text || "",
                    features: extractedFeatures,
                    history: aiMessages.slice(-8),
                    page_id: activePage?.page_id || null,
                    domain_id: domainId || null,
                }),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            const agentMsg = {
                sender: "agent",
                text: data.response || "Analysis complete.",
                llm_used: data.llm_used,
                graph_base64: data.graph_base64 || null,
                graph_type: data.graph_type || null,
            };
            setAiMessages((prev) => [...prev, agentMsg]);
        } catch (err) {
            console.error("AI chat error:", err);
            setAiMessages((prev) => [
                ...prev,
                { sender: "agent", text: "⚠️ AI service unavailable. Please ensure the intelligence service is running on port 8002." },
            ]);
        } finally {
            setAiSending(false);
        }
    };

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    // Graph generation handler
    const handleGenerateGraph = async (graphType = "bar") => {
        if (!extractedFeatures.length) return;
        setGraphLoading(true);
        try {
            const res = await fetch(`${AI_SERVICE_URL}/api/v1/generate-graph`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ features: extractedFeatures, graph_type: graphType }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setAiMessages((prev) => [
                ...prev,
                {
                    sender: "agent",
                    text: `📊 Generated **${graphType}** chart for ${data.feature_count} indicators:`,
                    graph_base64: data.graph_base64,
                    graph_type: graphType,
                },
            ]);
            setAiPanelOpen(true);
        } catch (err) {
            console.error("Graph generation failed:", err);
        } finally {
            setGraphLoading(false);
        }
    };

    // Investigation report generation handler
    const handleGenerateReport = async () => {
        if (!activePage) return;
        setReportLoading(true);
        try {
            const res = await fetch(`${AI_SERVICE_URL}/api/v1/generate-report`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    domain_id: domainId,
                    page_id: activePage.page_id,
                    page_url: activePage.page_url || "",
                    page_name: activePage.page_name || "Unknown Document",
                    page_text: activePage.page_text || "",
                    features: extractedFeatures,
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setReportData(data);
            setShowReport(true);
        } catch (err) {
            console.error("Report generation failed:", err);
            alert("Report generation failed. Ensure the AI service is running on port 8002.");
        } finally {
            setReportLoading(false);
        }
    };

    return (
        <>
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

                {/* View Switcher & Drawer Controls */}
                <div className="flex items-center gap-2.5">
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

                    {/* Left Sliding Drawer Toggle */}
                    <button
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        className={`flex items-center gap-1.5 rounded border px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
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

                    {/* Right Extracted Features Drawer Toggle */}
                    <button
                        onClick={() => {
                            setFeaturesDrawerOpen(!featuresDrawerOpen);
                            if (aiPanelOpen) setAiPanelOpen(false);
                        }}
                        className={`flex items-center gap-1.5 rounded border px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                            featuresDrawerOpen
                                ? "border-neutral-900 bg-neutral-900 text-white shadow-sm"
                                : "border-neutral-300 bg-white text-neutral-800 hover:bg-neutral-100"
                        }`}
                        title="Open Extracted Features Drawer"
                    >
                        <span>⚡ Extracted Features</span>
                        {extractedFeatures.length > 0 && (
                            <span className="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-[10px] font-bold text-neutral-900">
                                {extractedFeatures.length}
                            </span>
                        )}
                    </button>

                    {/* Right AI Agent Panel Toggle */}
                    <button
                        onClick={() => {
                            setAiPanelOpen(!aiPanelOpen);
                            if (featuresDrawerOpen) setFeaturesDrawerOpen(false);
                        }}
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
                                    {/* ⚡ EXTRACT FEATURE BUTTON */}
                                    <button
                                        onClick={handleExtractFeatures}
                                        disabled={extracting}
                                        className={`flex items-center gap-1.5 rounded border px-3.5 py-1.5 text-xs font-bold transition-all cursor-pointer shadow-xs ${
                                            extracting
                                                ? "border-neutral-400 bg-neutral-200 text-neutral-600 cursor-not-allowed"
                                                : "border-neutral-900 bg-neutral-900 text-white hover:bg-neutral-800"
                                        }`}
                                    >
                                        {extracting ? (
                                            <>
                                                <div className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-600 border-t-transparent" />
                                                <span>Extracting...</span>
                                            </>
                                        ) : (
                                            <>
                                                <span>⚡ Extract Feature</span>
                                            </>
                                        )}
                                    </button>

                                    <input
                                        type="text"
                                        value={docSearch}
                                        onChange={(e) => setDocSearch(e.target.value)}
                                        placeholder="Find in text..."
                                        className="w-36 rounded border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs font-sans text-neutral-900 placeholder-neutral-400 focus:border-neutral-400 focus:bg-white focus:outline-none"
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
                                        className="rounded border border-neutral-300 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-800 hover:bg-neutral-100 transition-colors cursor-pointer"
                                    >
                                        💾 TXT
                                    </button>

                                    {/* 📊 GRAPH BUTTONS */}
                                    {extractedFeatures.length > 0 && (
                                        <>
                                            <button
                                                onClick={() => handleGenerateGraph("bar")}
                                                disabled={graphLoading}
                                                className="rounded border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors cursor-pointer disabled:opacity-50"
                                                title="Bar chart of features"
                                            >
                                                {graphLoading ? "⏳" : "📊"} Bar
                                            </button>
                                            <button
                                                onClick={() => handleGenerateGraph("pie")}
                                                disabled={graphLoading}
                                                className="rounded border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-100 transition-colors cursor-pointer disabled:opacity-50"
                                                title="Pie chart of features"
                                            >
                                                {graphLoading ? "⏳" : "🥧"} Pie
                                            </button>
                                            <button
                                                onClick={() => handleGenerateGraph("confidence")}
                                                disabled={graphLoading}
                                                className="rounded border border-cyan-300 bg-cyan-50 px-3 py-1.5 text-xs font-semibold text-cyan-700 hover:bg-cyan-100 transition-colors cursor-pointer disabled:opacity-50"
                                                title="Confidence chart"
                                            >
                                                {graphLoading ? "⏳" : "📈"} Conf
                                            </button>
                                        </>
                                    )}

                                    {/* 📋 GENERATE REPORT BUTTON */}
                                    <button
                                        onClick={handleGenerateReport}
                                        disabled={reportLoading}
                                        className={`flex items-center gap-1.5 rounded border px-3.5 py-1.5 text-xs font-bold transition-all cursor-pointer ${
                                            reportLoading
                                                ? "border-neutral-300 bg-neutral-100 text-neutral-500 cursor-not-allowed"
                                                : "border-emerald-700 bg-emerald-700 text-white hover:bg-emerald-600"
                                        }`}
                                        title="Generate Investigation Report"
                                    >
                                        {reportLoading ? (
                                            <><div className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-400 border-t-transparent" /><span>Generating...</span></>
                                        ) : (
                                            <span>📋 Report</span>
                                        )}
                                    </button>

                                    <button
                                        onClick={() => setSelectedPageId(null)}
                                        className="rounded border border-neutral-300 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:border-neutral-900 hover:text-neutral-950 hover:bg-neutral-100 transition-colors cursor-pointer"
                                        title="Close active document window"
                                    >
                                        ✕ Close
                                    </button>
                                </div>

                            </div>

                            {/* STATS STRIP */}
                            <div className="flex items-center justify-between border-b border-neutral-200 bg-neutral-50 px-6 py-2 font-mono text-[11px] text-neutral-500">
                                <div className="flex items-center gap-6">
                                    <span>LINES: <strong className="text-neutral-900">{activeDocStats.lines}</strong></span>
                                    <span>WORDS: <strong className="text-neutral-900">{activeDocStats.words}</strong></span>
                                    <span>EXTRACTED FEATURES: <strong className="text-neutral-900">{extractedFeatures.length}</strong></span>
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
                   RIGHT DRAWER 1: EXTRACTED FEATURES DRAWER
                   ───────────────────────────────────────────── */}
                <aside
                    className={`absolute top-0 bottom-0 right-0 z-30 flex w-96 flex-col border-l border-neutral-200 bg-white text-neutral-900 transition-all duration-300 ease-in-out md:relative ${
                        featuresDrawerOpen
                            ? "translate-x-0"
                            : "translate-x-full md:-mr-96"
                    }`}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3 bg-neutral-50">
                        <div className="flex items-center gap-2">
                            <span className="text-sm">⚡</span>
                            <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-900">
                                Extracted Threat Features
                            </h2>
                            <span className="rounded bg-neutral-900 px-2 py-0.5 font-mono text-[10px] font-bold text-white">
                                {extractedFeatures.length}
                            </span>
                        </div>
                        <button
                            onClick={() => setFeaturesDrawerOpen(false)}
                            className="text-neutral-400 hover:text-neutral-900 cursor-pointer font-bold"
                        >
                            ✕
                        </button>
                    </div>

                    {/* Extraction Status Bar */}
                    {extractionMessage && (
                        <div className="border-b border-neutral-200 bg-neutral-100 px-4 py-2 text-[11px] font-mono text-neutral-800 flex items-center justify-between">
                            <span>{extractionMessage}</span>
                            {extracting && (
                                <div className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-900 border-t-transparent" />
                            )}
                        </div>
                    )}

                    {/* Category Filter Tabs */}
                    <div className="border-b border-neutral-200 p-2 bg-white flex flex-wrap gap-1">
                        {["all", "username", "email", "ip", "crypto_wallet", "post", "other"].map((cat) => (
                            <button
                                key={cat}
                                onClick={() => setFeatureFilter(cat)}
                                className={`px-2 py-0.5 text-[10px] font-mono font-semibold rounded uppercase transition-colors cursor-pointer ${
                                    featureFilter === cat
                                        ? "bg-neutral-900 text-white"
                                        : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                                }`}
                            >
                                {cat.replace("_", " ")}
                            </button>
                        ))}
                    </div>

                    {/* Feature Search Box */}
                    <div className="border-b border-neutral-200 p-3 bg-white">
                        <input
                            type="text"
                            value={featureSearch}
                            onChange={(e) => setFeatureSearch(e.target.value)}
                            placeholder="Filter extracted features..."
                            className="w-full rounded border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs text-neutral-900 placeholder-neutral-400 focus:border-neutral-400 focus:bg-white focus:outline-none"
                        />
                    </div>

                    {/* Feature List Cards */}
                    <div className="flex-1 overflow-y-auto p-3 space-y-2.5 bg-neutral-50/50">
                        {extracting ? (
                            <div className="p-8 text-center">
                                <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-neutral-900 border-t-transparent" />
                                <p className="mt-3 font-mono text-xs text-neutral-500">
                                    LangGraph Agent Extracting Entities...
                                </p>
                            </div>
                        ) : filteredExtractedFeatures.length === 0 ? (
                            <div className="p-8 text-center text-xs text-neutral-400">
                                {extractedFeatures.length === 0
                                    ? 'No features extracted yet. Click "⚡ Extract Feature" to scan this document.'
                                    : "No matching features found."}
                            </div>
                        ) : (
                            filteredExtractedFeatures.map((item, idx) => {
                                const isCopied = copiedFeatureId === (item.feature_id || idx);
                                return (
                                    <div
                                        key={item.feature_id || idx}
                                        className="rounded border border-neutral-200 bg-white p-3 shadow-xs hover:border-neutral-300 transition-colors"
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="rounded bg-neutral-900 px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-white">
                                                {item.feature_type}
                                            </span>
                                            {item.confidence_score !== undefined && (
                                                <span className="font-mono text-[10px] text-neutral-500">
                                                    {Math.round((item.confidence_score || 0) * 100)}% Confidence
                                                </span>
                                            )}
                                        </div>

                                        <div className="mt-2 flex items-center justify-between gap-2">
                                            <code className="font-mono text-xs font-bold text-neutral-900 break-all select-all">
                                                {item.feature_value}
                                            </code>
                                            <button
                                                onClick={() => handleCopyFeatureVal(item.feature_value, item.feature_id || idx)}
                                                className="shrink-0 rounded border border-neutral-200 bg-neutral-50 px-2 py-1 text-[10px] font-semibold text-neutral-700 hover:bg-neutral-200 transition-colors cursor-pointer"
                                            >
                                                {isCopied ? "✓ Copied" : "Copy"}
                                            </button>
                                        </div>

                                        {item.context && (
                                            <div className="mt-2 border-t border-neutral-100 pt-2 font-mono text-[10px] text-neutral-600 bg-neutral-50 p-2 rounded break-words">
                                                <span className="font-bold text-neutral-400">Context: </span>
                                                "{item.context}"
                                            </div>
                                        )}

                                        {item.description && (
                                            <p className="mt-1 text-[11px] text-neutral-500 italic">
                                                {item.description}
                                            </p>
                                        )}
                                    </div>
                                );
                            })
                        )}
                    </div>

                    <div className="border-t border-neutral-200 bg-neutral-50 p-3 font-mono text-[10px] text-neutral-500 flex justify-between">
                        <span>TOTAL: <strong className="text-neutral-900">{extractedFeatures.length}</strong></span>
                        <button
                            onClick={handleExtractFeatures}
                            className="text-neutral-900 font-bold hover:underline cursor-pointer"
                        >
                            Re-Extract
                        </button>
                    </div>
                </aside>

                {/* ─────────────────────────────────────────────
                   RIGHT DRAWER 2: AI AGENT PANEL (WHITE DRAWER)
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
                        <button onClick={() => handleSendAiPrompt("Summarize this document's key findings.")} className="rounded border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] font-semibold text-neutral-700 hover:bg-neutral-100 transition-colors cursor-pointer">⚡ Summarize</button>
                        <button onClick={() => handleSendAiPrompt("What usernames and aliases are in the extracted features?")} className="rounded border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] font-semibold text-neutral-700 hover:bg-neutral-100 transition-colors cursor-pointer">👤 Usernames</button>
                        <button onClick={() => handleSendAiPrompt("What crypto wallets were found? Assess risk.")} className="rounded border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-[10px] font-semibold text-neutral-700 hover:bg-neutral-100 transition-colors cursor-pointer">💰 Wallets</button>
                        <button onClick={() => handleSendAiPrompt("Generate a bar chart of the extracted features.")} className="rounded border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors cursor-pointer">📊 Bar Chart</button>
                        <button onClick={() => handleSendAiPrompt("Show a pie chart of feature distribution.")} className="rounded border border-violet-200 bg-violet-50 px-2.5 py-1 text-[10px] font-semibold text-violet-700 hover:bg-violet-100 transition-colors cursor-pointer">🥧 Pie Chart</button>
                        <button onClick={() => handleSendAiPrompt("Assess the overall threat level of this document.")} className="rounded border border-rose-200 bg-rose-50 px-2.5 py-1 text-[10px] font-semibold text-rose-700 hover:bg-rose-100 transition-colors cursor-pointer">🛡️ Threat Level</button>
                    </div>

                    {/* AI Messages Chat Window */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4 font-sans text-xs bg-neutral-50/50">
                        {aiMessages.map((msg, idx) => (
                            <div key={idx} className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}>
                                <div className="flex items-center gap-1.5 mb-1">
                                    {msg.sender === "agent" && <span className="text-[10px]">🤖</span>}
                                    <span className="font-mono text-[9px] uppercase tracking-wider text-neutral-400">
                                        {msg.sender === "user" ? "You" : "GUDAKESA AI"}
                                    </span>
                                    {msg.llm_used && (
                                        <span className="font-mono text-[8px] text-neutral-300 border border-neutral-200 px-1 rounded">
                                            {msg.llm_used}
                                        </span>
                                    )}
                                </div>
                                <div className={`rounded-lg p-3 text-xs leading-relaxed max-w-[95%] border shadow-xs ${
                                    msg.sender === "user"
                                        ? "border-neutral-800 bg-neutral-900 text-white"
                                        : "border-neutral-200 bg-white text-neutral-800"
                                }`}>
                                    <p className="whitespace-pre-wrap">{msg.text}</p>
                                    {msg.graph_base64 && (
                                        <div className="mt-3 rounded overflow-hidden border border-neutral-200">
                                            <img
                                                src={`data:image/png;base64,${msg.graph_base64}`}
                                                alt={`${msg.graph_type || 'feature'} chart`}
                                                className="w-full h-auto"
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        {aiSending && (
                            <div className="flex flex-col items-start">
                                <span className="font-mono text-[9px] uppercase tracking-wider text-neutral-400 mb-1">🤖 GUDAKESA AI</span>
                                <div className="border border-neutral-200 bg-white rounded-lg px-4 py-3 shadow-xs">
                                    <div className="flex gap-1 items-center">
                                        <div className="h-1.5 w-1.5 rounded-full bg-neutral-400 animate-bounce" style={{animationDelay:'0ms'}} />
                                        <div className="h-1.5 w-1.5 rounded-full bg-neutral-400 animate-bounce" style={{animationDelay:'150ms'}} />
                                        <div className="h-1.5 w-1.5 rounded-full bg-neutral-400 animate-bounce" style={{animationDelay:'300ms'}} />
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* AI Input Box */}
                    <div className="border-t border-neutral-200 p-3 bg-white flex gap-2">
                        <input
                            type="text"
                            value={aiInput}
                            onChange={(e) => setAiInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && !aiSending && handleSendAiPrompt()}
                            placeholder="Ask about threats, features, patterns..."
                            disabled={aiSending}
                            className="flex-1 rounded border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs text-neutral-900 placeholder-neutral-400 focus:border-neutral-400 focus:bg-white focus:outline-none disabled:opacity-60"
                        />
                        <button
                            onClick={() => handleSendAiPrompt()}
                            disabled={aiSending || !aiInput.trim()}
                            className="rounded border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-neutral-800 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {aiSending ? <div className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-400 border-t-transparent" /> : "Send"}
                        </button>
                    </div>
                </aside>
            </div>
        </div>

        {/* ═══════════════════════════════════════════
             INVESTIGATION REPORT MODAL
           ═══════════════════════════════════════════ */}
        {showReport && reportData && (
            <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-sm overflow-y-auto p-4 py-8">
                <div className="w-full max-w-4xl bg-white rounded-2xl shadow-2xl overflow-hidden font-sans">

                    {/* Report Header */}
                    <div className="bg-neutral-900 text-white px-8 py-6">
                        <div className="flex items-start justify-between">
                            <div>
                                <div className="flex items-center gap-3 mb-2">
                                    <span className="text-2xl">🛡️</span>
                                    <div>
                                        <p className="text-[10px] font-mono uppercase tracking-widest text-neutral-400">GUDAKESA CTI Platform — Investigation Report</p>
                                        <h1 className="text-xl font-bold mt-0.5">{reportData.metadata?.page_name || "Dark Web Investigation"}</h1>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-3 mt-3">
                                    <span className="font-mono text-[10px] text-neutral-400">Report ID: <strong className="text-white">{reportData.metadata?.report_id}</strong></span>
                                    <span className="font-mono text-[10px] text-neutral-400">Generated: <strong className="text-white">{new Date(reportData.metadata?.generated_at).toLocaleString()}</strong></span>
                                </div>
                            </div>
                            <div className="flex flex-col items-end gap-2">
                                <button onClick={() => setShowReport(false)} className="text-neutral-400 hover:text-white text-xl cursor-pointer">✕</button>
                                <span className={`mt-2 px-3 py-1 rounded-full text-xs font-bold ${
                                    reportData.analysis?.threat_level === 'CRITICAL' ? 'bg-red-600 text-white' :
                                    reportData.analysis?.threat_level === 'HIGH' ? 'bg-orange-500 text-white' :
                                    reportData.analysis?.threat_level === 'MEDIUM' ? 'bg-yellow-400 text-neutral-900' :
                                    reportData.analysis?.threat_level === 'LOW' ? 'bg-green-500 text-white' :
                                    'bg-neutral-600 text-white'
                                }`}>{reportData.analysis?.threat_level || 'UNKNOWN'}</span>
                            </div>
                        </div>
                        <div className="mt-4 border-t border-neutral-700 pt-3">
                            <p className="text-[10px] font-mono text-neutral-500">{reportData.metadata?.classification}</p>
                        </div>
                    </div>

                    <div className="p-8 space-y-8 bg-neutral-50">

                        {/* Stats Row */}
                        <div className="grid grid-cols-3 gap-4">
                            {[
                                { label: "Total Indicators", value: reportData.metadata?.total_indicators, icon: "📍" },
                                { label: "High Confidence", value: reportData.statistics?.high_confidence_count, icon: "✅" },
                                { label: "Avg Confidence", value: `${((reportData.statistics?.avg_confidence || 0) * 100).toFixed(0)}%`, icon: "📊" },
                            ].map((s) => (
                                <div key={s.label} className="bg-white border border-neutral-200 rounded-xl p-4 text-center shadow-sm">
                                    <div className="text-2xl mb-1">{s.icon}</div>
                                    <div className="text-2xl font-bold text-neutral-900">{s.value ?? "—"}</div>
                                    <div className="text-[10px] font-mono uppercase text-neutral-500 mt-0.5">{s.label}</div>
                                </div>
                            ))}
                        </div>

                        {/* Executive Summary */}
                        <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
                            <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-3">Executive Summary</h2>
                            <p className="text-sm text-neutral-800 leading-relaxed">{reportData.analysis?.executive_summary}</p>
                            {reportData.analysis?.threat_level_rationale && (
                                <p className="mt-3 text-xs text-neutral-500 italic border-t border-neutral-100 pt-3">{reportData.analysis.threat_level_rationale}</p>
                            )}
                        </div>

                        {/* Key Findings */}
                        {reportData.analysis?.key_findings?.length > 0 && (
                            <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
                                <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-4">Key Findings</h2>
                                <ul className="space-y-2">
                                    {reportData.analysis.key_findings.map((f, i) => (
                                        <li key={i} className="flex items-start gap-3 text-sm text-neutral-800">
                                            <span className="mt-0.5 h-5 w-5 flex-shrink-0 rounded-full bg-neutral-900 text-white text-[10px] flex items-center justify-center font-bold">{i + 1}</span>
                                            <span className="leading-relaxed">{f}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Threat Actor Profile + IOC Analysis */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {reportData.analysis?.threat_actor_profile && (
                                <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-4">Threat Actor Profile</h2>
                                    <dl className="space-y-3">
                                        {[['Motivation', reportData.analysis.threat_actor_profile.likely_motivation],
                                          ['OPSEC', reportData.analysis.threat_actor_profile.operational_security],
                                          ['Sophistication', reportData.analysis.threat_actor_profile.estimated_sophistication]].map(([k,v]) => v && (
                                            <div key={k}>
                                                <dt className="text-[10px] font-mono uppercase text-neutral-400">{k}</dt>
                                                <dd className="text-xs text-neutral-800 mt-0.5">{v}</dd>
                                            </div>
                                        ))}
                                        {reportData.analysis.threat_actor_profile.indicators_of_attribution?.length > 0 && (
                                            <div>
                                                <dt className="text-[10px] font-mono uppercase text-neutral-400">Attribution Indicators</dt>
                                                <dd className="mt-1 flex flex-wrap gap-1">
                                                    {reportData.analysis.threat_actor_profile.indicators_of_attribution.map((a, i) => (
                                                        <span key={i} className="font-mono text-[9px] bg-neutral-100 border border-neutral-200 rounded px-1.5 py-0.5">{a}</span>
                                                    ))}
                                                </dd>
                                            </div>
                                        )}
                                    </dl>
                                </div>
                            )}
                            {reportData.analysis?.ioc_analysis && (
                                <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-4">High-Value IOCs</h2>
                                    <div className="space-y-1 mb-3">
                                        {(reportData.analysis.ioc_analysis.high_value || []).slice(0, 8).map((ioc, i) => (
                                            <div key={i} className="font-mono text-[10px] bg-neutral-50 border border-neutral-200 rounded px-2 py-1 text-neutral-800 break-all">{ioc}</div>
                                        ))}
                                    </div>
                                    {reportData.analysis.ioc_analysis.notes && (
                                        <p className="text-[10px] text-neutral-500 italic">{reportData.analysis.ioc_analysis.notes}</p>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Indicators Table */}
                        {reportData.indicators?.length > 0 && (
                            <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden shadow-sm">
                                <div className="px-6 py-4 border-b border-neutral-100">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-500">Extracted Indicators ({reportData.indicators.length})</h2>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-xs">
                                        <thead>
                                            <tr className="bg-neutral-50 border-b border-neutral-100">
                                                {['Type','Value','Confidence','Context'].map(h => (
                                                    <th key={h} className="px-4 py-2 text-left font-mono text-[10px] uppercase text-neutral-400">{h}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {reportData.indicators.slice(0, 30).map((ind, i) => (
                                                <tr key={i} className="border-b border-neutral-50 hover:bg-neutral-50 transition-colors">
                                                    <td className="px-4 py-2">
                                                        <span className="rounded-full border border-neutral-200 bg-neutral-100 px-2 py-0.5 font-mono text-[9px] text-neutral-700">{ind.feature_type}</span>
                                                    </td>
                                                    <td className="px-4 py-2 font-mono text-[10px] text-neutral-900 max-w-[200px] truncate">{ind.feature_value}</td>
                                                    <td className="px-4 py-2">
                                                        <div className="flex items-center gap-1.5">
                                                            <div className="h-1.5 w-16 rounded-full bg-neutral-100 overflow-hidden">
                                                                <div className="h-full rounded-full bg-neutral-900" style={{width:`${((ind.confidence_score||0)*100)}%`}} />
                                                            </div>
                                                            <span className="font-mono text-[9px] text-neutral-500">{((ind.confidence_score||0)*100).toFixed(0)}%</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-2 text-neutral-500 max-w-[250px] truncate text-[10px]">{ind.context}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {/* Recommendations + Investigative Leads */}
                        {reportData.analysis?.attack_vectors?.length > 0 && (
                            <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
                                <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-4">Attack Vectors</h2>
                                <ul className="space-y-2">
                                    {reportData.analysis.attack_vectors.map((v, i) => (
                                        <li key={i} className="flex items-start gap-2 text-sm text-neutral-800">
                                            <span className="mt-0.5 text-rose-500">▸</span><span>{v}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {reportData.analysis?.recommendations?.length > 0 && (
                                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-6 shadow-sm">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-emerald-700 mb-4">Recommendations</h2>
                                    <ul className="space-y-2">
                                        {reportData.analysis.recommendations.map((r, i) => (
                                            <li key={i} className="flex items-start gap-2 text-xs text-emerald-900">
                                                <span className="mt-0.5 text-emerald-500">✓</span><span>{r}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {reportData.analysis?.investigative_leads?.length > 0 && (
                                <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 shadow-sm">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-amber-700 mb-4">Investigative Leads</h2>
                                    <ul className="space-y-2">
                                        {reportData.analysis.investigative_leads.map((l, i) => (
                                            <li key={i} className="flex items-start gap-2 text-xs text-amber-900">
                                                <span className="mt-0.5 text-amber-500">→</span><span>{l}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between border-t border-neutral-200 pt-4">
                            <p className="font-mono text-[10px] text-neutral-400">{reportData.metadata?.classification}</p>
                            <button
                                onClick={() => setShowReport(false)}
                                className="rounded-lg border border-neutral-900 bg-neutral-900 px-5 py-2 text-xs font-bold text-white hover:bg-neutral-800 transition-colors cursor-pointer"
                            >
                                Close Report
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        )}
        </>
    );
};

export default Playground;