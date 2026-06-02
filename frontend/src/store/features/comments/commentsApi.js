import { api } from "@/store/api";

export const commentsApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getComments: builder.query({
            query: (issueId) => `/issues/${issueId}/comments/`,
            providesTags: (result, error, issueId) => [
                { type: "Comment", id: issueId },
            ],
        }),

        createComment: builder.mutation({
            query: ({ issueId, data }) => ({
                url: `/issues/${issueId}/comments/`,
                method: "POST",
                body: data,
            }),
            invalidatesTags: (result, error, { issueId }) => [
                { type: "Comment", id: issueId },
                { type: "Activity", id: issueId },
            ],
        }),

        updateComment: builder.mutation({
            query: ({ issueId, commentId, data }) => ({
                url: `/issues/${issueId}/comments/${commentId}`,
                method: "PATCH",
                body: data,
            }),
            invalidatesTags: (result, error, { issueId }) => [
                { type: "Comment", id: issueId },
            ],
        }),

        deleteComment: builder.mutation({
            query: ({ issueId, commentId }) => ({
                url: `/issues/${issueId}/comments/${commentId}`,
                method: "DELETE",
            }),
            invalidatesTags: (result, error, { issueId }) => [
                { type: "Comment", id: issueId },
                { type: "Activity", id: issueId },
            ],
        }),
    }),
});

export const {
    useGetCommentsQuery,
    useCreateCommentMutation,
    useUpdateCommentMutation,
    useDeleteCommentMutation,
} = commentsApi;
