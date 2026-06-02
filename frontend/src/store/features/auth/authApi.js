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
            providesTags: ["User"],
        }),

        forgotPassword: builder.mutation({
            query: (body) => ({
                url: "/auth/forgot-password",
                method: "POST",
                body,
            }),
        }),

        resetPassword: builder.mutation({
            query: (body) => ({
                url: "/auth/reset-password",
                method: "POST",
                body,
            }),
        }),

        verifyEmail: builder.mutation({
            query: (body) => ({
                url: "/auth/verify-email",
                method: "POST",
                body,
            }),
            invalidatesTags: ["User"],
        }),

        resendVerification: builder.mutation({
            query: () => ({
                url: "/auth/resend-verification",
                method: "POST",
            }),
        }),

        changePassword: builder.mutation({
            query: (body) => ({
                url: "/auth/change-password",
                method: "POST",
                body,
            }),
        }),
    }),
});

export const {
    useLoginMutation,
    useRegisterMutation,
    useGetMeQuery,
    useForgotPasswordMutation,
    useResetPasswordMutation,
    useVerifyEmailMutation,
    useResendVerificationMutation,
    useChangePasswordMutation,
} = authApi;
