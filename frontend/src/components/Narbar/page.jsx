"use client"

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useDispatch } from "react-redux";

import { api } from "@/store/api";
import { logout } from "@/store/features/auth/authSlice";
import { useGetNotificationCountQuery } from "@/store/features/notifications/notificationsApi";
import NotificationDrawer from "@/components/NotificationDrawer/page";
import RoleGate from "../RoleGate/page";
import styles from "./page.module.css";

export default function Navbar() {
    const dispatch = useDispatch();
    const router = useRouter();
    const [searchQuery, setSearchQuery] = useState("");
    const [drawerOpen, setDrawerOpen] = useState(false);

    const { data: notifCount } = useGetNotificationCountQuery(undefined, {
        pollingInterval: 30000,
    });
    const unreadCount = notifCount?.unread || 0;

    const handleLogout = () => {
        dispatch(logout());
        dispatch(api.util.resetApiState());
        router.push("/login");
    };

    const handleSearch = (e) => {
        e.preventDefault();
        const q = searchQuery.trim();
        if (q.length < 2) return;
        router.push(`/search?q=${encodeURIComponent(q)}`);
    };

    return (
        <>
            <nav className={styles.navbar}>
                <div className={styles.left}>
                    <Link className={styles.logo} href="/projects">
                        IssueTracker
                    </Link>
                    <Link className={styles.link} href="/projects">
                        Projects
                    </Link>
                    <Link className={styles.link} href="/issues">
                        Issues
                    </Link>
                    <RoleGate allowedRoles={["admin"]}>
                        <Link className={styles.link} href="/admin">
                            Admin
                        </Link>
                    </RoleGate>
                </div>

                <form className={styles.searchForm} onSubmit={handleSearch}>
                    <div className={styles.searchWrap}>
                        <svg className={styles.searchIcon} width="14" height="14" viewBox="0 0 20 20" fill="none">
                            <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="2" />
                            <line x1="14.5" y1="14.5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                        </svg>
                        <input
                            className={styles.searchInput}
                            type="search"
                            placeholder="Search..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            aria-label="Global search"
                        />
                    </div>
                </form>

                <div className={styles.right}>
                    <button
                        type="button"
                        className={styles.notifBtn}
                        onClick={() => setDrawerOpen(true)}
                        aria-label="Open notifications"
                        aria-expanded={drawerOpen}
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                        </svg>
                        {unreadCount > 0 && (
                            <span className={styles.badge}>
                                {unreadCount > 99 ? "99+" : unreadCount}
                            </span>
                        )}
                    </button>

                    <Link className={styles.link} href="/profile">
                        Profile
                    </Link>

                    <button className={styles.logoutButton} onClick={handleLogout}>
                        Logout
                    </button>
                </div>
            </nav>

            <NotificationDrawer
                isOpen={drawerOpen}
                onClose={() => setDrawerOpen(false)}
            />
        </>
    );
}
