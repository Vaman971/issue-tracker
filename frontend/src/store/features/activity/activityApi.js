import { api } from "@/store/api";

export const activityApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getIssueActivity: builder.query({
            query: ({ issueId, skip = 0, limit = 50 } = {}) =>
                `/issues/${issueId}/activity/?skip=${skip}&limit=${limit}`,
            providesTags: (result, error, { issueId }) => [
                { type: "Activity", id: issueId },
            ],
        }),
    }),
});

export const { useGetIssueActivityQuery } = activityApi;
