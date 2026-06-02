import { api } from "@/store/api";

export const searchApi = api.injectEndpoints({
    endpoints: (builder) => ({
        search: builder.query({
            query: (q) => `/search/?q=${encodeURIComponent(q)}`,
        }),
    }),
});

export const { useSearchQuery } = searchApi;
