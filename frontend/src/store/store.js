import { configureStore } from "@reduxjs/toolkit";
import { api } from "./api";

import authReducer from "./features/auth/authSlice"

/* 
authApi: talks to the server
authSlice: stores the current auth state locally
*/

export const store = configureStore({
    // stores the API cache inside the Redux
    reducer: {
        auth: authReducer,
        [api.reducerPath] : api.reducer, // this created store.api, the square bracket syntax means the key is dynamic, since api.reducerPath is "api", it becomes { api: api.reducer }
    },

    // handles async request lifecycle, caching, invalidation, polling and refecthing behavior.
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                // The RAG chat mutation takes an `onDelta` callback so a
                // component can render tokens as they stream in. RTK puts a
                // mutation's arguments into the action, and a function is not
                // serialisable, so this one path is exempted rather than
                // giving up streaming. Nothing reads it back out of the store.
                ignoredActions: ["api/executeMutation/pending"],
                ignoredPaths: ["meta.arg.originalArgs.onDelta"],
            },
        }).concat(api.middleware)
})