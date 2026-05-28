import { api } from "@/store/api";

export const usersApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getUsers: builder.query({
            query: () => "/users/",
            providesTags: ["User"]
        }),

        updateUserRole: builder.mutation({
            query: ({userId, role}) => ({
                url: `/users/${userId}/role?role=${role}`,
                method: "PATCH"
            }),
            invalidatesTags: ["User"]
        }),
    }),
});

export const {
    useGetUsersQuery,
    useUpdateUserRoleMutation,
} = usersApi