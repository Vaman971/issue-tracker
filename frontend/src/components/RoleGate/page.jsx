"use client";

import { useSelector } from "react-redux";

export default function RoleGate({allowedRoles, children}){
    const user = useSelector((state) => state.auth.user)

    if (!user){
        return null;
    }

    if(!allowedRoles.includes(user.role)){
        return null;
    }

    return children;
}