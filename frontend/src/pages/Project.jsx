import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getProjects } from "../api/projects";
import { useAuth } from "../context/AuthContext";

const Project = () => {
    const { projectId } = useParams();
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const [project, setProject] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const loadProject = async () => {
            try {
                setLoading(true);
                setError("");

                // We already have the projects API.
                // Find the project belonging to the authenticated user.
                const projects = await getProjects();

                const foundProject = projects.find(
                    (item) => item.project_id === projectId
                );

                if (!foundProject) {
                    setError("Project not found.");
                    return;
                }

                setProject(foundProject);
            } catch (err) {
                console.error(err);
                setError("Unable to load this project.");
            } finally {
                setLoading(false);
            }
        };

        loadProject();
    }, [projectId]);

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

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

    const createdDate = new Date(project.created_at).toLocaleDateString(
        undefined,
        {
            year: "numeric",
            month: "long",
            day: "numeric",
        }
    );

    const createdTime = new Date(project.created_at).toLocaleTimeString(
        undefined,
        {
            hour: "2-digit",
            minute: "2-digit",
        }
    );

    return (
        <div className="min-h-screen bg-white text-black">
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
                        {/* PROJECT ID */}
                        <div className="border-2 border-black bg-white p-5 shadow-[4px_4px_0_0_#000]">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                                Project ID
                            </p>

                            <p className="mt-4 break-all font-mono text-xs font-medium leading-relaxed">
                                {project.project_id}
                            </p>
                        </div>

                        {/* CREATED DATE */}
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

                        {/* OWNER */}
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

                {/* INVESTIGATION AREA */}
                <section className="mt-12">
                    <div className="mb-6 flex items-end justify-between">
                        <div>
                            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-neutral-400">
                                Investigation
                            </p>

                            <h2 className="mt-2 text-xl font-bold">
                                Investigation Workspace
                            </h2>
                        </div>
                    </div>

                    <div className="border-2 border-dashed border-neutral-300 px-6 py-20 text-center">
                        <div className="mx-auto flex h-10 w-10 items-center justify-center border-2 border-black bg-white text-sm font-bold shadow-[2px_2px_0_0_#000]">
                            +
                        </div>

                        <h3 className="mt-5 text-base font-bold">
                            No investigation data yet
                        </h3>

                        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-neutral-500">
                            This workspace will contain the investigation,
                            intelligence, entities, evidence and analysis
                            associated with this project.
                        </p>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Project;