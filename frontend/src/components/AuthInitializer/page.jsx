"use client";

import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import { useGetMeQuery } from "@/store/features/auth/authApi";

import {
    restoreAuth,
    setCurrentUser,
    logout,
} from "@/store/features/auth/authSlice"

export default function AuthInitializer({children}) {
    const dispath = useDispatch();

    useEffect(() => {
        dispath(restoreAuth());
    }, [dispath]);

    const { isAuthenticated } = useSelector((state) => state.auth);

    const {
        data: currentUser,
        isSuccess,
        isError,
    } = useGetMeQuery(undefined, {
        skip:  !isAuthenticated,
        refetchOnMountOrArgChange: isAuthenticated // makes sure that the auth api's RTK query cache is also resetting not just the auth slice
    });

    useEffect(() => {
        if(isSuccess && currentUser){
            dispath(setCurrentUser(currentUser));
        }

        if (isError){
            dispath(logout());
        }
    }, [isSuccess, isError, currentUser, dispath]);

    return children;
}