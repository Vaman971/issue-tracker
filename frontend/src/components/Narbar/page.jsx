"use client"

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDispatch } from "react-redux";
import { api } from "@/store/api";
import { logout } from "@/store/features/auth/authSlice";

import styles from "./page.module.css"
import RoleGate from "../RoleGate/page";

export default function Navbar() {
    const dispatch = useDispatch();
    const router = useRouter();

    const handleLogout = () => {
        dispatch(logout());
        dispatch(api.util.resetApiState()); // for removing RTK api cache from redux
        router.push("/login");
    }

    return (
        <nav className={styles.navbar}>
            <div className={styles.left}>
                <Link className={styles.logo} href="/projects">IssueTracker</Link>
                <Link className={styles.link} href="/projects">Projects</Link>
                <Link className={styles.link} href="/issues">Issues</Link>
                <RoleGate allowedRoles={["admin"]}>
                    <Link className={styles.link} href={"/admin"}>Admin</Link>
                </RoleGate>
            </div>

            <button 
                className={styles.logoutButton}
                onClick={handleLogout}
            >
                Logout
            </button>
        </nav>
    );
}
