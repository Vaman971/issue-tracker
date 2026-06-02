"use client"

import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { useSelector } from "react-redux";

import { useGetIssueActivityQuery } from "@/store/features/activity/activityApi";
import {
    useDeleteAttachmentMutation,
    useGetAttachmentsQuery,
    useUploadAttachmentMutation,
} from "@/store/features/attachments/attachmentsApi";
import {
    useCreateCommentMutation,
    useDeleteCommentMutation,
    useGetCommentsQuery,
    useUpdateCommentMutation,
} from "@/store/features/comments/commentsApi";
import { useGetIssueQuery, useUpdateIssueMutation } from "@/store/features/issues/issuesApi";
import {
    useAddIssueLabelMutation,
    useGetProjectLabelsQuery,
    useRemoveIssueLabelMutation,
} from "@/store/features/labels/labelsApi";
import {
    useGetProjectQuery,
    useGetIssueAssigneeCandidatesQuery,
} from "@/store/features/projects/projectsApi";
import UserSelect from "@/components/UserSelect/page";
import styles from "./page.module.css";

const PRIORITY_COLORS = {
    low: "#6b7280",
    medium: "#2563eb",
    high: "#d97706",
    critical: "#dc2626",
};

const STATUS_LABELS = {
    todo: "To Do",
    in_progress: "In Progress",
    in_review: "In Review",
    done: "Done",
};

const ACTION_LABELS = {
    created: "created the issue",
    status_changed: "changed status",
    priority_changed: "changed priority",
    assigned: "changed assignee",
    unassigned: "unassigned",
    comment_added: "added a comment",
    comment_deleted: "deleted a comment",
    attachment_added: "added an attachment",
    attachment_deleted: "removed an attachment",
    label_added: "added a label",
    label_removed: "removed a label",
    title_changed: "changed the title",
};

function formatDate(dateStr) {
    if (!dateStr) return "";
    return new Date(dateStr + "Z").toLocaleString();
}

function PersonRow({ person, onRemove, canRemove }) {
    const initial = (person?.full_name?.[0] || person?.email?.[0] || "?").toUpperCase();
    return (
        <div className={styles.personRow}>
            <div className={styles.personAvatar}>{initial}</div>
            <span className={styles.personName}>{person?.full_name || person?.email}</span>
            {canRemove && (
                <button
                    className={styles.removeAssigneeBtn}
                    type="button"
                    onClick={() => onRemove(person.id)}
                    title="Remove assignee"
                >
                    ✕
                </button>
            )}
        </div>
    );
}

export default function IssueDetailPage() {
    const { id } = useParams();
    const issueId = Number(id);
    const user = useSelector((s) => s.auth.user);

    const { data: issue, isLoading: loadingIssue } = useGetIssueQuery(issueId);
    const { data: comments = [] } = useGetCommentsQuery(issueId);
    const { data: attachments = [] } = useGetAttachmentsQuery(issueId);
    const { data: activity = [] } = useGetIssueActivityQuery({ issueId });

    const projectId = issue?.project_id;
    const { data: project } = useGetProjectQuery(projectId, { skip: !projectId });
    const { data: projectLabels = [] } = useGetProjectLabelsQuery(projectId, { skip: !projectId });
    const { data: assigneeCandidates = [] } = useGetIssueAssigneeCandidatesQuery(projectId, {
        skip: !projectId,
    });

    const [updateIssue] = useUpdateIssueMutation();
    const [createComment, { isLoading: postingComment }] = useCreateCommentMutation();
    const [updateComment] = useUpdateCommentMutation();
    const [deleteComment] = useDeleteCommentMutation();
    const [uploadAttachment, { isLoading: uploading }] = useUploadAttachmentMutation();
    const [deleteAttachment] = useDeleteAttachmentMutation();
    const [addLabel] = useAddIssueLabelMutation();
    const [removeLabel] = useRemoveIssueLabelMutation();

    const [newComment, setNewComment] = useState("");
    const [replyTo, setReplyTo] = useState(null);
    const [editingComment, setEditingComment] = useState(null);
    const [editContent, setEditContent] = useState("");
    const [activeTab, setActiveTab] = useState("comments");
    const fileRef = useRef(null);

    const isFullEditor =
        user?.role === "admin" ||
        (user?.role === "project_leader" && project?.leader_id === user?.id);

    const handleStatusChange = async (e) => {
        await updateIssue({ issueId, data: { status: e.target.value } });
    };

    const handlePriorityChange = async (e) => {
        await updateIssue({ issueId, data: { priority: e.target.value } });
    };

    const handleAddAssignee = async (user) => {
        if (!user) return;
        const currentIds = (issue?.assignees || []).map((a) => a.id);
        if (currentIds.includes(user.id)) return;
        await updateIssue({ issueId, data: { assignee_ids: [...currentIds, user.id] } });
    };

    const handleRemoveAssignee = async (assigneeId) => {
        const currentIds = (issue?.assignees || []).map((a) => a.id).filter((i) => i !== assigneeId);
        await updateIssue({ issueId, data: { assignee_ids: currentIds } });
    };

    const handleSubmitComment = async (e) => {
        e.preventDefault();
        if (!newComment.trim()) return;
        await createComment({
            issueId,
            data: { content: newComment.trim(), parent_id: replyTo },
        });
        setNewComment("");
        setReplyTo(null);
    };

    const handleEditSave = async (commentId) => {
        if (!editContent.trim()) return;
        await updateComment({ issueId, commentId, data: { content: editContent.trim() } });
        setEditingComment(null);
        setEditContent("");
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        await uploadAttachment({ issueId, formData });
        e.target.value = "";
    };

    const handleLabelToggle = async (label) => {
        const isAttached = issue?.labels?.some((l) => l.id === label.id);
        if (isAttached) {
            await removeLabel({ issueId, labelId: label.id });
        } else {
            await addLabel({ issueId, labelId: label.id });
        }
    };

    const rootComments = comments.filter((c) => !c.parent_id);
    const childComments = (parentId) => comments.filter((c) => c.parent_id === parentId);

    // Candidates not already assigned
    const unassignedCandidates = assigneeCandidates.filter(
        (c) => !(issue?.assignees || []).some((a) => a.id === c.id)
    );

    if (loadingIssue) {
        return (
            <main className={styles.page}>
                <p className={styles.loadingText}>Loading issue...</p>
            </main>
        );
    }

    if (!issue) {
        return (
            <main className={styles.page}>
                <p className={styles.error}>Issue not found.</p>
                <Link href="/issues" className={styles.backLink}>← Back to Issues</Link>
            </main>
        );
    }

    return (
        <main className={styles.page}>
            {/* Header */}
            <div className={styles.breadcrumb}>
                <Link href="/issues" className={styles.backLink}>← Issues</Link>
                {issue.project_id && (
                    <>
                        <span className={styles.breadcrumbSep}>/</span>
                        <Link href={`/projects/${issue.project_id}`} className={styles.backLink}>
                            {project?.name || `Project #${issue.project_id}`}
                        </Link>
                    </>
                )}
            </div>

            <div className={styles.layout}>
                {/* Main content */}
                <div className={styles.main}>
                    <div className={styles.issueHeader}>
                        <h1 className={styles.issueTitle}>{issue.title}</h1>
                        <div className={styles.issueMeta}>
                            <span
                                className={styles.priorityBadge}
                                style={{ background: PRIORITY_COLORS[issue.priority] + "22", color: PRIORITY_COLORS[issue.priority] }}
                            >
                                {issue.priority}
                            </span>
                            <span className={styles.statusBadge}>
                                {STATUS_LABELS[issue.status]}
                            </span>
                        </div>
                    </div>

                    {issue.description && (
                        <div className={styles.descriptionBox}>
                            <p className={styles.descriptionText}>{issue.description}</p>
                        </div>
                    )}

                    {/* Labels on issue */}
                    {issue.labels && issue.labels.length > 0 && (
                        <div className={styles.labelRow}>
                            {issue.labels.map((l) => (
                                <span
                                    key={l.id}
                                    className={styles.labelChip}
                                    style={{ borderColor: l.color, color: l.color }}
                                >
                                    {l.name}
                                </span>
                            ))}
                        </div>
                    )}

                    {/* Tabs */}
                    <div className={styles.tabs}>
                        {["comments", "attachments", "activity"].map((tab) => (
                            <button
                                key={tab}
                                className={activeTab === tab ? styles.tabActive : styles.tab}
                                type="button"
                                onClick={() => setActiveTab(tab)}
                            >
                                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                                {tab === "comments" && comments.length > 0 && (
                                    <span className={styles.tabCount}>{comments.length}</span>
                                )}
                                {tab === "attachments" && attachments.length > 0 && (
                                    <span className={styles.tabCount}>{attachments.length}</span>
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Comments tab */}
                    {activeTab === "comments" && (
                        <div className={styles.tabContent}>
                            {rootComments.length === 0 && (
                                <p className={styles.emptyText}>No comments yet. Be the first!</p>
                            )}

                            {rootComments.map((comment) => (
                                <div key={comment.id} className={styles.commentThread}>
                                    <div className={styles.comment}>
                                        <div className={styles.commentAvatar}>
                                            {comment.author?.full_name?.[0]?.toUpperCase() ||
                                                comment.author?.email?.[0]?.toUpperCase() ||
                                                "?"}
                                        </div>
                                        <div className={styles.commentBody}>
                                            <div className={styles.commentHeader}>
                                                <span className={styles.commentAuthor}>
                                                    {comment.author?.full_name || comment.author?.email}
                                                </span>
                                                <span className={styles.commentDate}>
                                                    {formatDate(comment.created_at)}
                                                </span>
                                            </div>

                                            {editingComment === comment.id ? (
                                                <div className={styles.editBox}>
                                                    <textarea
                                                        className={styles.commentInput}
                                                        rows={3}
                                                        value={editContent}
                                                        onChange={(e) => setEditContent(e.target.value)}
                                                    />
                                                    <div className={styles.editActions}>
                                                        <button
                                                            className={styles.saveButton}
                                                            type="button"
                                                            onClick={() => handleEditSave(comment.id)}
                                                        >
                                                            Save
                                                        </button>
                                                        <button
                                                            className={styles.cancelButton}
                                                            type="button"
                                                            onClick={() => setEditingComment(null)}
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <p className={styles.commentContent}>{comment.content}</p>
                                            )}

                                            <div className={styles.commentActions}>
                                                <button
                                                    className={styles.actionLink}
                                                    type="button"
                                                    onClick={() => {
                                                        setReplyTo(comment.id);
                                                        setNewComment("");
                                                    }}
                                                >
                                                    Reply
                                                </button>
                                                {(comment.author_id === user?.id ||
                                                    user?.role === "admin") && (
                                                    <>
                                                        <button
                                                            className={styles.actionLink}
                                                            type="button"
                                                            onClick={() => {
                                                                setEditingComment(comment.id);
                                                                setEditContent(comment.content);
                                                            }}
                                                        >
                                                            Edit
                                                        </button>
                                                        <button
                                                            className={styles.actionLinkDanger}
                                                            type="button"
                                                            onClick={() =>
                                                                deleteComment({ issueId, commentId: comment.id })
                                                            }
                                                        >
                                                            Delete
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Replies */}
                                    {childComments(comment.id).map((reply) => (
                                        <div key={reply.id} className={styles.reply}>
                                            <div className={styles.comment}>
                                                <div className={styles.commentAvatar} style={{ width: 28, height: 28, fontSize: 12 }}>
                                                    {reply.author?.email?.[0]?.toUpperCase() || "?"}
                                                </div>
                                                <div className={styles.commentBody}>
                                                    <div className={styles.commentHeader}>
                                                        <span className={styles.commentAuthor}>
                                                            {reply.author?.full_name || reply.author?.email}
                                                        </span>
                                                        <span className={styles.commentDate}>
                                                            {formatDate(reply.created_at)}
                                                        </span>
                                                    </div>
                                                    <p className={styles.commentContent}>{reply.content}</p>
                                                    <div className={styles.commentActions}>
                                                        {(reply.author_id === user?.id ||
                                                            user?.role === "admin") && (
                                                            <button
                                                                className={styles.actionLinkDanger}
                                                                type="button"
                                                                onClick={() =>
                                                                    deleteComment({ issueId, commentId: reply.id })
                                                                }
                                                            >
                                                                Delete
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ))}

                            {/* New comment form */}
                            <form className={styles.commentForm} onSubmit={handleSubmitComment}>
                                {replyTo && (
                                    <div className={styles.replyBanner}>
                                        Replying to comment #{replyTo}&nbsp;
                                        <button
                                            className={styles.cancelButton}
                                            type="button"
                                            onClick={() => setReplyTo(null)}
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                )}
                                <textarea
                                    className={styles.commentInput}
                                    rows={3}
                                    placeholder={replyTo ? "Write a reply..." : "Write a comment..."}
                                    value={newComment}
                                    onChange={(e) => setNewComment(e.target.value)}
                                />
                                <button
                                    className={styles.submitButton}
                                    type="submit"
                                    disabled={postingComment || !newComment.trim()}
                                >
                                    {postingComment ? "Posting..." : "Post Comment"}
                                </button>
                            </form>
                        </div>
                    )}

                    {/* Attachments tab */}
                    {activeTab === "attachments" && (
                        <div className={styles.tabContent}>
                            <div className={styles.attachmentList}>
                                {attachments.length === 0 && (
                                    <p className={styles.emptyText}>No attachments yet.</p>
                                )}
                                {attachments.map((att) => (
                                    <div key={att.id} className={styles.attachmentItem}>
                                        <div className={styles.attachmentIcon}>📎</div>
                                        <div className={styles.attachmentInfo}>
                                            <span className={styles.attachmentName}>
                                                {att.original_filename}
                                            </span>
                                            <span className={styles.attachmentMeta}>
                                                {att.mime_type} &middot;{" "}
                                                {(att.file_size_bytes / 1024).toFixed(1)} KB
                                            </span>
                                        </div>
                                        <div className={styles.attachmentActions}>
                                            <a
                                                href={`/api/issues/${issueId}/attachments/${att.id}/url`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className={styles.downloadLink}
                                            >
                                                Download
                                            </a>
                                            <button
                                                className={styles.actionLinkDanger}
                                                type="button"
                                                onClick={() => deleteAttachment({ issueId, attachmentId: att.id })}
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className={styles.uploadRow}>
                                <button
                                    className={styles.uploadButton}
                                    type="button"
                                    disabled={uploading}
                                    onClick={() => fileRef.current?.click()}
                                >
                                    {uploading ? "Uploading..." : "📎 Attach File"}
                                </button>
                                <input
                                    ref={fileRef}
                                    type="file"
                                    style={{ display: "none" }}
                                    onChange={handleFileUpload}
                                />
                                <span className={styles.uploadHint}>
                                    Max 10 MB · Images, PDF, Office docs
                                </span>
                            </div>
                        </div>
                    )}

                    {/* Activity tab */}
                    {activeTab === "activity" && (
                        <div className={styles.tabContent}>
                            {activity.length === 0 && (
                                <p className={styles.emptyText}>No activity yet.</p>
                            )}
                            <ul className={styles.activityList}>
                                {activity.map((entry) => (
                                    <li key={entry.id} className={styles.activityItem}>
                                        <div className={styles.activityDot} />
                                        <div className={styles.activityContent}>
                                            <span className={styles.activityActor}>
                                                {entry.actor?.full_name || entry.actor?.email || "Someone"}
                                            </span>{" "}
                                            <span className={styles.activityAction}>
                                                {ACTION_LABELS[entry.action] || entry.action}
                                            </span>
                                            {entry.new_value && (
                                                <span className={styles.activityValue}>
                                                    {" "}→ {entry.new_value}
                                                </span>
                                            )}
                                            <span className={styles.activityDate}>
                                                {formatDate(entry.created_at)}
                                            </span>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>

                {/* Sidebar */}
                <aside className={styles.sidebar}>

                    {/* People card */}
                    <div className={styles.sideCard}>
                        <h3 className={styles.sideTitle}>People</h3>

                        {/* Creator */}
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Created by</span>
                            {issue.creator ? (
                                <PersonRow person={issue.creator} canRemove={false} />
                            ) : (
                                <span className={styles.detailValue}>User #{issue.creator_id}</span>
                            )}
                        </div>

                        {/* Project leader */}
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Project Leader</span>
                            {project?.leader ? (
                                <PersonRow person={project.leader} canRemove={false} />
                            ) : (
                                <span className={styles.detailValue}>—</span>
                            )}
                        </div>

                        {/* Assignees */}
                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Assignees</span>
                            {issue.assignees && issue.assignees.length > 0 ? (
                                issue.assignees.map((a) => (
                                    <PersonRow
                                        key={a.id}
                                        person={a}
                                        canRemove={isFullEditor}
                                        onRemove={handleRemoveAssignee}
                                    />
                                ))
                            ) : (
                                <span className={styles.detailValue} style={{ color: "#9ca3af" }}>Unassigned</span>
                            )}

                            {isFullEditor && unassignedCandidates.length > 0 && (
                                <div className={styles.addAssigneeRow}>
                                    <UserSelect
                                        users={unassignedCandidates}
                                        value={null}
                                        onChange={handleAddAssignee}
                                        placeholder="Add assignee..."
                                    />
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Details card */}
                    <div className={styles.sideCard}>
                        <h3 className={styles.sideTitle}>Details</h3>

                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Status</span>
                            <select
                                className={styles.detailSelect}
                                value={issue.status}
                                onChange={handleStatusChange}
                            >
                                <option value="todo">To Do</option>
                                <option value="in_progress">In Progress</option>
                                <option value="in_review">In Review</option>
                                <option value="done">Done</option>
                            </select>
                        </div>

                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Priority</span>
                            <select
                                className={styles.detailSelect}
                                value={issue.priority}
                                onChange={handlePriorityChange}
                            >
                                <option value="low">Low</option>
                                <option value="medium">Medium</option>
                                <option value="high">High</option>
                                <option value="critical">Critical</option>
                            </select>
                        </div>

                        <div className={styles.detailRow}>
                            <span className={styles.detailLabel}>Created</span>
                            <span className={styles.detailValue}>{formatDate(issue?.created_at)}</span>
                        </div>
                    </div>

                    {/* Labels management */}
                    {projectLabels.length > 0 && (
                        <div className={styles.sideCard}>
                            <h3 className={styles.sideTitle}>Labels</h3>
                            <div className={styles.labelsGrid}>
                                {projectLabels.map((label) => {
                                    const attached = issue.labels?.some((l) => l.id === label.id);
                                    return (
                                        <button
                                            key={label.id}
                                            className={attached ? styles.labelBtnOn : styles.labelBtnOff}
                                            type="button"
                                            style={attached ? { background: label.color + "22", color: label.color, borderColor: label.color } : {}}
                                            onClick={() => handleLabelToggle(label)}
                                        >
                                            <span
                                                className={styles.labelDot}
                                                style={{ background: label.color }}
                                            />
                                            {label.name}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </aside>
            </div>
        </main>
    );
}
