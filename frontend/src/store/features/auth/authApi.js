import { api } from "@/store/api";

export const authApi = api.injectEndpoints({
    endpoints: (builder) => ({
        login: builder.mutation({
            query: (credentials) => ({
                url: "/auth/login",
                method: "POST",
                body: credentials,
            }),
        }),

        register: builder.mutation({
            query: (userData) => ({
                url: "/auth/register",
                method: "POST",
                body: userData,
            }),
        }),

        getMe: builder.query({
            query: () => "/auth/me",
        })
    }),
});

// redux RTK, now auto-generates the react hooks
export const {
    useLoginMutation,
    useRegisterMutation,
    useGetMeQuery,
} = authApi;
