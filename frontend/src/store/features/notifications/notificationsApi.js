import { api } from "@/store/api";

export const notificationsApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getNotifications: builder.query({
            query: ({ unreadOnly = false } = {}) =>
                `/notifications/${unreadOnly ? "?unread_only=true" : ""}`,
            providesTags: ["Notification"],
        }),

        getNotificationCount: builder.query({
            query: () => "/notifications/count",
            providesTags: ["Notification"],
        }),

        markNotificationRead: builder.mutation({
            query: (notificationId) => ({
                url: `/notifications/${notificationId}/read`,
                method: "PATCH",
            }),
            invalidatesTags: ["Notification"],
        }),

        markAllNotificationsRead: builder.mutation({
            query: () => ({
                url: "/notifications/read-all",
                method: "PATCH",
            }),
            invalidatesTags: ["Notification"],
        }),

        deleteNotification: builder.mutation({
            query: (notificationId) => ({
                url: `/notifications/${notificationId}`,
                method: "DELETE",
            }),
            invalidatesTags: ["Notification"],
        }),
    }),
});

export const {
    useGetNotificationsQuery,
    useGetNotificationCountQuery,
    useMarkNotificationReadMutation,
    useMarkAllNotificationsReadMutation,
    useDeleteNotificationMutation,
} = notificationsApi;
