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
        getDefaultMiddleware().concat(api.middleware)
})