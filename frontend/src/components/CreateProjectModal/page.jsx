"use client"

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { useCreateProjectMutation } from "@/store/features/projects/projectsApi";
import { useGetUserLeadersQuery } from "@/store/features/users/usersApi";
import UserSelect from "@/components/UserSelect/page";
import styles from "./page.module.css";

export default function CreateProjectModal({ isOpen, onClose }) {
    const [mounted, setMounted] = useState(false);
    const [form, setForm] = useState({ name: "", description: "" });
    const [leader, setLeader] = useState(null);
    const [error, setError] = useState("");

    useEffect(() => { setMounted(true); }, []);

    const [createProject, { isLoading }] = useCreateProjectMutation();
    const { data: leaders = [], isLoading: loadingLeaders } = useGetUserLeadersQuery(undefined, {
        skip: !isOpen,
    });

    useEffect(() => {
        if (isOpen) {
            setForm({ name: "", description: "" });
            setLeader(null);
            setError("");
        }
    }, [isOpen]);

    useEffect(() => {
        if (!isOpen) return;
        const onKey = (e) => { if (e.key === "Escape") onClose(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [isOpen, onClose]);

    useEffect(() => {
        document.body.style.overflow = isOpen ? "hidden" : "";
        return () => { document.body.style.overflow = ""; };
    }, [isOpen]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.name.trim() || form.name.length < 2) {
            setError("Project name must be at least 2 characters.");
            return;
        }
        if (!leader) {
            setError("Please select a project leader.");
            return;
        }
        setError("");
        try {
            await createProject({
                name: form.name.trim(),
                description: form.description.trim() || null,
                leader_id: leader.id,
            }).unwrap();
            onClose();
        } catch (err) {
            setError(err?.data?.detail || "Failed to create project.");
        }
    };

    if (!mounted) return null;

    return createPortal(
        <>
            <div
                className={`${styles.backdrop} ${isOpen ? styles.backdropOpen : ""}`}
                onClick={onClose}
                aria-hidden="true"
            />
            <div
                className={`${styles.modal} ${isOpen ? styles.modalOpen : ""}`}
                role="dialog"
                aria-modal="true"
                aria-label="Create Project"
            >
                <div className={styles.header}>
                    <h2 className={styles.title}>Create Project</h2>
                    <button
                        type="button"
                        className={styles.closeBtn}
                        onClick={onClose}
                        aria-label="Close"
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    <div className={styles.body}>
                        <div className={styles.field}>
                            <label className={styles.label}>Project Name *</label>
                            <input
                                className={styles.input}
                                type="text"
                                value={form.name}
                                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                                placeholder="Enter project name..."
                                maxLength={255}
                                autoFocus
                            />
                        </div>

                        <div className={styles.field}>
                            <label className={styles.label}>Description</label>
                            <textarea
                                className={styles.textarea}
                                value={form.description}
                                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                                placeholder="What is this project about?"
                                rows={3}
                                maxLength={1000}
                            />
                        </div>

                        <div className={styles.field}>
                            <label className={styles.label}>Project Leader *</label>
                            <UserSelect
                                users={leaders}
                                value={leader}
                                onChange={setLeader}
                                loading={loadingLeaders}
                                placeholder="Search for a leader..."
                            />
                        </div>

                        {error && <p className={styles.error}>{error}</p>}
                    </div>

                    <div className={styles.footer}>
                        <button type="submit" className={styles.submitBtn} disabled={isLoading}>
                            {isLoading ? "Creating..." : "Create Project"}
                        </button>
                        <button type="button" className={styles.cancelBtn} onClick={onClose}>
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </>,
        document.body
    );
}
