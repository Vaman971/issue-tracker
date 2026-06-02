"use client"

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useSearchQuery } from "@/store/features/search/searchApi";
import styles from "./page.module.css";

const PRIORITY_COLORS = {
    low: "#6b7280",
    medium: "#2563eb",
    high: "#d97706",
    critical: "#dc2626",
};

export default function SearchPage() {
    const searchParams = useSearchParams();
    const urlQuery = searchParams.get("q") || "";

    const [query, setQuery] = useState(urlQuery);
    const [submitted, setSubmitted] = useState(urlQuery);

    // Sync when the URL param changes (e.g. new search from navbar)
    useEffect(() => {
        const q = searchParams.get("q") || "";
        setQuery(q);
        setSubmitted(q);
    }, [searchParams]);

    const { data, isLoading, isFetching } = useSearchQuery(submitted, {
        skip: submitted.trim().length < 2,
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        setSubmitted(query.trim());
    };

    const hasResults =
        data && (data.issues?.length > 0 || data.projects?.length > 0);
    const noResults =
        submitted && !isLoading && !isFetching && data && !hasResults;

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <p className={styles.eyebrow}>Search</p>
                <h1 className={styles.title}>Find anything</h1>
            </header>

            <form className={styles.searchForm} onSubmit={handleSubmit}>
                <input
                    className={styles.searchInput}
                    type="search"
                    placeholder="Search issues and projects..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    autoFocus
                />
                <button
                    className={styles.searchButton}
                    type="submit"
                    disabled={isLoading || isFetching || query.trim().length < 2}
                >
                    {isLoading || isFetching ? "Searching..." : "Search"}
                </button>
            </form>

            {(isLoading || isFetching) && (
                <p className={styles.loadingText}>Searching...</p>
            )}

            {noResults && (
                <div className={styles.emptyState}>
                    <div className={styles.emptyIcon}>🔍</div>
                    <h2 className={styles.emptyTitle}>No results for &quot;{submitted}&quot;</h2>
                    <p className={styles.emptyText}>Try different keywords.</p>
                </div>
            )}

            {!isLoading && !isFetching && hasResults && (
                <div className={styles.results}>
                    {/* Projects */}
                    {data.projects?.length > 0 && (
                        <section className={styles.section}>
                            <h2 className={styles.sectionTitle}>
                                Projects
                                <span className={styles.count}>{data.projects.length}</span>
                            </h2>
                            <div className={styles.grid}>
                                {data.projects.map((project) => (
                                    <Link
                                        key={project.id}
                                        href={`/projects/${project.id}`}
                                        className={styles.projectCard}
                                    >
                                        <div className={styles.projectIcon}>📁</div>
                                        <div>
                                            <h3 className={styles.cardTitle}>{project.name}</h3>
                                            {project.description && (
                                                <p className={styles.cardDesc}>
                                                    {project.description.slice(0, 100)}
                                                    {project.description.length > 100 && "..."}
                                                </p>
                                            )}
                                        </div>
                                    </Link>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Issues */}
                    {data.issues?.length > 0 && (
                        <section className={styles.section}>
                            <h2 className={styles.sectionTitle}>
                                Issues
                                <span className={styles.count}>{data.issues.length}</span>
                            </h2>
                            <div className={styles.issueList}>
                                {data.issues.map((issue) => (
                                    <Link
                                        key={issue.id}
                                        href={`/issues/${issue.id}`}
                                        className={styles.issueCard}
                                    >
                                        <div className={styles.issueInfo}>
                                            <h3 className={styles.cardTitle}>{issue.title}</h3>
                                            {issue.description && (
                                                <p className={styles.cardDesc}>
                                                    {issue.description.slice(0, 120)}
                                                    {issue.description.length > 120 && "..."}
                                                </p>
                                            )}
                                        </div>
                                        <div className={styles.issueBadges}>
                                            <span
                                                className={styles.priorityBadge}
                                                style={{
                                                    background:
                                                        PRIORITY_COLORS[issue.priority] + "22",
                                                    color: PRIORITY_COLORS[issue.priority],
                                                }}
                                            >
                                                {issue.priority}
                                            </span>
                                            <span className={styles.statusBadge}>
                                                {issue.status.replace("_", " ")}
                                            </span>
                                        </div>
                                    </Link>
                                ))}
                            </div>
                        </section>
                    )}
                </div>
            )}
        </main>
    );
}
