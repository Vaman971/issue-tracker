# Module 02-03 — Redux Toolkit & RTK Query: State and Data Fetching

---

## Learning Objectives

After this module you will:
- Understand the Redux pattern and why it exists
- Know how Redux Toolkit simplifies Redux
- Understand RTK Query and why it replaces manual fetch + useEffect patterns
- See exactly how this project's store is structured and how data flows

---

## Why Global State Management?

As apps grow, **prop drilling** becomes painful:

```
WITHOUT Redux (prop drilling hell):
App
└── Layout
    └── Navbar
        └── UserMenu
            └── UserAvatar
                └── ProfileLink
                    └── username prop ← has to be passed down 5 levels!
```

With Redux, any component can access the global store directly:

```
WITH Redux (any component accesses store directly):
App
└── Layout
    └── Navbar
        └── UserMenu (reads username from Redux store directly)
```

But there's more than just avoiding prop drilling. Redux gives you:
- **Predictable state**: State can only change through actions
- **Time-travel debugging**: Replay actions to reproduce bugs
- **Centralized cache**: Server data cached in one place, all components see the same data

---

## Redux Architecture: The Core Pattern

```
┌──────────────────────────────────────────────────────────────┐
│                        REDUX STORE                           │
│                                                              │
│  state = {                                                   │
│    auth: { user: {...}, isAuthenticated: true },             │
│    projectsApi: { queries: {...}, mutations: {...} },        │
│    issuesApi: { queries: {...}, mutations: {...} },          │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
         ▲                          │
         │ dispatch(action)         │ state changes
         │                          ▼
┌─────────────────┐       ┌─────────────────┐
│   COMPONENT     │◄──────│   COMPONENT     │
│  (dispatches)   │       │  (reads state)  │
└─────────────────┘       └─────────────────┘
         │
         ▼ dispatch({ type: 'auth/setUser', payload: userData })
┌──────────────────────────────────────────────────────────────┐
│                        REDUCER                               │
│  function authReducer(state, action) {                       │
│    switch (action.type) {                                    │
│      case 'auth/setUser':                                    │
│        return { ...state, user: action.payload }             │
│    }                                                         │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
         │ returns new state
         ▼
Store updates → all subscribed components re-render
```

The **one-way data flow** is Redux's most important property:
```
Action → Reducer → New State → Components re-render
```
No component can modify state directly. All changes go through reducers. This makes debugging predictable.

---

## Redux Toolkit — Modern Redux

Plain Redux required a lot of boilerplate. Redux Toolkit (RTK) eliminates it:

```javascript
// OLD Redux (verbose):
const ADD_TODO = 'ADD_TODO'

const addTodo = (text) => ({ type: ADD_TODO, payload: text })

function todoReducer(state = [], action) {
  switch (action.type) {
    case ADD_TODO:
      return [...state, { text: action.payload }]
    default:
      return state
  }
}

// NEW Redux Toolkit (concise):
import { createSlice } from '@reduxjs/toolkit'

const todoSlice = createSlice({
  name: 'todos',
  initialState: [],
  reducers: {
    addTodo: (state, action) => {
      state.push({ text: action.payload })  // "mutate" (Immer handles immutability)
    }
  }
})

export const { addTodo } = todoSlice.actions
export default todoSlice.reducer
```

RTK uses **Immer** under the hood — you can write "mutating" code and Immer produces an immutable update. This dramatically simplifies reducers.

---

## The Auth Slice — This Project's Core State

```javascript
// frontend/src/store/features/auth/authSlice.js

import { createSlice } from '@reduxjs/toolkit'

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,           // The logged-in user object
    accessToken: null,    // JWT access token
    isAuthenticated: false,
    isLoading: true,      // True during initial token refresh check
  },
  reducers: {
    setCredentials: (state, action) => {
      const { user, accessToken } = action.payload
      state.user = user
      state.accessToken = accessToken
      state.isAuthenticated = true
      state.isLoading = false
    },
    logout: (state) => {
      state.user = null
      state.accessToken = null
      state.isAuthenticated = false
    },
    setLoading: (state, action) => {
      state.isLoading = action.payload
    }
  }
})

export const { setCredentials, logout, setLoading } = authSlice.actions
export default authSlice.reducer

// Selectors — functions that extract data from state
export const selectCurrentUser = (state) => state.auth.user
export const selectIsAuthenticated = (state) => state.auth.isAuthenticated
```

---

## RTK Query — The Data Fetching Layer

RTK Query is a data fetching and caching tool built into Redux Toolkit. It completely replaces the `useEffect` + `fetch` + `useState` pattern for server data.

### The Problem RTK Query Solves

```javascript
// WITHOUT RTK Query (manual, tedious, error-prone):
function ProjectList() {
  const [projects, setProjects] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  
  useEffect(() => {
    setIsLoading(true)
    fetch('/api/projects')
      .then(r => r.json())
      .then(data => {
        setProjects(data)
        setIsLoading(false)
      })
      .catch(err => {
        setError(err)
        setIsLoading(false)
      })
  }, [])  // Only runs once — no auto-refresh!
  
  // 40+ lines of boilerplate for one simple query
}
```

```javascript
// WITH RTK Query:
function ProjectList() {
  const { data: projects, isLoading, error } = useGetProjectsQuery()
  // That's it. RTK Query handles everything:
  // - Loading state
  // - Error state  
  // - Caching (won't refetch if data is fresh)
  // - Background refetching
  // - Deduplication (if 5 components call this, only 1 request is made)
}
```

### How RTK Query Works Internally

```
Component calls useGetProjectsQuery()
        │
        ▼
RTK Query checks its cache:
  Has this query been run before?
  Is the cached data still valid (within refetchInterval)?
        │
   ┌────┴─────┐
   │ In cache │ YES → return cached data immediately
   │  valid?  │       subscribe component to cache entry
   └────┬─────┘       (component re-renders when cache updates)
        │ NO
        ▼
RTK Query fires HTTP request
(using the baseQuery you configured)
        │
        ▼
Response received
        │
        ▼
Data stored in Redux store under:
state.projectsApi.queries['getProjects(undefined)'].data
        │
        ▼
All subscribed components re-render with new data
```

### The Base API Configuration

```javascript
// frontend/src/store/api.js
// This is the BASE configuration all API slices extend from

import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import { setCredentials, logout } from './features/auth/authSlice'

export const baseApi = createApi({
  reducerPath: 'api',
  
  // The base HTTP client configuration
  baseQuery: async (args, api, extraOptions) => {
    // Get the current access token from Redux state
    const token = api.getState().auth.accessToken
    
    // Add Authorization header to every request
    const baseQueryFn = fetchBaseQuery({
      baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
      prepareHeaders: (headers) => {
        if (token) {
          headers.set('Authorization', `Bearer ${token}`)
        }
        return headers
      }
    })
    
    // Make the request
    let result = await baseQueryFn(args, api, extraOptions)
    
    // If we get 401 (Unauthorized), try refreshing the token
    if (result.error?.status === 401) {
      // Try to get a new access token using the refresh token
      const refreshResult = await baseQueryFn(
        { url: '/auth/refresh', method: 'POST' },
        api,
        extraOptions
      )
      
      if (refreshResult.data) {
        // Got a new token! Save it and retry the original request
        api.dispatch(setCredentials(refreshResult.data))
        result = await baseQueryFn(args, api, extraOptions)
      } else {
        // Refresh failed — log out
        api.dispatch(logout())
      }
    }
    
    return result
  },
  
  // Cache tags for invalidation
  // When a mutation runs, it can invalidate related queries
  tagTypes: ['Project', 'Issue', 'User', 'Comment', 'Attachment', 
             'Label', 'Notification', 'Activity', 'Stats', 'Member'],
  
  endpoints: () => ({}) // Endpoints are added in individual slices
})
```

This **automatic token refresh** is one of the most important features — it silently refreshes expired tokens without the user noticing.

### API Slices — Feature-Based Organization

Each feature has its own API slice that extends the base API:

```javascript
// frontend/src/store/features/projects/projectsApi.js

import { baseApi } from '../../api'

export const projectsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    
    // QUERY: fetch data (GET requests)
    getProjects: builder.query({
      query: () => '/projects',
      // This query provides 'Project' tagged data
      // When a mutation invalidates 'Project', this re-fetches
      providesTags: ['Project'],
    }),
    
    getProjectById: builder.query({
      query: (id) => `/projects/${id}`,
      // Tags with ID — only this specific project is invalidated
      providesTags: (result, error, id) => [{ type: 'Project', id }],
    }),
    
    // MUTATION: modify data (POST/PUT/PATCH/DELETE requests)
    createProject: builder.mutation({
      query: (projectData) => ({
        url: '/projects',
        method: 'POST',
        body: projectData,
      }),
      // After creating, invalidate ALL project queries → they re-fetch
      invalidatesTags: ['Project'],
    }),
    
    updateProject: builder.mutation({
      query: ({ id, ...data }) => ({
        url: `/projects/${id}`,
        method: 'PATCH',
        body: data,
      }),
      // Only invalidate this specific project
      invalidatesTags: (result, error, { id }) => [{ type: 'Project', id }],
    }),
    
    deleteProject: builder.mutation({
      query: (id) => ({
        url: `/projects/${id}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Project'],
    }),
  }),
})

// RTK Query auto-generates hooks from endpoint names:
// getProjects → useGetProjectsQuery
// getProjectById → useGetProjectByIdQuery
// createProject → useCreateProjectMutation
export const {
  useGetProjectsQuery,
  useGetProjectByIdQuery,
  useCreateProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
} = projectsApi
```

### Cache Invalidation — How It Works

```
User creates a new project (createProject mutation fires)
        │
        ▼
Mutation succeeds (HTTP 201)
        │
        ▼
RTK Query: mutation has invalidatesTags: ['Project']
        │
        ▼
RTK Query checks: which queries have providesTags: ['Project']?
        │
        ▼
getProjects query found → marked as stale
        │
        ▼
If getProjects is currently subscribed to by a component:
  → re-fetch automatically
  → component re-renders with updated data

If getProjects is NOT subscribed (component unmounted):
  → cache entry marked as stale
  → next time component mounts, data will be re-fetched
```

This is automatic — you never manually update a cached list when adding an item.

---

## The Redux Store Configuration

```javascript
// frontend/src/store/store.js

import { configureStore } from '@reduxjs/toolkit'
import authReducer from './features/auth/authSlice'
import { baseApi } from './api'

export const store = configureStore({
  reducer: {
    // Regular Redux slices
    auth: authReducer,
    
    // RTK Query reducer (all API slices share one root reducer)
    [baseApi.reducerPath]: baseApi.reducer,
  },
  
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(
      // RTK Query middleware enables caching, polling, invalidation
      baseApi.middleware,
    ),
})

// TypeScript-style helper type (not used here, JS project)
export const RootState = store.getState
export const AppDispatch = store.dispatch
```

---

## Component Usage Patterns

### Querying Data

```javascript
'use client'
import { useGetProjectsQuery } from '../store/features/projects/projectsApi'

function ProjectList() {
  const { 
    data: projects,    // The actual data
    isLoading,         // True during first fetch
    isFetching,        // True during any background refetch
    isError,           // True if request failed
    error,             // Error object
    refetch,           // Manually trigger a refetch
  } = useGetProjectsQuery()
  
  if (isLoading) return <SkeletonList />
  if (isError) return <ErrorMessage error={error} />
  
  return (
    <ul>
      {projects.map(project => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </ul>
  )
}
```

### Mutating Data

```javascript
'use client'
import { useCreateProjectMutation } from '../store/features/projects/projectsApi'

function CreateProjectForm() {
  const [createProject, { 
    isLoading,  // True while request is in flight
    isSuccess,  // True after successful mutation
    isError,    // True if mutation failed
    error,      // Error object
  }] = useCreateProjectMutation()
  
  async function handleSubmit(formData) {
    try {
      const newProject = await createProject(formData).unwrap()
      // .unwrap() throws an error if the mutation failed
      // Instead of checking isError, use try/catch
      console.log('Created:', newProject)
    } catch (err) {
      console.error('Failed:', err)
    }
  }
  
  return (
    <form onSubmit={handleSubmit}>
      {/* form fields */}
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Creating...' : 'Create Project'}
      </button>
    </form>
  )
}
```

### Reading Auth State

```javascript
'use client'
import { useSelector, useDispatch } from 'react-redux'
import { selectCurrentUser, logout } from '../store/features/auth/authSlice'

function Navbar() {
  const user = useSelector(selectCurrentUser)
  const dispatch = useDispatch()
  
  return (
    <nav>
      <span>Hello, {user?.name}</span>
      <button onClick={() => dispatch(logout())}>
        Log out
      </button>
    </nav>
  )
}
```

---

## Polling & Real-Time Updates

RTK Query supports automatic polling (re-fetching on a schedule):

```javascript
// Poll for new notifications every 30 seconds
const { data: notifications } = useGetNotificationsQuery(undefined, {
  pollingInterval: 30000,  // milliseconds
})
```

This is simpler than WebSockets for low-frequency updates and works reliably across all browsers.

---

## DevTools Integration

Install the Redux DevTools browser extension to see:
- All dispatched actions in chronological order
- Current state at any point in time
- Ability to "time travel" (jump to any previous state)
- RTK Query cache contents and request status

```
State tree in DevTools:
├── auth
│   ├── user: { id: 1, email: "alice@example.com", role: "ADMIN" }
│   ├── accessToken: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
│   └── isAuthenticated: true
└── api
    └── queries
        ├── getProjects(undefined)
        │   ├── status: "fulfilled"
        │   ├── data: [{ id: 1, name: "Website" }, ...]
        │   └── lastFulfilled: 1706123456789
        └── getProjectById("1")
            ├── status: "fulfilled"
            └── data: { id: 1, name: "Website", ... }
```

---

## Further Reading & Videos

- **YouTube**: Search "Redux Toolkit Tutorial 2024" — Dave Gray has an excellent complete course
- **YouTube**: Search "RTK Query Tutorial" — Dave Gray also covers this thoroughly
- **Official Docs**: [Redux Toolkit documentation](https://redux-toolkit.js.org)
- **Official Docs**: [RTK Query overview](https://redux-toolkit.js.org/rtk-query/overview)

---

*Next: [Module 02-04 — React Hook Form & Zod](./04-forms-validation.md)*
