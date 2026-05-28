"use client"

import { useGetProjectsQuery } from "@/store/features/projects/projectsApi"
import styles from "./page.module.css";
import SkeletonCard from "@/components/SkeletonCard/page";
import RoleGate from "@/components/RoleGate/page";
import Link from "next/link";

export default function ProjectPage() {
    // RTK query replaces a lot of manual redux code lile 
    // projectsFetchStart
    // projectFetechSuccess
    // projectFetchFailure
    // RTK Query han6dles that lifecycle.
    const {
        data: projects = [],
        isLoading,
        isError,
    } = useGetProjectsQuery();

    if (isLoading){
        return (
            <main className={styles.page}>
               <header className={styles.header}>
                <div>
                    <p className={styles.eyebrow}>Projects</p>
                    <h1 className={styles.title}>Your Project workspace</h1>
                </div>
               </header>

               <section className={styles.grid}>
                    {Array.from({length: 5}).map((_, index) => (
                        <SkeletonCard key={index}/>
                    ))}
               </section>
            </main>
        );
    }
    if (isError){
        return (
            <main className={styles.page}>
                <header className={styles.header}>
                    <div>
                        <p className={styles.eyebrow}>Projects</p>
                        <h1 className={styles.title}>Your Project workspace</h1>
                    </div>
               </header>
                <p className={styles.error}>Could not load projects.</p>
            </main>
        );
    }

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <div>
                    <p className={styles.eyebrow}>Projects</p>
                    <h1 className={styles.title}> Your project workspace</h1>
                </div>

                <RoleGate allowedRoles={["admin"]}>
                    <Link className={styles.createButton} href={"/projects/create"}>
                    Create project
                    </Link>
                </RoleGate>
            </header>

            <section className={styles.grid}>
                {projects.length === 0 && (
                    <p className={styles.empty}> No project available.</p>
                )}

                {projects && projects.map((project) => (
                    <article key={project.id} className={styles.card}>
                        <h2 className={styles.cardTitle}>{project.name}</h2>
                        <p className={styles.description}>
                            {project.description || "No description provided"}
                        </p>
                        <p className={styles.meta}>Leader ID: {project.leader_id}</p>
                    </article>
                ))};
            </section>
        </main>
    );
}
