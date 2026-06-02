"use client"

import { useEffect, useState } from "react";

import SkeletonCard from "@/components/SkeletonCard/page";
import RoleGate from "@/components/RoleGate/page";
import CreateProjectModal from "@/components/CreateProjectModal/page";
import { useGetProjectsQuery } from "@/store/features/projects/projectsApi";
import { useDebounce } from "@/hooks/useDebounce";
import styles from "./page.module.css";
import Link from "next/link";

const PAGE_SIZE = 12;

export default function ProjectPage() {
    const [searchTerm, setSearchTerm] = useState("");
    const [page, setPage] = useState(0);
    const [showCreate, setShowCreate] = useState(false);
    const debouncedSearch = useDebounce(searchTerm, 350);
    const skip = page * PAGE_SIZE;

    useEffect(() => {
        setPage(0);
    }, [debouncedSearch]);

    const {
        data: projects = [],
        isLoading,
        isError,
    } = useGetProjectsQuery({ skip, limit: PAGE_SIZE, q: debouncedSearch || undefined });

    const toolbar = (
        <div className={styles.toolbar}>
            <input
                className={styles.searchInput}
                type="search"
                placeholder="Search projects..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
            />
            <RoleGate allowedRoles={["admin", "project_leader"]}>
                <button
                    type="button"
                    className={styles.createButton}
                    onClick={() => setShowCreate(true)}
                >
                    + Create Project
                </button>
            </RoleGate>
        </div>
    );

    if (isLoading) {
        return (
            <main className={styles.page}>
                <header className={styles.header}>
                    <p className={styles.eyebrow}>Projects</p>
                    <h1 className={styles.title}>Your Project Workspace</h1>
                </header>
                {toolbar}
                <section className={styles.grid}>
                    {Array.from({ length: PAGE_SIZE }).map((_, i) => (
                        <SkeletonCard key={i} />
                    ))}
                </section>
                <CreateProjectModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
            </main>
        );
    }

    if (isError) {
        return (
            <main className={styles.page}>
                <header className={styles.header}>
                    <p className={styles.eyebrow}>Projects</p>
                    <h1 className={styles.title}>Your Project Workspace</h1>
                </header>
                {toolbar}
                <p className={styles.error}>Could not load projects.</p>
                <CreateProjectModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
            </main>
        );
    }

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <p className={styles.eyebrow}>Projects</p>
                <h1 className={styles.title}>Your Project Workspace</h1>
            </header>

            {toolbar}

            <section className={styles.grid}>
                {projects.length === 0 && (
                    <p className={styles.empty}>
                        {debouncedSearch
                            ? `No projects matching "${debouncedSearch}".`
                            : "No projects available."}
                    </p>
                )}

                {projects.map((project) => (
                    <Link
                        key={project.id}
                        href={`/projects/${project.id}`}
                        className={styles.cardLink}
                    >
                        <article className={styles.card}>
                            <h2 className={styles.cardTitle}>{project.name}</h2>
                            <p className={styles.description}>
                                {project.description || "No description provided"}
                            </p>
                            <div className={styles.cardFooter}>
                                <span className={styles.meta}>
                                    {project.leader
                                        ? (project.leader.full_name || project.leader.email)
                                        : `Leader #${project.leader_id}`}
                                </span>
                                <span className={styles.viewLink}>View →</span>
                            </div>
                        </article>
                    </Link>
                ))}
            </section>

            {(page > 0 || projects.length === PAGE_SIZE) && (
                <div className={styles.pagination}>
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
                        disabled={projects.length < PAGE_SIZE}
                        onClick={() => setPage((p) => p + 1)}
                    >
                        Next →
                    </button>
                </div>
            )}

            <CreateProjectModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
        </main>
    );
}
