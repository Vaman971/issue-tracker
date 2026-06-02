import { api } from "@/store/api";

export const attachmentsApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getAttachments: builder.query({
            query: (issueId) => `/issues/${issueId}/attachments/`,
            providesTags: (result, error, issueId) => [
                { type: "Attachment", id: issueId },
            ],
        }),

        uploadAttachment: builder.mutation({
            query: ({ issueId, formData }) => ({
                url: `/issues/${issueId}/attachments/`,
                method: "POST",
                body: formData,
            }),
            invalidatesTags: (result, error, { issueId }) => [
                { type: "Attachment", id: issueId },
            ],
        }),

        getAttachmentUrl: builder.query({
            query: ({ issueId, attachmentId }) =>
                `/issues/${issueId}/attachments/${attachmentId}/url`,
        }),

        deleteAttachment: builder.mutation({
            query: ({ issueId, attachmentId }) => ({
                url: `/issues/${issueId}/attachments/${attachmentId}`,
                method: "DELETE",
            }),
            invalidatesTags: (result, error, { issueId }) => [
                { type: "Attachment", id: issueId },
            ],
        }),
    }),
});

export const {
    useGetAttachmentsQuery,
    useUploadAttachmentMutation,
    useGetAttachmentUrlQuery,
    useDeleteAttachmentMutation,
} = attachmentsApi;
