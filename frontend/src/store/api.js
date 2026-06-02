"use client"

import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { logout, setCredentials } from "./features/auth/authSlice";

const API_BASE_URL = "/api";

const getStoredAccessToken = () => {
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

const baseQueryWithRefresh = async (args, api, extraOptions) => {
    let result = await rawBaseQuery(args, api, extraOptions);

    if (result.error && result.error.status === 401) {
        const refreshToken = localStorage.getItem("refreshToken");

        if (!refreshToken) {
            api.dispatch(logout());
            return result;
        }

        const refreshResult = await rawBaseQuery(
            {
                url: "/auth/refresh",
                method: "POST",
                body: { refresh_token: refreshToken },
            },
            api,
            extraOptions
        );

        if (refreshResult.data) {
            api.dispatch(
                setCredentials({
                    accessToken: refreshResult.data.access_token,
                    refreshToken: refreshResult.data.refresh_token,
                })
            );

            result = await rawBaseQuery(args, api, extraOptions);
        } else {
            api.dispatch(logout());
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
    ],
    endpoints: () => ({}),
});
