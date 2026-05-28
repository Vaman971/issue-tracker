"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSelector } from "react-redux";

/* Without this redux initializes, and isAuthenticated is false initially means redirect happens immediately and then restoreAuth runs, therefore we wait until authChecked is true before deciding */
export default function ProtectedRoute({children}){
    const router = useRouter();

    const {
        isAuthenticated,
        authChecked,
        user,
    } = useSelector((state) => state.auth);

    useEffect(() => {
        if (authChecked && !isAuthenticated){
            router.push("/login")
        }
    }, [authChecked, isAuthenticated, router]);

    if (!authChecked){
        return <p>Loading...</p>;
    }

    if(!isAuthenticated){
        return null; // useEffect runs after render, therefore we return null, so that the browser does not throw error till the state is initialized
    }

    if (!user){
        return <p>Loading user profile ...</p>
    }

    return children;
}