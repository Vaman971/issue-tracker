"use client"

import { useEffect, useState } from "react";
import Link from "next/link";

import { useGetIssuesQuery, useUpdateIssueMutation } from "@/store/features/issues/issuesApi";
import SkeletonCard from "@/components/SkeletonCard/page";
import RoleGate from "@/components/RoleGate/page";
import { useDebounce } from "@/hooks/useDebounce";
import styles from "./page.module.css";

const PAGE_SIZE = 10;

const PRIORITY_COLORS = {
    low: "#6b7280",
    medium: "#2563eb",
    high: "#d97706",
    critical: "#dc2626",
};

const STATUS_CYCLE = {
    todo: "in_progress",
    in_progress: "in_review",
    in_review: "done",
    done: "todo",
};

export default function IssuePage() {
    const [page, setPage] = useState(0);
    const [searchTerm, setSearchTerm] = useState("");
    const debouncedSearch = useDebounce(searchTerm, 400);
    const skip = page * PAGE_SIZE;

    // Reset to first page whenever the search term changes
    useEffect(() => {
        setPage(0);
    }, [debouncedSearch]);

    const {
        data: issues = [],
        isLoading,
        isError,
    } = useGetIssuesQuery({ skip, limit: PAGE_SIZE, q: debouncedSearch || undefined });

    const [updateIssue] = useUpdateIssueMutation();

    const handleStatusChange = async (issue) => {
        await updateIssue({
            issueId: issue.id,
            data: { status: STATUS_CYCLE[issue.status] || "todo" },
            queryArgs: { skip, limit: PAGE_SIZE, q: debouncedSearch || undefined },
        });
    };

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <p className={styles.eyebrow}>Issues</p>
                <h1 className={styles.title}>Your Issue Board</h1>
            </header>

            <div className={styles.searchBar}>
                <input
                    className={styles.searchInput}
                    type="search"
                    placeholder="Search issues..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            {isLoading && (
                <section className={styles.list}>
                    {Array.from({ length: 5 }).map((_, i) => (
                        <SkeletonCard key={i} />
                    ))}
                </section>
            )}

            {isError && <p className={styles.error}>Could not load issues.</p>}

            {!isLoading && !isError && (
                <>
                    <section className={styles.list}>
                        {issues.length === 0 && (
                            <p className={styles.empty}>
                                {debouncedSearch ? `No issues matching "${debouncedSearch}".` : "No issues found."}
                            </p>
                        )}

                        {issues.map((issue) => (
                            <article key={issue.id} className={styles.card}>
                                <Link href={`/issues/${issue.id}`} className={styles.cardLink}>
                                    <div className={styles.cardMain}>
                                        <h2 className={styles.cardTitle}>{issue.title}</h2>
                                        <p className={styles.description}>
                                            {issue.description || "No description provided"}
                                        </p>
                                    </div>

                                    <div className={styles.metaRow}>
                                        <span
                                            className={styles.priorityBadge}
                                            style={{
                                                background: PRIORITY_COLORS[issue.priority] + "22",
                                                color: PRIORITY_COLORS[issue.priority],
                                            }}
                                        >
                                            {issue.priority}
                                        </span>
                                        <span className={styles.statusBadge}>
                                            {issue.status.replace("_", " ")}
                                        </span>
                                        {issue.project_id && (
                                            <span className={styles.projectRef}>
                                                Project #{issue.project_id}
                                            </span>
                                        )}
                                    </div>
                                </Link>

                                <RoleGate
                                    allowedRoles={["admin", "project_leader", "developer", "qa"]}
                                >
                                    <button
                                        className={styles.statusButton}
                                        type="button"
                                        onClick={() => handleStatusChange(issue)}
                                    >
                                        Move: {STATUS_CYCLE[issue.status]?.replace("_", " ")}
                                    </button>
                                </RoleGate>
                            </article>
                        ))}
                    </section>

                    {issues.length !== 0 && (
                        <div className={styles.pagination}>
                            <button
                                type="button"
                                disabled={page === 0}
                                onClick={() => setPage((p) => p - 1)}
                            >
                                Previous
                            </button>
                            <span className={styles.pageLabel}>Page {page + 1}</span>
                            <button
                                type="button"
                                disabled={issues.length < PAGE_SIZE}
                                onClick={() => setPage((p) => p + 1)}
                            >
                                Next
                            </button>
                        </div>
                    )}
                </>
            )}
        </main>
    );
}
