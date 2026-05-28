"use client"

import { useState } from "react";
import { useGetIssuesQuery, useUpdateIssueMutation } from "@/store/features/issues/issuesApi";
import SkeletonCard from "@/components/SkeletonCard/page";
import styles from "./page.module.css"
import RoleGate from "@/components/RoleGate/page";

const PAGE_SIZE = 5;

export default function IssuePage() {
    const [page, setPage] = useState(0); // local UI, not a redux state, so it only matters to this page
    const skip = page * PAGE_SIZE;

    const {
        data: issues = [],
        isLoading,
        isError,
    } = useGetIssuesQuery({
        skip,
        limit: PAGE_SIZE
    });

    const [updateIssue] = useUpdateIssueMutation();

    const handleStatusChange = async (issue) => {
        const nextStatus =  
                issue.status === "todo"
                ? "in_progress"
                : issue.status === "in_progress"
                    ? "in_review"
                    : issue.status === "in_review"
                        ? "done"
                        : "todo";
        
        await updateIssue({
            issueId: issue.id,
            data: {
                status: nextStatus,
            },
            queryArgs: {
                skip,
                limit: PAGE_SIZE
            }
        })
    }

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <p className={styles.eyebrow}>Issues</p>
                <h1 className={styles.title}>Your Issue board</h1>
            </header>

            {isLoading && (
                <section className={styles.list}>
                    {Array.from({length: 5}).map((_, index) => (
                        <SkeletonCard key={index}/>
                    ))}
                </section>
            )}

            {isError && <p className={styles.error}>Could not load issues.</p>}

            {!isLoading && !isError && (
                <>
                    <section className={styles.list}>
                        {issues.length === 0 && (
                            <p className={styles.empty}>No issues found</p>
                        )}

                        {issues.map((issue) => (
                            <article key={issue.id} className={styles.card}>
                                <div>
                                    <h2 className={styles.cardTitle}>{issue.title}</h2>
                                    <p className={styles.description}>
                                        {issue.description || "No description provided"}
                                    </p>
                                </div>

                                <div className={styles.metaRow}>
                                    <span>Status: {issue.status}</span>
                                    <span>Priority: {issue.priority}</span>
                                </div>
                                <RoleGate allowedRoles={["admin", "project_leader", "developer", "qa"]}>                       
                                <button
                                 className={styles.statusButton}
                                 type="button"
                                 onClick={() => handleStatusChange(issue)}
                                >Move status</button>
                                </RoleGate>
                            </article>
                        ))}
                    </section>
                {issues.length !== 0 && (
                    <div className={styles.pagination}>
                        <button
                        type="button"
                        disabled = {page === 0}
                        onClick={() => setPage((currentPage) => currentPage -1)}
                        >
                            Previous
                        </button>

                        <span className={styles.span}> Page {page +1}</span>

                        <button
                        type="button"
                        disabled = {issues.length < PAGE_SIZE}
                        onClick={() => setPage((currentPage) => currentPage + 1)} 
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