import { api } from "@/store/api";

export const projectApi = api.injectEndpoints({
    endpoints: (builder) => ({
        getProjects: builder.query({
            query: () => "/projects/",
            providesTags: ["Project"] // used by RTK query to know that calls with this tags will need invalidation in future, when CREATE/UPDATE/DELETE is called
        }),

        createProject: builder.mutation({
            query: (projectData) => ({
                url: "/projects/",
                method: "POST",
                body: projectData,
            }),

            invalidatesTags: ["Project"]
        })
    }),
});

export const {
  useGetProjectsQuery,
  useCreateProjectMutation,
} = projectApi;