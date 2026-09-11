import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();
    const location = useLocation();

    if (loading) {
        return (
            <div className="min-h-screen bg-white text-black flex items-center justify-center px-6">
                <div className="border-2 border-black bg-white px-10 py-8 shadow-[8px_8px_0_0_#000]">
                    
                    {/* Meta strip */}
                    <div className="mb-5 flex items-center gap-3 border-b border-neutral-300 pb-4">
                        <span className="h-1.5 w-1.5 bg-black" />

                        <span className="text-[10px] font-bold uppercase tracking-[0.35em] text-neutral-500">
                            Session
                        </span>
                    </div>

                    {/* Big display text */}
                    <h1 className="text-4xl font-black leading-[0.9] tracking-[-0.04em] sm:text-5xl">
                        VERIFYING
                    </h1>

                    {/* Animated dots */}
                    <div className="mt-5 flex items-center gap-2">
                        <span className="h-2 w-2 animate-pulse bg-black [animation-delay:0ms]" />
                        <span className="h-2 w-2 animate-pulse bg-black [animation-delay:150ms]" />
                        <span className="h-2 w-2 animate-pulse bg-black [animation-delay:300ms]" />

                        <span className="ml-3 font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-neutral-500">
                            Please wait
                        </span>
                    </div>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return (
            <Navigate
                to="/login"
                state={{ from: location }}
                replace
            />
        );
    }

    return children;
};

export default ProtectedRoute;