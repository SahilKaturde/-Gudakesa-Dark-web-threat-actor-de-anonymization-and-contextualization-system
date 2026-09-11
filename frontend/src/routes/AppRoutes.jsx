import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import Home from "../pages/Home";
import Project from "../pages/Project";
import Login from "../pages/Login";
import Register from "../pages/Register";

import Playground from "../pages/Playground";

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

            {/* Playground */}
            <Route
                path="/playground/:domainId"
                element={
                    <ProtectedRoute>
                        <Playground />
                    </ProtectedRoute>
                }
            />

            {/* Fallback */}
            <Route
                path="*"
                element={<Navigate to="/" replace />}
            />
        </Routes>
    );
};

export default AppRoutes;