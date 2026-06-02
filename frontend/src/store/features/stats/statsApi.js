import { api } from "@/store/api";

export const statsApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getProjectStats: builder.query({
            query: (projectId) => `/projects/${projectId}/stats`,
            providesTags: (result, error, id) => [{ type: "Stats", id }],
        }),

        getAdminStats: builder.query({
            query: () => "/admin/stats",
            providesTags: [{ type: "Stats", id: "admin" }],
        }),
    }),
});

export const { useGetProjectStatsQuery, useGetAdminStatsQuery } = statsApi;
