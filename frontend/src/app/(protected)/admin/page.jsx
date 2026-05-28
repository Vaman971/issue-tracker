"use client"

import {
    useGetUsersQuery,
    useUpdateUserRoleMutation,
} from "@/store/features/users/usersApi";

import styles from "./page.module.css";


const roles = [
    "admin",
    "project_leader",
    "developer",
    "qa",
    "viewer",
];

export default function AdminPage(){
    const {
        data: users = [],
        isLoading,
        isError,
    } = useGetUsersQuery();

    const [updateUserRole, { isLoading: isUpdating}] = useUpdateUserRoleMutation();

    const handleRoleChange = async (userId, role) => {
        await updateUserRole({
            userId,
            role,
        }).unwrap();
    }

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <p className={styles.eyebrow}>Admin</p>
                <h1 className={styles.title}>User management</h1>
            </header>

            {isLoading && <p>Loading users...</p>}

            {isError && (
                <p className={styles.error}>
                    Could not load users.
                </p>
            )}

            {!isLoading && !isError && (
                <section className={styles.card}>
                    <table className={styles.table}>
                        <thead>
                            <tr>
                                <th>Email</th>
                                <th>Current Role</th>
                                <th>Change Role</th>
                            </tr>
                        </thead>

                        <tbody>
                            {users.map((user) => (
                                <tr key={user.id}>
                                    <td>{user.email}</td>
                                    <td>{user.role}</td>
                                    <td>
                                        <select
                                        value={user.role}
                                        disabled={isUpdating}
                                        onChange={(e) => handleRoleChange(
                                            user.id,
                                            e.target.value
                                        )}
                                        >
                                        {roles.map((role) => (
                                            <option key={role} value={role}>
                                                {role}
                                            </option>
                                        ))}
                                        </select>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>
            )}
        </main>
    )
}