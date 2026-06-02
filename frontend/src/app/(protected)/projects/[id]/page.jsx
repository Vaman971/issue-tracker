"use client"

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSelector } from "react-redux";

import {
    useGetProjectQuery,
    useUpdateProjectMutation,
    useAddProjectMemberMutation,
    useGetMemberCandidatesQuery,
    useGetProjectMembersQuery,
    useRemoveProjectMemberMutation,
    useGetProjectIssuesQuery,
} from "@/store/features/projects/projectsApi";
import {
    useCreateLabelMutation,
    useDeleteLabelMutation,
    useGetProjectLabelsQuery,
} from "@/store/features/labels/labelsApi";
import { useGetProjectStatsQuery } from "@/store/features/stats/statsApi";
import { useGetUserLeadersQuery } from "@/store/features/users/usersApi";
import RoleGate from "@/components/RoleGate/page";
import CreateIssueModal from "@/components/CreateIssueModal/page";
import UserSelect from "@/components/UserSelect/page";
import UserMultiSelect from "@/components/UserMultiSelect/page";
import { useDebounce } from "@/hooks/useDebounce";
import styles from "./page.module.css";

const ISSUE_PAGE_SIZE = 10;

const STATUS_COLORS = {
    todo: "#6b7280",
    in_progress: "#2563eb",
    in_review: "#d97706",
    done: "#16a34a",
};

const STATUS_LABELS = {
    todo: "To Do",
    in_progress: "In Progress",
    in_review: "In Review",
    done: "Done",
};

const STATUS_CLASS = {
    todo: styles.statusTodo,
    in_progress: styles.statusInProgress,
    in_review: styles.statusInReview,
    done: styles.statusDone,
};

const PRIORITY_CLASS = {
    low: styles.priorityLow,
    medium: styles.priorityMedium,
    high: styles.priorityHigh,
    critical: styles.priorityCritical,
};

export default function ProjectDetailPage() {
    const { id } = useParams();
    const projectId = Number(id);
    const router = useRouter();
    const user = useSelector((s) => s.auth.user);

    const { data: project, isLoading: loadingProject } = useGetProjectQuery(projectId);
    const { data: stats } = useGetProjectStatsQuery(projectId);
    const { data: members = [], isLoading: loadingMembers } = useGetProjectMembersQuery(projectId);
    const { data: labels = [] } = useGetProjectLabelsQuery(projectId);

    const isAdmin = user?.role === "admin";
    const isAdminOrLeader =
        isAdmin ||
        user?.role === "project_leader" ||
        project?.leader_id === user?.id;

    const { data: candidates = [], isLoading: loadingCandidates } = useGetMemberCandidatesQuery(
        projectId,
        { skip: !isAdminOrLeader }
    );
    const { data: leaders = [], isLoading: loadingLeaders } = useGetUserLeadersQuery(undefined, {
        skip: !isAdmin,
    });

    // Issue filters + pagination
    const [issueStatus, setIssueStatus] = useState("");
    const [issuePriority, setIssuePriority] = useState("");
    const [issueSearch, setIssueSearch] = useState("");
    const [issuePage, setIssuePage] = useState(0);
    const debouncedIssueSearch = useDebounce(issueSearch, 350);

    useEffect(() => {
        setIssuePage(0);
    }, [debouncedIssueSearch, issueStatus, issuePriority]);

    const { data: projectIssues = [], isLoading: loadingIssues } = useGetProjectIssuesQuery({
        projectId,
        status: issueStatus || undefined,
        priority: issuePriority || undefined,
        search: debouncedIssueSearch || undefined,
        skip: issuePage * ISSUE_PAGE_SIZE,
        limit: ISSUE_PAGE_SIZE,
    });

    // Create issue modal
    const [showCreateIssue, setShowCreateIssue] = useState(false);

    // Edit project modal
    const [showEdit, setShowEdit] = useState(false);
    const [editForm, setEditForm] = useState({ name: "", description: "" });
    const [editLeader, setEditLeader] = useState(null);
    const [editMsg, setEditMsg] = useState("");
    const [updateProject, { isLoading: updatingProject }] = useUpdateProjectMutation();

    const handleOpenEdit = () => {
        setEditForm({
            name: project?.name || "",
            description: project?.description || "",
        });
        setEditLeader(leaders.find((l) => l.id === project?.leader_id) || null);
        setEditMsg("");
        setShowEdit(true);
    };

    const handleSaveEdit = async (e) => {
        e.preventDefault();
        try {
            const data = { name: editForm.name, description: editForm.description || null };
            if (editLeader) data.leader_id = editLeader.id;
            await updateProject({ projectId, data }).unwrap();
            setEditMsg("Project updated.");
            setShowEdit(false);
        } catch (err) {
            setEditMsg(err?.data?.detail || "Failed to update project.");
        }
    };

    const [addMember, { isLoading: addingMember }] = useAddProjectMemberMutation();
    const [removeMember] = useRemoveProjectMemberMutation();
    const [createLabel, { isLoading: creatingLabel }] = useCreateLabelMutation();
    const [deleteLabel] = useDeleteLabelMutation();

    const [selectedMemberUsers, setSelectedMemberUsers] = useState([]);
    const [newLabel, setNewLabel] = useState({ name: "", color: "#2563eb" });
    const [memberMsg, setMemberMsg] = useState("");
    const [labelMsg, setLabelMsg] = useState("");

    const handleAddMembers = async (e) => {
        e.preventDefault();
        if (selectedMemberUsers.length === 0) return;
        try {
            for (const u of selectedMemberUsers) {
                await addMember({ projectId, userId: u.id, role: "developer" }).unwrap();
            }
            setSelectedMemberUsers([]);
            setMemberMsg(
                selectedMemberUsers.length === 1
                    ? "Member added."
                    : `${selectedMemberUsers.length} members added.`
            );
        } catch (err) {
            setMemberMsg(err?.data?.detail || "Failed to add member(s).");
        }
    };

    const handleRemoveMember = async (userId) => {
        try {
            await removeMember({ projectId, userId }).unwrap();
        } catch {
            // silent
        }
    };

    const handleCreateLabel = async (e) => {
        e.preventDefault();
        if (!newLabel.name.trim()) return;
        try {
            await createLabel({ projectId, data: newLabel }).unwrap();
            setNewLabel({ name: "", color: "#2563eb" });
            setLabelMsg("Label created.");
        } catch (err) {
            setLabelMsg(err?.data?.detail || "Failed to create label.");
        }
    };

    const handleDeleteLabel = async (labelId) => {
        try {
            await deleteLabel({ projectId, labelId }).unwrap();
        } catch {
            // silent
        }
    };

    if (loadingProject) {
        return (
            <main className={styles.page}>
                <p className={styles.loadingText}>Loading project...</p>
            </main>
        );
    }

    if (!project) {
        return (
            <main className={styles.page}>
                <p className={styles.error}>Project not found.</p>
                <Link href="/projects" className={styles.backLink}>← Back to Projects</Link>
            </main>
        );
    }

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <div>
                    <Link href="/projects" className={styles.backLink}>← Projects</Link>
                    <p className={styles.eyebrow}>Project</p>
                    <h1 className={styles.title}>{project.name}</h1>
                    {project.description && (
                        <p className={styles.description}>{project.description}</p>
                    )}
                </div>
                <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                    {isAdmin && (
                        <button
                            className={styles.editToggle}
                            type="button"
                            onClick={handleOpenEdit}
                        >
                            Edit Project
                        </button>
                    )}
                    <RoleGate allowedRoles={["admin", "project_leader", "developer", "qa"]}>
                        <button
                            type="button"
                            className={styles.createButton}
                            onClick={() => setShowCreateIssue(true)}
                        >
                            + Create Issue
                        </button>
                    </RoleGate>
                </div>
            </header>

            {/* Edit project modal (admin only) */}
            {isAdmin && showEdit && (
                <div
                    className={styles.modalOverlay}
                    onClick={(e) => {
                        if (e.target === e.currentTarget) setShowEdit(false);
                    }}
                >
                    <div className={styles.modalContent}>
                        <div className={styles.modalHeader}>
                            <h2 className={styles.editTitle}>Edit Project</h2>
                        </div>
                        <form onSubmit={handleSaveEdit}>
                            <div className={styles.modalBody}>
                                <div className={styles.editField}>
                                    <label className={styles.editLabel}>Name *</label>
                                    <input
                                        className={styles.editInput}
                                        value={editForm.name}
                                        onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                                        required
                                        minLength={2}
                                        maxLength={255}
                                    />
                                </div>
                                <div className={styles.editField}>
                                    <label className={styles.editLabel}>Description</label>
                                    <textarea
                                        className={styles.editTextarea}
                                        value={editForm.description}
                                        onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                                        maxLength={1000}
                                        rows={3}
                                    />
                                </div>
                                <div className={styles.editField}>
                                    <label className={styles.editLabel}>Project Leader</label>
                                    <UserSelect
                                        users={leaders}
                                        value={editLeader}
                                        onChange={setEditLeader}
                                        loading={loadingLeaders}
                                        placeholder="Search for a leader..."
                                    />
                                </div>
                                {editMsg && <p className={styles.editMsg}>{editMsg}</p>}
                            </div>
                            <div className={styles.modalFooter}>
                                <button
                                    className={styles.saveButton}
                                    type="submit"
                                    disabled={updatingProject}
                                >
                                    {updatingProject ? "Saving..." : "Save Changes"}
                                </button>
                                <button
                                    className={styles.cancelEditButton}
                                    type="button"
                                    onClick={() => setShowEdit(false)}
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Stats */}
            {stats && (
                <section className={styles.statsRow}>
                    <div className={styles.statCard}>
                        <span className={styles.statNumber}>{stats.total_issues}</span>
                        <span className={styles.statLabel}>Total Issues</span>
                    </div>
                    <div className={styles.statCard}>
                        <span className={styles.statNumber} style={{ color: "#16a34a" }}>
                            {stats.issues_by_status?.done || 0}
                        </span>
                        <span className={styles.statLabel}>Done</span>
                    </div>
                    <div className={styles.statCard}>
                        <span className={styles.statNumber} style={{ color: "#2563eb" }}>
                            {stats.issues_by_status?.in_progress || 0}
                        </span>
                        <span className={styles.statLabel}>In Progress</span>
                    </div>
                    <div className={styles.statCard}>
                        <span className={styles.statNumber} style={{ color: "#d97706" }}>
                            {Math.round(stats.completion_rate || 0)}%
                        </span>
                        <span className={styles.statLabel}>Complete</span>
                    </div>
                </section>
            )}

            {/* Status breakdown bar */}
            {stats && stats.total_issues > 0 && (
                <div className={styles.progressBarWrap}>
                    {Object.entries(stats.issues_by_status || {}).map(([st, count]) => (
                        <div
                            key={st}
                            className={styles.progressSegment}
                            style={{
                                width: `${(count / stats.total_issues) * 100}%`,
                                background: STATUS_COLORS[st] || "#e5e7eb",
                            }}
                            title={`${st}: ${count}`}
                        />
                    ))}
                </div>
            )}

            {/* Issues table */}
            <section className={styles.issuesSection}>
                <div className={styles.card}>
                    <h2 className={styles.sectionTitle}>Issues</h2>
                    <div className={styles.issuesFilters}>
                        <input
                            className={styles.filterInput}
                            placeholder="Search issues..."
                            value={issueSearch}
                            onChange={(e) => setIssueSearch(e.target.value)}
                        />
                        <select
                            className={styles.filterSelect}
                            value={issueStatus}
                            onChange={(e) => setIssueStatus(e.target.value)}
                        >
                            <option value="">All Statuses</option>
                            <option value="todo">To Do</option>
                            <option value="in_progress">In Progress</option>
                            <option value="in_review">In Review</option>
                            <option value="done">Done</option>
                        </select>
                        <select
                            className={styles.filterSelect}
                            value={issuePriority}
                            onChange={(e) => setIssuePriority(e.target.value)}
                        >
                            <option value="">All Priorities</option>
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="critical">Critical</option>
                        </select>
                    </div>

                    {loadingIssues ? (
                        <p className={styles.loadingText}>Loading issues...</p>
                    ) : projectIssues.length === 0 ? (
                        <p className={styles.emptyIssues}>No issues found.</p>
                    ) : (
                        <div style={{ overflowX: "auto" }}>
                            <table className={styles.issuesTable}>
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        <th>Title</th>
                                        <th>Status</th>
                                        <th>Priority</th>
                                        <th>Assignees</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {projectIssues.map((issue) => (
                                        <tr
                                            key={issue.id}
                                            className={styles.issueRow}
                                            onClick={() => router.push(`/issues/${issue.id}`)}
                                        >
                                            <td style={{ color: "#9ca3af", fontSize: 13 }}>#{issue.id}</td>
                                            <td className={styles.issueTitle}>{issue.title}</td>
                                            <td>
                                                <span className={`${styles.statusBadge} ${STATUS_CLASS[issue.status]}`}>
                                                    {STATUS_LABELS[issue.status] || issue.status}
                                                </span>
                                            </td>
                                            <td>
                                                <span className={`${styles.priorityBadge} ${PRIORITY_CLASS[issue.priority]}`}>
                                                    {issue.priority}
                                                </span>
                                            </td>
                                            <td style={{ fontSize: 13, color: "#6b7280" }}>
                                                {issue.assignees && issue.assignees.length > 0
                                                    ? issue.assignees.map((a) => a.full_name || a.email).join(", ")
                                                    : "—"}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {(issuePage > 0 || projectIssues.length === ISSUE_PAGE_SIZE) && (
                        <div className={styles.issuePagination}>
                            <button
                                type="button"
                                className={styles.pageBtn}
                                disabled={issuePage === 0}
                                onClick={() => setIssuePage((p) => p - 1)}
                            >
                                ← Previous
                            </button>
                            <span className={styles.pageLabel}>Page {issuePage + 1}</span>
                            <button
                                type="button"
                                className={styles.pageBtn}
                                disabled={projectIssues.length < ISSUE_PAGE_SIZE}
                                onClick={() => setIssuePage((p) => p + 1)}
                            >
                                Next →
                            </button>
                        </div>
                    )}
                </div>
            </section>

            <div className={styles.columns}>
                {/* Members */}
                <section className={styles.card}>
                    <h2 className={styles.sectionTitle}>Members</h2>

                    {loadingMembers ? (
                        <p className={styles.loadingText}>Loading...</p>
                    ) : (
                        <ul className={styles.memberList}>
                            {members.map((m) => (
                                <li key={m.user_id} className={styles.memberItem}>
                                    <div className={styles.memberAvatar}>
                                        {(m.user?.full_name?.[0] || m.user?.email?.[0] || "?").toUpperCase()}
                                    </div>
                                    <div className={styles.memberInfo}>
                                        <span className={styles.memberEmail}>
                                            {m.user?.full_name || m.user?.email || `User #${m.user_id}`}
                                        </span>
                                        <span className={styles.memberRole}>{m.user?.role}</span>
                                    </div>
                                    {isAdminOrLeader && m.user_id !== project.leader_id && (
                                        <button
                                            className={styles.removeButton}
                                            type="button"
                                            onClick={() => handleRemoveMember(m.user_id)}
                                        >
                                            ✕
                                        </button>
                                    )}
                                </li>
                            ))}
                            {members.length === 0 && (
                                <p className={styles.emptyText}>No members yet.</p>
                            )}
                        </ul>
                    )}

                    {isAdminOrLeader && (
                        <form className={styles.addForm} onSubmit={handleAddMembers}>
                            <div style={{ flex: 1 }}>
                                <UserMultiSelect
                                    users={candidates}
                                    value={selectedMemberUsers}
                                    onChange={setSelectedMemberUsers}
                                    loading={loadingCandidates}
                                    placeholder="Search users to add..."
                                />
                            </div>
                            <button
                                className={styles.addButton}
                                type="submit"
                                disabled={addingMember || selectedMemberUsers.length === 0}
                            >
                                {addingMember
                                    ? "Adding..."
                                    : selectedMemberUsers.length > 1
                                    ? `Add ${selectedMemberUsers.length}`
                                    : "Add"}
                            </button>
                            {memberMsg && <p className={styles.formMsg}>{memberMsg}</p>}
                        </form>
                    )}
                </section>

                {/* Labels */}
                <section className={styles.card}>
                    <h2 className={styles.sectionTitle}>Labels</h2>

                    <div className={styles.labelList}>
                        {labels.map((label) => (
                            <div key={label.id} className={styles.labelChip}>
                                <span
                                    className={styles.labelDot}
                                    style={{ background: label.color }}
                                />
                                <span className={styles.labelName}>{label.name}</span>
                                {isAdminOrLeader && (
                                    <button
                                        className={styles.labelRemove}
                                        type="button"
                                        onClick={() => handleDeleteLabel(label.id)}
                                    >
                                        ✕
                                    </button>
                                )}
                            </div>
                        ))}
                        {labels.length === 0 && (
                            <p className={styles.emptyText}>No labels yet.</p>
                        )}
                    </div>

                    {isAdminOrLeader && (
                        <form className={styles.addForm} onSubmit={handleCreateLabel}>
                            <input
                                className={styles.input}
                                type="text"
                                placeholder="Label name"
                                value={newLabel.name}
                                onChange={(e) =>
                                    setNewLabel((prev) => ({ ...prev, name: e.target.value }))
                                }
                            />
                            <input
                                className={styles.colorPicker}
                                type="color"
                                value={newLabel.color}
                                onChange={(e) =>
                                    setNewLabel((prev) => ({ ...prev, color: e.target.value }))
                                }
                            />
                            <button
                                className={styles.addButton}
                                type="submit"
                                disabled={creatingLabel || !newLabel.name.trim()}
                            >
                                Add
                            </button>
                            {labelMsg && <p className={styles.formMsg}>{labelMsg}</p>}
                        </form>
                    )}
                </section>
            </div>

            <CreateIssueModal
                isOpen={showCreateIssue}
                onClose={() => setShowCreateIssue(false)}
                projectId={projectId}
            />
        </main>
    );
}
