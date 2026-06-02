"use client"

import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import {
    useActivateUserMutation,
    useDeactivateUserMutation,
    useGetUsersQuery,
    useUpdateUserRoleMutation,
} from "@/store/features/users/usersApi";
import { useGetAdminStatsQuery } from "@/store/features/stats/statsApi";
import { useDebounce } from "@/hooks/useDebounce";
import styles from "./page.module.css";

const roles = ["admin", "project_leader", "developer", "qa", "viewer"];
const PAGE_SIZE = 15;

function StatCard({ label, value, color }) {
    return (
        <div className={styles.statCard}>
            <span className={styles.statNumber} style={color ? { color } : {}}>
                {value ?? "—"}
            </span>
            <span className={styles.statLabel}>{label}</span>
        </div>
    );
}

export default function AdminPage() {
    const [userSearch, setUserSearch] = useState("");
    const [page, setPage] = useState(0);
    const debouncedUserSearch = useDebounce(userSearch, 350);
    const skip = page * PAGE_SIZE;

    // Reset to first page when search changes
    useEffect(() => {
        setPage(0);
    }, [debouncedUserSearch]);

    const { data: users = [], isLoading, isError } = useGetUsersQuery({
        skip,
        limit: PAGE_SIZE,
        q: debouncedUserSearch || undefined,
    });
    const { data: stats } = useGetAdminStatsQuery();
    const currentUser = useSelector((s) => s.auth.user);

    const [updateUserRole, { isLoading: isUpdating }] = useUpdateUserRoleMutation();
    const [activateUser] = useActivateUserMutation();
    const [deactivateUser] = useDeactivateUserMutation();

    const handleRoleChange = async (userId, role) => {
        try {
            await updateUserRole({ userId, role }).unwrap();
        } catch (err) {
            alert(err?.data?.detail || "Failed to update role.");
        }
    };

    const handleToggleActive = async (user) => {
        try {
            if (user.is_active) {
                await deactivateUser(user.id).unwrap();
            } else {
                await activateUser(user.id).unwrap();
            }
        } catch (err) {
            alert(err?.data?.detail || "Failed to update status.");
        }
    };

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <p className={styles.eyebrow}>Admin</p>
                <h1 className={styles.title}>Dashboard</h1>
            </header>

            {/* Platform Stats */}
            {stats && (
                <section className={styles.statsSection}>
                    <h2 className={styles.sectionTitle}>Platform Overview</h2>
                    <div className={styles.statsRow}>
                        <StatCard label="Total Users" value={stats.total_users} />
                        <StatCard label="Total Projects" value={stats.total_projects} />
                        <StatCard label="Total Issues" value={stats.total_issues} />
                        <StatCard
                            label="Completed"
                            value={stats.issues_by_status?.done ?? 0}
                            color="#16a34a"
                        />
                        <StatCard
                            label="In Progress"
                            value={stats.issues_by_status?.in_progress ?? 0}
                            color="#2563eb"
                        />
                    </div>

                    {stats.users_by_role && (
                        <div className={styles.roleBreakdown}>
                            <p className={styles.breakdownTitle}>Users by role:</p>
                            <div className={styles.roleChips}>
                                {Object.entries(stats.users_by_role).map(([role, count]) => (
                                    <span key={role} className={styles.roleChip}>
                                        {role}: <strong>{count}</strong>
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* User Management */}
            <section>
                <div className={styles.userMgmtHeader}>
                    <h2 className={styles.sectionTitle}>User Management</h2>
                    <input
                        className={styles.userSearchInput}
                        type="search"
                        placeholder="Search by name or email..."
                        value={userSearch}
                        onChange={(e) => setUserSearch(e.target.value)}
                    />
                </div>

                {isLoading && <p>Loading users...</p>}
                {isError && <p className={styles.error}>Could not load users.</p>}

                {!isLoading && !isError && (
                    <>
                        <div className={styles.card}>
                            <table className={styles.table}>
                                <thead>
                                    <tr>
                                        <th>Email</th>
                                        <th>Name</th>
                                        <th>Current Role</th>
                                        <th>Change Role</th>
                                        <th>Status</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} style={{ textAlign: "center", color: "#9ca3af", padding: "24px" }}>
                                                {debouncedUserSearch
                                                    ? `No users matching "${debouncedUserSearch}".`
                                                    : "No users found."}
                                            </td>
                                        </tr>
                                    ) : (
                                        users.map((user) => {
                                            const isSelf = user.id === currentUser?.id;
                                            return (
                                                <tr key={user.id}>
                                                    <td>{user.email}</td>
                                                    <td>{user.full_name || "—"}</td>
                                                    <td>
                                                        <span className={styles.roleBadge}>{user.role}</span>
                                                    </td>
                                                    <td>
                                                        {isSelf ? (
                                                            <span style={{ fontSize: 13, color: "#9ca3af" }}>
                                                                (your account)
                                                            </span>
                                                        ) : (
                                                            <select
                                                                value={user.role}
                                                                disabled={isUpdating}
                                                                onChange={(e) =>
                                                                    handleRoleChange(user.id, e.target.value)
                                                                }
                                                            >
                                                                {roles.map((r) => (
                                                                    <option key={r} value={r}>
                                                                        {r}
                                                                    </option>
                                                                ))}
                                                            </select>
                                                        )}
                                                    </td>
                                                    <td>
                                                        <span
                                                            className={
                                                                user.is_active
                                                                    ? styles.activeChip
                                                                    : styles.inactiveChip
                                                            }
                                                        >
                                                            {user.is_active ? "Active" : "Inactive"}
                                                        </span>
                                                    </td>
                                                    <td>
                                                        {isSelf ? (
                                                            <span style={{ fontSize: 13, color: "#9ca3af" }}>—</span>
                                                        ) : (
                                                            <button
                                                                className={
                                                                    user.is_active
                                                                        ? styles.deactivateBtn
                                                                        : styles.activateBtn
                                                                }
                                                                type="button"
                                                                onClick={() => handleToggleActive(user)}
                                                            >
                                                                {user.is_active ? "Deactivate" : "Activate"}
                                                            </button>
                                                        )}
                                                    </td>
                                                </tr>
                                            );
                                        })
                                    )}
                                </tbody>
                            </table>
                        </div>

                        {(page > 0 || users.length === PAGE_SIZE) && (
                            <div className={styles.tablePagination}>
                                <button
                                    type="button"
                                    className={styles.pageBtn}
                                    disabled={page === 0}
                                    onClick={() => setPage((p) => p - 1)}
                                >
                                    ← Previous
                                </button>
                                <span className={styles.pageLabel}>Page {page + 1}</span>
                                <button
                                    type="button"
                                    className={styles.pageBtn}
                                    disabled={users.length < PAGE_SIZE}
                                    onClick={() => setPage((p) => p + 1)}
                                >
                                    Next →
                                </button>
                            </div>
                        )}
                    </>
                )}
            </section>
        </main>
    );
}
