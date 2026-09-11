import React, {
    createContext,
    useContext,
    useState,
    useEffect,
} from "react";

import api from "../api/axiosInstance";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(() => {
        const savedUser = localStorage.getItem("user");

        try {
            return savedUser ? JSON.parse(savedUser) : null;
        } catch {
            localStorage.removeItem("user");
            return null;
        }
    });

    const [loading, setLoading] = useState(true);

    // --------------------------------
    // FETCH CURRENT USER
    // --------------------------------
    const fetchUserProfile = async () => {
        try {
            const response = await api.get("/user/");

            setUser(response.data);

            localStorage.setItem(
                "user",
                JSON.stringify(response.data)
            );

        } catch (error) {
            console.error(
                "Failed to fetch user:",
                error
            );

            // Token is no longer valid
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
            localStorage.removeItem("user");

            setUser(null);

        } finally {
            setLoading(false);
        }
    };

    // --------------------------------
    // INITIAL AUTH CHECK
    // --------------------------------
    useEffect(() => {
        const accessToken =
            localStorage.getItem("access_token");

        if (accessToken) {
            fetchUserProfile();
        } else {
            setLoading(false);
        }
    }, []);

    // --------------------------------
    // LOGIN
    // --------------------------------
    const login = async (username, password) => {
        const response = await api.post("/login/", {
            username,
            password,
        });

        const {
            access,
            refresh,
        } = response.data;

        localStorage.setItem(
            "access_token",
            access
        );

        localStorage.setItem(
            "refresh_token",
            refresh
        );

        // Get current user
        const userResponse =
            await api.get("/user/");

        setUser(userResponse.data);

        localStorage.setItem(
            "user",
            JSON.stringify(userResponse.data)
        );

        return userResponse.data;
    };

    // --------------------------------
    // REGISTER
    // --------------------------------
    const register = async (userData) => {
        const response =
            await api.post(
                "/register/",
                userData
            );

        return response.data;
    };

    // --------------------------------
    // LOGOUT
    // --------------------------------
    const logout = async () => {
        const refreshToken =
            localStorage.getItem("refresh_token");

        if (refreshToken) {
            try {
                await api.post("/logout/", {
                    refresh: refreshToken,
                });
            } catch (error) {
                console.warn(
                    "Logout backend call failed."
                );
            }
        }

        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("user");

        setUser(null);
    };

    // --------------------------------
    // AUTH STATE
    // --------------------------------
    const value = {
        user,
        loading,

        isAuthenticated:
            !!user ||
            !!localStorage.getItem(
                "access_token"
            ),

        login,
        register,
        logout,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

// --------------------------------
// useAuth Hook
// --------------------------------
export const useAuth = () => {
    const context = useContext(AuthContext);

    if (!context) {
        throw new Error(
            "useAuth must be used within an AuthProvider"
        );
    }

    return context;
};