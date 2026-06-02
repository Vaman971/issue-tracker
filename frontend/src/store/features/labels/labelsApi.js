import { api } from "@/store/api";

export const labelsApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getProjectLabels: builder.query({
            query: (projectId) => `/projects/${projectId}/labels/`,
            providesTags: (result, error, projectId) => [
                { type: "Label", id: projectId },
            ],
        }),

        createLabel: builder.mutation({
            query: ({ projectId, data }) => ({
                url: `/projects/${projectId}/labels/`,
                method: "POST",
                body: data,
            }),
            invalidatesTags: (result, error, { projectId }) => [
                { type: "Label", id: projectId },
            ],
        }),

        deleteLabel: builder.mutation({
            query: ({ projectId, labelId }) => ({
                url: `/projects/${projectId}/labels/${labelId}`,
                method: "DELETE",
            }),
            invalidatesTags: (result, error, { projectId }) => [
                { type: "Label", id: projectId },
            ],
        }),

        addIssueLabel: builder.mutation({
            query: ({ issueId, labelId }) => ({
                url: `/issues/${issueId}/labels/${labelId}`,
                method: "POST",
            }),
            invalidatesTags: (result, error, { issueId }) => [
                { type: "Issue", id: issueId },
                { type: "Activity", id: issueId },
            ],
        }),

        removeIssueLabel: builder.mutation({
            query: ({ issueId, labelId }) => ({
                url: `/issues/${issueId}/labels/${labelId}`,
                method: "DELETE",
            }),
            invalidatesTags: (result, error, { issueId }) => [
                { type: "Issue", id: issueId },
                { type: "Activity", id: issueId },
            ],
        }),
    }),
});

export const {
    useGetProjectLabelsQuery,
    useCreateLabelMutation,
    useDeleteLabelMutation,
    useAddIssueLabelMutation,
    useRemoveIssueLabelMutation,
} = labelsApi;
