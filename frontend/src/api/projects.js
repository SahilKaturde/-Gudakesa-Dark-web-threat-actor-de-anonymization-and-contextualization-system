import api from "./axiosInstance";

export const getProjects = async () => {
    const response = await api.get("/projects/");
    return response.data;
};

export const createProject = async (projectTitle) => {
    const response = await api.post("/projects/", {
        project_title: projectTitle,
    });

    return response.data;
};

export const updateProject = async (projectId, projectTitle) => {
    const response = await api.patch(`/projects/${projectId}/`, {
        project_title: projectTitle,
    });

    return response.data;
};

export const deleteProject = async (projectId) => {
    await api.delete(`/projects/${projectId}/`);
};