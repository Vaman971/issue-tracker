"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSelector } from "react-redux";

export default function RoleProtectedRoute({
    allowedRoles,
    children,
}) {
    const router = useRouter();

    const {
        authChecked,
        isAuthenticated,
        user,
    } = useSelector((state) => state.auth);

    useEffect(() => {
        if (authChecked && !isAuthenticated){
            router.push("/login");
            return;
        }

        if (authChecked && user && !allowedRoles.includes(user.role)) {
            router.push("/projects");
        }
    }, [authChecked, isAuthenticated, user, allowedRoles, router]);

    if(!authChecked || !user){
        return <p>Checking permissions... </p>
    }

    if(!allowedRoles.includes(user.role)){
        return null;
    }

    return children;
}