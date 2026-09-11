import React from "react";
import { Routes, Route } from "react-router-dom";

import Home from "../pages/Home";
import Project from "../pages/Project";
import Login from "../pages/auth/Login";
import Register from "../pages/auth/Register";
import NotFound from "../pages/NotFound";

import ProtectedRoute from "./ProtectedRoute";

const AppRoutes = () => {
    return (
        <Routes>
            {/* Public routes */}
            <Route
                path="/login"
                element={<Login />}
            />

            <Route
                path="/register"
                element={<Register />}
            />

            {/* Home */}
            <Route
                path="/"
                element={
                    <ProtectedRoute>
                        <Home />
                    </ProtectedRoute>
                }
            />

            {/* Project */}
            <Route
                path="/project/:projectId"
                element={
                    <ProtectedRoute>
                        <Project />
                    </ProtectedRoute>
                }
            />

            {/* 404 */}
            <Route
                path="*"
                element={<NotFound />}
            />
        </Routes>
    );
};

export default AppRoutes;