"use client"

import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { logout, setCredentials } from "./features/auth/authSlice";

const API_BASE_URL = "/api";

export const getStoredAccessToken = () => {
    const accessToken = localStorage.getItem("accessToken") || localStorage.getItem("access_token");

    if (accessToken === "null" || accessToken === "undefined") {
        return null;
    }

    return accessToken;
};

const rawBaseQuery = fetchBaseQuery({
    baseUrl: API_BASE_URL,

    prepareHeaders: (headers) => {
        const accessToken = getStoredAccessToken();

        if (accessToken) {
            headers.set("Authorization", `Bearer ${accessToken}`);
        }

        return headers;
    },
});

/**
 * Exchange the refresh token for a new access token.
 *
 * Pulled out of the base query because the RAG chat endpoint streams, so it
 * has to bypass fetchBaseQuery entirely and would otherwise need its own copy
 * of this. One implementation means one place where the token keys, the
 * logout-on-failure rule and the request shape are decided.
 *
 * Returns whether the session is usable afterwards.
 */
export const refreshAccessToken = async (dispatch) => {
    const refreshToken = localStorage.getItem("refreshToken");

    if (!refreshToken) {
        dispatch(logout());
        return false;
    }

    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
        dispatch(logout());
        return false;
    }

    const data = await response.json();

    dispatch(
        setCredentials({
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
        })
    );

    return true;
};

const baseQueryWithRefresh = async (args, api, extraOptions) => {
    let result = await rawBaseQuery(args, api, extraOptions);

    if (result.error && result.error.status === 401) {
        if (await refreshAccessToken(api.dispatch)) {
            result = await rawBaseQuery(args, api, extraOptions);
        }
    }

    return result;
};

export const api = createApi({
    reducerPath: "api",
    baseQuery: baseQueryWithRefresh,
    tagTypes: [
        "Project",
        "Issue",
        "User",
        "Comment",
        "Attachment",
        "Label",
        "Notification",
        "Activity",
        "Stats",
        "Member",
        "Conversation",
        "ConversationMessage",
    ],
    endpoints: () => ({}),
});
