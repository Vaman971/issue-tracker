import { api } from "@/store/api";

export const IssuesApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getIssues: builder.query({
            query: ({ skip = 0, limit = 20, q } = {}) => {
                const params = new URLSearchParams({ skip, limit });
                if (q) params.set("q", q);
                return `/issues/?${params}`;
            },
            providesTags: ["Issue"],
        }),

        getIssue: builder.query({
            query: (issueId) => `/issues/${issueId}`,
            providesTags: (_result, _error, id) => [{ type: "Issue", id }],
        }),

        createIssue: builder.mutation({
            query: (issueData) => ({
                url: `/issues/`,
                method: "POST",
                body: issueData,
            }),
            invalidatesTags: (result) => [
                "Issue",
                ...(result?.project_id ? [{ type: "Stats", id: result.project_id }] : []),
            ],
        }),

        updateIssue: builder.mutation({
            query: ({ issueId, data }) => ({
                url: `/issues/${issueId}`,
                method: "PATCH",
                body: data,
            }),
            async onQueryStarted(
                { issueId, data, queryArgs = { skip: 0, limit: 20 } },
                { dispatch, queryFulfilled }
            ) {
                const patchResult = dispatch(
                    api.util.updateQueryData("getIssues", queryArgs, (draft) => {
                        const issue = draft.find((item) => item.id === issueId);
                        if (issue) {
                            Object.assign(issue, data);
                        }
                    })
                );

                try {
                    await queryFulfilled;
                } catch {
                    patchResult.undo();
                }
            },
            invalidatesTags: (result, _error, { issueId }) => [
                "Issue",
                { type: "Issue", id: issueId },
                ...(result?.project_id ? [{ type: "Stats", id: result.project_id }] : []),
            ],
        }),

        deleteIssue: builder.mutation({
            query: ({ issueId }) => ({
                url: `/issues/${issueId}`,
                method: "DELETE",
            }),
            invalidatesTags: (_result, _error, { projectId }) => [
                "Issue",
                ...(projectId ? [{ type: "Stats", id: projectId }] : []),
            ],
        }),
    }),
});

export const {
    useGetIssuesQuery,
    useGetIssueQuery,
    useCreateIssueMutation,
    useUpdateIssueMutation,
    useDeleteIssueMutation,
} = IssuesApi;
