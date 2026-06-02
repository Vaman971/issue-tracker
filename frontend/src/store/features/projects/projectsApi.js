import { api } from "@/store/api";

export const projectApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getProjects: builder.query({
            query: ({ skip = 0, limit = 12, q } = {}) => {
                const params = new URLSearchParams({ skip, limit });
                if (q) params.set("q", q);
                return `/projects/?${params}`;
            },
            providesTags: ["Project"],
        }),

        getProject: builder.query({
            query: (projectId) => `/projects/${projectId}`,
            providesTags: (_result, _error, id) => [{ type: "Project", id }],
        }),

        createProject: builder.mutation({
            query: (projectData) => ({
                url: "/projects/",
                method: "POST",
                body: projectData,
            }),
            invalidatesTags: ["Project"],
        }),

        updateProject: builder.mutation({
            query: ({ projectId, data }) => ({
                url: `/projects/${projectId}`,
                method: "PATCH",
                body: data,
            }),
            invalidatesTags: (_result, _error, { projectId }) => [
                "Project",
                { type: "Project", id: projectId },
            ],
        }),

        deleteProject: builder.mutation({
            query: (projectId) => ({
                url: `/projects/${projectId}`,
                method: "DELETE",
            }),
            invalidatesTags: ["Project"],
        }),

        getProjectIssues: builder.query({
            query: ({ projectId, status, priority, search, skip = 0, limit = 10 }) => ({
                url: `/projects/${projectId}/issues/`,
                params: {
                    skip,
                    limit,
                    ...(status && { status }),
                    ...(priority && { priority }),
                    ...(search && { search }),
                },
            }),
            providesTags: (_result, _error, { projectId }) => [
                { type: "Issue", id: `project-${projectId}` },
                "Issue",
            ],
        }),

        getIssueAssigneeCandidates: builder.query({
            query: (projectId) => `/projects/${projectId}/issue-assignee-candidates`,
            providesTags: (_result, _error, id) => [{ type: "Member", id }],
        }),

        getProjectMembers: builder.query({
            query: (projectId) => `/projects/${projectId}/members/`,
            providesTags: (_result, _error, id) => [{ type: "Member", id }],
        }),

        addProjectMember: builder.mutation({
            query: ({ projectId, userId, role }) => ({
                url: `/projects/${projectId}/members/`,
                method: "POST",
                body: { user_id: userId, role },
            }),
            invalidatesTags: (_result, _error, { projectId }) => [
                { type: "Member", id: projectId },
            ],
        }),

        removeProjectMember: builder.mutation({
            query: ({ projectId, userId }) => ({
                url: `/projects/${projectId}/members/${userId}`,
                method: "DELETE",
            }),
            invalidatesTags: (_result, _error, { projectId }) => [
                { type: "Member", id: projectId },
            ],
        }),

        getMemberCandidates: builder.query({
            query: (projectId) => `/projects/${projectId}/members/candidates`,
            providesTags: (_result, _error, id) => [{ type: "Member", id }],
        }),
    }),
});

export const {
    useGetProjectsQuery,
    useGetProjectQuery,
    useCreateProjectMutation,
    useUpdateProjectMutation,
    useDeleteProjectMutation,
    useGetProjectIssuesQuery,
    useGetIssueAssigneeCandidatesQuery,
    useGetProjectMembersQuery,
    useAddProjectMemberMutation,
    useRemoveProjectMemberMutation,
    useGetMemberCandidatesQuery,
} = projectApi;
