import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import {
    getProjects,
    createProject,
    updateProject,
    deleteProject,
} from "../api/projects";

const Home = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const [showCreate, setShowCreate] = useState(false);
    const [projectTitle, setProjectTitle] = useState("");
    const [creating, setCreating] = useState(false);

    const [editingProjectId, setEditingProjectId] = useState(null);
    const [editingTitle, setEditingTitle] = useState("");
    const [saving, setSaving] = useState(false);

    const [deletingProjectId, setDeletingProjectId] = useState(null);

    // -----------------------------
    // LOAD PROJECTS
    // -----------------------------
    const loadProjects = async () => {
        try {
            setLoading(true);
            setError("");

            const data = await getProjects();
            setProjects(data);
        } catch (err) {
            console.error(err);
            setError("Unable to load your projects.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadProjects();
    }, []);

    // -----------------------------
    // CREATE PROJECT
    // -----------------------------
    const handleCreateProject = async (event) => {
        event.preventDefault();

        const title = projectTitle.trim();

        if (!title) return;

        try {
            setCreating(true);
            setError("");

            const project = await createProject(title);

            setProjects((current) => [project, ...current]);

            setProjectTitle("");
            setShowCreate(false);
        } catch (err) {
            console.error(err);
            setError("Unable to create the project.");
        } finally {
            setCreating(false);
        }
    };

    // -----------------------------
    // OPEN PROJECT
    // -----------------------------
    const openProject = (projectId) => {
        navigate(`/project/${projectId}`);
    };

    // -----------------------------
    // RENAME PROJECT
    // -----------------------------
    const startEditing = (project) => {
        setEditingProjectId(project.project_id);
        setEditingTitle(project.project_title);
    };

    const cancelEditing = () => {
        setEditingProjectId(null);
        setEditingTitle("");
    };

    const handleUpdateProject = async (projectId) => {
        const title = editingTitle.trim();

        if (!title) return;

        try {
            setSaving(true);
            setError("");

            const updatedProject = await updateProject(projectId, title);

            setProjects((current) =>
                current.map((project) =>
                    project.project_id === projectId
                        ? updatedProject
                        : project
                )
            );

            cancelEditing();
        } catch (err) {
            console.error(err);
            setError("Unable to update the project.");
        } finally {
            setSaving(false);
        }
    };

    // -----------------------------
    // DELETE PROJECT
    // -----------------------------
    const handleDeleteProject = async (projectId) => {
        const confirmed = window.confirm(
            "Are you sure you want to delete this project?"
        );

        if (!confirmed) return;

        try {
            setDeletingProjectId(projectId);
            setError("");

            await deleteProject(projectId);

            setProjects((current) =>
                current.filter(
                    (project) => project.project_id !== projectId
                )
            );
        } catch (err) {
            console.error(err);
            setError("Unable to delete the project.");
        } finally {
            setDeletingProjectId(null);
        }
    };

    // -----------------------------
    // LOGOUT
    // -----------------------------
    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

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
            <main className="mx-auto max-w-5xl px-6 py-16">

                {/* PAGE HEADER */}
                <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">

                    <div>

                        <div className="mb-4 flex items-center gap-2">
                            <span className="h-2 w-2 bg-black" />

                            <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-neutral-500">
                                Workspace
                            </span>
                        </div>

                        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
                            Projects
                        </h1>

                        <p className="mt-4 max-w-md text-sm leading-relaxed text-neutral-500">
                            Your investigation workspace.

                            {!loading && (
                                <>
                                    {" "}

                                    <span className="font-semibold text-black">
                                        {projects.length}
                                    </span>{" "}

                                    {projects.length === 1
                                        ? "project"
                                        : "projects"}{" "}

                                    active.
                                </>
                            )}
                        </p>

                    </div>

                    <button
                        onClick={() => setShowCreate(true)}
                        className="inline-flex items-center gap-2 self-start border-2 border-black bg-black px-5 py-3 text-xs font-bold uppercase tracking-wider text-white shadow-[4px_4px_0_0_#000] transition-all hover:bg-neutral-800 active:translate-x-[4px] active:translate-y-[4px] active:shadow-none cursor-pointer sm:self-end"
                    >
                        <span className="text-base leading-none">
                            +
                        </span>

                        New Project
                    </button>

                </div>

                {/* ERROR */}
                {error && (
                    <div className="mt-10 flex items-start gap-3 border-2 border-black bg-white px-4 py-3">

                        <span className="mt-1.5 h-2 w-2 shrink-0 bg-black" />

                        <p className="text-sm font-medium text-black">
                            {error}
                        </p>

                    </div>
                )}

                {/* CREATE FORM */}
                {showCreate && (
                    <div className="mt-10 border-2 border-black bg-white p-6">

                        <div className="mb-5 flex items-center justify-between">

                            <div>
                                <h2 className="text-sm font-bold text-black">
                                    New project
                                </h2>

                                <p className="mt-1 text-xs text-neutral-500">
                                    Give your project a name to get started.
                                </p>
                            </div>

                            <button
                                onClick={() => {
                                    setShowCreate(false);
                                    setProjectTitle("");
                                }}
                                className="text-lg leading-none text-neutral-400 transition-colors hover:text-black cursor-pointer"
                                aria-label="Close"
                            >
                                ×
                            </button>

                        </div>

                        <form
                            onSubmit={handleCreateProject}
                            className="flex flex-col gap-3 sm:flex-row"
                        >

                            <input
                                type="text"
                                value={projectTitle}
                                onChange={(event) =>
                                    setProjectTitle(event.target.value)
                                }
                                placeholder="Project title"
                                autoFocus
                                maxLength={255}
                                className="flex-1 border-2 border-black bg-white px-4 py-3 text-sm font-medium text-black placeholder-neutral-400 outline-none transition-shadow focus:shadow-[4px_4px_0_0_#000]"
                            />

                            <div className="flex gap-3">

                                <button
                                    type="submit"
                                    disabled={
                                        creating ||
                                        !projectTitle.trim()
                                    }
                                    className="border-2 border-black bg-black px-5 py-3 text-xs font-bold uppercase tracking-wider text-white shadow-[3px_3px_0_0_#000] transition-all hover:bg-neutral-800 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
                                >
                                    {creating
                                        ? "Creating..."
                                        : "Create"}
                                </button>

                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowCreate(false);
                                        setProjectTitle("");
                                    }}
                                    className="border-2 border-black bg-white px-5 py-3 text-xs font-bold uppercase tracking-wider text-black transition-colors hover:bg-neutral-100 cursor-pointer"
                                >
                                    Cancel
                                </button>

                            </div>
                        </form>
                    </div>
                )}

                {/* PROJECTS */}
                <section className="mt-12">

                    {loading ? (

                        /* LOADING */
                        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">

                            {[1, 2, 3].map((item) => (
                                <div
                                    key={item}
                                    className="h-48 animate-pulse border-2 border-neutral-200 bg-neutral-50"
                                />
                            ))}

                        </div>

                    ) : projects.length === 0 ? (

                        /* EMPTY STATE */
                        <div className="border-2 border-dashed border-neutral-300 px-6 py-20 text-center">

                            <div className="mx-auto flex h-10 w-10 items-center justify-center border-2 border-black bg-white text-lg font-bold text-black shadow-[2px_2px_0_0_#000]">
                                +
                            </div>

                            <h2 className="mt-5 text-base font-bold text-black">
                                No projects yet
                            </h2>

                            <p className="mx-auto mt-2 max-w-sm text-sm text-neutral-500">
                                Create your first project to start organizing
                                your investigations.
                            </p>

                            <button
                                onClick={() => setShowCreate(true)}
                                className="mt-6 border-2 border-black bg-black px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-white shadow-[3px_3px_0_0_#000] transition-all hover:bg-neutral-800 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none cursor-pointer"
                            >
                                Create Project
                            </button>

                        </div>

                    ) : (

                        /* PROJECT GRID */
                        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">

                            {projects.map((project, index) => (

                                <div
                                    key={project.project_id}
                                    onClick={() =>
                                        openProject(project.project_id)
                                    }
                                    className="group relative flex cursor-pointer flex-col border-2 border-black bg-white p-5 transition-all hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-[6px_6px_0_0_#000]"
                                >

                                    {editingProjectId ===
                                    project.project_id ? (

                                        /* RENAME MODE */
                                        <div
                                            className="flex-1"
                                            onClick={(event) =>
                                                event.stopPropagation()
                                            }
                                        >

                                            <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">
                                                Rename
                                            </p>

                                            <input
                                                type="text"
                                                value={editingTitle}
                                                onChange={(event) =>
                                                    setEditingTitle(
                                                        event.target.value
                                                    )
                                                }
                                                maxLength={255}
                                                autoFocus
                                                onKeyDown={(event) => {
                                                    if (
                                                        event.key ===
                                                        "Enter"
                                                    ) {
                                                        handleUpdateProject(
                                                            project.project_id
                                                        );
                                                    }

                                                    if (
                                                        event.key ===
                                                        "Escape"
                                                    ) {
                                                        cancelEditing();
                                                    }
                                                }}
                                                className="w-full border-2 border-black bg-white px-3 py-2 text-sm font-medium text-black outline-none transition-shadow focus:shadow-[3px_3px_0_0_#000]"
                                            />

                                            <div className="mt-4 flex gap-2">

                                                <button
                                                    onClick={() =>
                                                        handleUpdateProject(
                                                            project.project_id
                                                        )
                                                    }
                                                    disabled={
                                                        saving ||
                                                        !editingTitle.trim()
                                                    }
                                                    className="border-2 border-black bg-black px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-[2px_2px_0_0_#000] transition-all hover:bg-neutral-800 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none disabled:opacity-40 cursor-pointer"
                                                >
                                                    {saving
                                                        ? "Saving..."
                                                        : "Save"}
                                                </button>

                                                <button
                                                    onClick={
                                                        cancelEditing
                                                    }
                                                    className="border-2 border-black bg-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-black transition-colors hover:bg-neutral-100 cursor-pointer"
                                                >
                                                    Cancel
                                                </button>

                                            </div>
                                        </div>

                                    ) : (

                                        /* PROJECT CARD */
                                        <>
                                            <span className="absolute right-4 top-4 font-mono text-[10px] font-bold text-neutral-300">
                                                {String(index + 1).padStart(
                                                    2,
                                                    "0"
                                                )}
                                            </span>

                                            <div className="flex-1">

                                                <h2 className="pr-8 text-base font-bold leading-snug text-black">
                                                    {project.project_title}
                                                </h2>

                                                <p className="mt-2 font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-400">
                                                    {new Date(
                                                        project.created_at
                                                    ).toLocaleDateString(
                                                        undefined,
                                                        {
                                                            year: "numeric",
                                                            month: "short",
                                                            day: "numeric",
                                                        }
                                                    )}
                                                </p>

                                                <p className="mt-3 truncate font-mono text-[9px] text-neutral-300">
                                                    {project.project_id}
                                                </p>

                                            </div>

                                            {/* CARD ACTIONS */}
                                            <div
                                                className="mt-6 flex items-center justify-between border-t-2 border-neutral-100 pt-4"
                                                onClick={(event) =>
                                                    event.stopPropagation()
                                                }
                                            >

                                                <button
                                                    onClick={() =>
                                                        startEditing(project)
                                                    }
                                                    className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 transition-colors hover:text-black cursor-pointer"
                                                >
                                                    Rename
                                                </button>

                                                <button
                                                    onClick={() =>
                                                        handleDeleteProject(
                                                            project.project_id
                                                        )
                                                    }
                                                    disabled={
                                                        deletingProjectId ===
                                                        project.project_id
                                                    }
                                                    className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 transition-colors hover:text-black disabled:opacity-40 cursor-pointer"
                                                >
                                                    {deletingProjectId ===
                                                    project.project_id
                                                        ? "Deleting..."
                                                        : "Delete"}
                                                </button>

                                            </div>
                                        </>
                                    )}

                                </div>
                            ))}

                        </div>
                    )}

                </section>
            </main>
        </div>
    );
};

export default Home;