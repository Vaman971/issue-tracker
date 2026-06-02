import { api } from "@/store/api";

export const usersApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getUsers: builder.query({
            query: ({ skip = 0, limit = 15, q } = {}) => {
                const params = new URLSearchParams({ skip, limit });
                if (q) params.set("q", q);
                return `/users/?${params}`;
            },
            providesTags: ["User"],
        }),

        updateUserRole: builder.mutation({
            query: ({ userId, role }) => ({
                url: `/users/${userId}/role`,
                method: "PATCH",
                body: { role },
            }),
            invalidatesTags: ["User"],
        }),

        activateUser: builder.mutation({
            query: (userId) => ({
                url: `/users/${userId}/activate`,
                method: "PATCH",
            }),
            invalidatesTags: ["User"],
        }),

        deactivateUser: builder.mutation({
            query: (userId) => ({
                url: `/users/${userId}/deactivate`,
                method: "PATCH",
            }),
            invalidatesTags: ["User"],
        }),

        updateProfile: builder.mutation({
            query: (data) => ({
                url: `/users/me`,
                method: "PATCH",
                body: data,
            }),
            invalidatesTags: ["User"],
        }),

        uploadAvatar: builder.mutation({
            query: (formData) => ({
                url: `/users/me/avatar`,
                method: "POST",
                body: formData,
            }),
            invalidatesTags: ["User"],
        }),

        getAvatarUrl: builder.query({
            query: () => `/users/me/avatar-url`,
        }),

        getUserLeaders: builder.query({
            query: () => "/users/leaders",
            providesTags: ["User"],
        }),
    }),
});

export const {
    useGetUsersQuery,
    useUpdateUserRoleMutation,
    useActivateUserMutation,
    useDeactivateUserMutation,
    useUpdateProfileMutation,
    useUploadAvatarMutation,
    useGetAvatarUrlQuery,
    useGetUserLeadersQuery,
} = usersApi;
