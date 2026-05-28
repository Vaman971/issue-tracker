import { api } from "@/store/api";

export const IssuesApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getIssues: builder.query({
            query: ({skip = 0, limit = 20} = {}) => (
                `/issues/?skip=${skip}&limit=${limit}`
            ),
            providesTags: ["Issue"], // marks the fetched data as cacheable
        }),

        createIssue: builder.mutation({
            query: (issueData) => ({
                url: `/issues/`,
                method: "POST",
                body: issueData,
            }),
            invalidatesTags: ["Issue"] // tells after creating/update the data may be stale, so reload it
        }),

        updateIssue: builder.mutation({
            query: ({issueId, data}) => ({
                url: `/issues/${issueId}`,
                method: "PATCH",
                body: data,
            }),
            
            /*click update
            → update UI immediately
            → send request
            → if server fails, rollback */
            async onQueryStarted(
                {issueId, data, queryArgs= {skip: 0, limit: 20}}, 
                {dispatch, queryFulfilled}
            ){
                const patchResult = dispatch (
                    api.util.updateQueryData(
                        "getIssues",
                        queryArgs,
                        (draft) => {
                            const issue = draft.find((item) => item.id === issueId);

                            if (issue) {
                                Object.assign(issue, data)
                            }
                        }
                    )
                );

                try {
                    await queryFulfilled;
                } catch {
                    patchResult.undo(); //rollback
                }
            },
            invalidatesTags: ["Issue"]
        }),
    }),
});

export const {
    useGetIssuesQuery,
    useCreateIssueMutation,
    useUpdateIssueMutation,
} = IssuesApi;
