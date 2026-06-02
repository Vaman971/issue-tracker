"use client"

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { useCreateIssueMutation } from "@/store/features/issues/issuesApi";
import { useGetIssueAssigneeCandidatesQuery } from "@/store/features/projects/projectsApi";
import UserMultiSelect from "@/components/UserMultiSelect/page";
import styles from "./page.module.css";

export default function CreateIssueModal({ isOpen, onClose, projectId }) {
    const [mounted, setMounted] = useState(false);
    const [form, setForm] = useState({
        title: "",
        description: "",
        status: "todo",
        priority: "medium",
    });
    const [assignees, setAssignees] = useState([]);
    const [error, setError] = useState("");

    useEffect(() => { setMounted(true); }, []);

    const [createIssue, { isLoading }] = useCreateIssueMutation();
    const { data: candidates = [], isLoading: loadingCandidates } = useGetIssueAssigneeCandidatesQuery(
        projectId,
        { skip: !isOpen || !projectId }
    );

    useEffect(() => {
        if (isOpen) {
            setForm({ title: "", description: "", status: "todo", priority: "medium" });
            setAssignees([]);
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
        if (!form.title.trim() || form.title.length < 3) {
            setError("Title must be at least 3 characters.");
            return;
        }
        setError("");
        try {
            await createIssue({
                title: form.title.trim(),
                description: form.description.trim() || null,
                status: form.status,
                priority: form.priority,
                project_id: projectId,
                assignee_ids: assignees.map((a) => a.id),
            }).unwrap();
            onClose();
        } catch (err) {
            setError(err?.data?.detail || "Failed to create issue.");
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
                aria-label="Create Issue"
            >
                <div className={styles.header}>
                    <h2 className={styles.title}>Create Issue</h2>
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
                            <label className={styles.label}>Title *</label>
                            <input
                                className={styles.input}
                                type="text"
                                value={form.title}
                                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                                placeholder="Brief issue summary..."
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
                                placeholder="Describe the issue in detail..."
                                rows={4}
                                maxLength={2000}
                            />
                        </div>

                        <div className={styles.row}>
                            <div className={styles.field}>
                                <label className={styles.label}>Status</label>
                                <select
                                    className={styles.select}
                                    value={form.status}
                                    onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                                >
                                    <option value="todo">To Do</option>
                                    <option value="in_progress">In Progress</option>
                                    <option value="in_review">In Review</option>
                                    <option value="done">Done</option>
                                </select>
                            </div>

                            <div className={styles.field}>
                                <label className={styles.label}>Priority</label>
                                <select
                                    className={styles.select}
                                    value={form.priority}
                                    onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
                                >
                                    <option value="low">Low</option>
                                    <option value="medium">Medium</option>
                                    <option value="high">High</option>
                                    <option value="critical">Critical</option>
                                </select>
                            </div>
                        </div>

                        <div className={styles.field}>
                            <label className={styles.label}>
                                Assignees
                                {assignees.length > 0 && (
                                    <span className={styles.assigneeCount}>{assignees.length} selected</span>
                                )}
                            </label>
                            <UserMultiSelect
                                users={candidates}
                                value={assignees}
                                onChange={setAssignees}
                                loading={loadingCandidates}
                                placeholder="Search and select assignees..."
                            />
                        </div>

                        {error && <p className={styles.error}>{error}</p>}
                    </div>

                    <div className={styles.footer}>
                        <button type="submit" className={styles.submitBtn} disabled={isLoading}>
                            {isLoading ? "Creating..." : "Create Issue"}
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
