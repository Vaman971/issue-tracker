import { createSlice } from "@reduxjs/toolkit";

const initialState = {
    accessToken: null,
    refreshToken: null,
    user: null,
    isAuthenticated: false,
    authChecked: false
};

const authSlice = createSlice({
    name: "auth",

    initialState,

    reducers: {

        setCurrentUser: (state, action) => {
            state.user = action.payload;
        },

        // action: action-type-specific case reducer
        setCredentials: (state, action) => {
            const { accessToken, refreshToken} = action.payload || {};

            state.accessToken = accessToken;
            state.refreshToken = refreshToken;
            state.isAuthenticated = true;
            state.authChecked = true

            localStorage.setItem("accessToken", accessToken);
            localStorage.setItem("refreshToken", refreshToken);
        },

        restoreAuth: (state) => {
            const accessToken = localStorage.getItem("accessToken");
            const refreshToken = localStorage.getItem("refreshToken");

            if(accessToken && refreshToken){
                state.accessToken = accessToken;
                state.refreshToken = refreshToken;
                state.isAuthenticated = true;
            }

            state.authChecked = true;
        },

        logout: (state) => {
            state.accessToken = null;
            state.refreshToken = null;
            state.user = null;
            state.isAuthenticated = false;
            state.authChecked = true;

            localStorage.removeItem("accessToken");
            localStorage.removeItem("refreshToken");
        },
    },
});

export const {
    setCurrentUser,
    setCredentials,
    restoreAuth,
    logout,
} = authSlice.actions;

export default authSlice.reducer;
