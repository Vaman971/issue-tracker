"use client"

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
    useDeleteNotificationMutation,
    useGetNotificationsQuery,
    useMarkAllNotificationsReadMutation,
    useMarkNotificationReadMutation,
} from "@/store/features/notifications/notificationsApi";
import styles from "./page.module.css";

const TYPE_CONFIG = {
    issue_created:        { icon: "🐛", color: "#7c3aed" },
    issue_assigned:       { icon: "👤", color: "#2563eb" },
    issue_commented:      { icon: "💬", color: "#059669" },
    issue_status_changed: { icon: "🔄", color: "#d97706" },
    issue_updated:        { icon: "✏️", color: "#6b7280" },
    project_member_added: { icon: "📁", color: "#0891b2" },
    password_reset:       { icon: "🔒", color: "#dc2626" },
    email_verified:       { icon: "✅", color: "#16a34a" },
};

function timeAgo(dateStr) {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr + "Z").getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return "Just now";
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 7) return `${d}d ago`;
    return new Date(dateStr + "Z").toLocaleDateString();
}

export default function NotificationDrawer({ isOpen, onClose }) {
    const [unreadOnly, setUnreadOnly] = useState(false);
    const [mounted, setMounted] = useState(false);
    const panelRef = useRef(null);

    useEffect(() => { setMounted(true); }, []);

    const { data: notifications = [], isLoading } = useGetNotificationsQuery(
        { unreadOnly },
        { skip: !isOpen }
    );

    const [markRead]  = useMarkNotificationReadMutation();
    const [markAllRead, { isLoading: markingAll }] = useMarkAllNotificationsReadMutation();
    const [deleteNotif] = useDeleteNotificationMutation();

    const unreadCount = notifications.filter((n) => !n.is_read).length;

    // Escape key closes drawer
    useEffect(() => {
        if (!isOpen) return;
        const onKey = (e) => { if (e.key === "Escape") onClose(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [isOpen, onClose]);

    // Lock body scroll when open
    useEffect(() => {
        document.body.style.overflow = isOpen ? "hidden" : "";
        return () => { document.body.style.overflow = ""; };
    }, [isOpen]);

    if (!mounted) return null;

    return createPortal(
        <>
            {/* Blur backdrop */}
            <div
                className={`${styles.backdrop} ${isOpen ? styles.backdropOpen : ""}`}
                onClick={onClose}
                aria-hidden="true"
            />

            {/* Drawer panel */}
            <aside
                ref={panelRef}
                className={`${styles.drawer} ${isOpen ? styles.drawerOpen : ""}`}
                role="dialog"
                aria-modal="true"
                aria-label="Notifications"
            >
                {/* ── Header ── */}
                <div className={styles.header}>
                    <div className={styles.headerRow}>
                        <div className={styles.headerLeft}>
                            <span className={styles.headerIcon} aria-hidden="true">🔔</span>
                            <h2 className={styles.headerTitle}>Notifications</h2>
                            {unreadCount > 0 && (
                                <span className={styles.countBadge}>{unreadCount > 99 ? "99+" : unreadCount}</span>
                            )}
                        </div>
                        <button
                            className={styles.closeBtn}
                            onClick={onClose}
                            aria-label="Close notifications"
                            type="button"
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    </div>

                    <div className={styles.headerControls}>
                        {/* Toggle */}
                        <button
                            type="button"
                            role="switch"
                            aria-checked={unreadOnly}
                            className={styles.toggleWrap}
                            onClick={() => setUnreadOnly((v) => !v)}
                        >
                            <span className={`${styles.track} ${unreadOnly ? styles.trackOn : ""}`}>
                                <span className={styles.thumb} />
                            </span>
                            <span className={styles.toggleLabel}>Unread only</span>
                        </button>

                        {unreadCount > 0 && (
                            <button
                                type="button"
                                className={styles.markAllBtn}
                                onClick={() => markAllRead()}
                                disabled={markingAll}
                            >
                                {markingAll ? "Marking…" : "Mark all read"}
                            </button>
                        )}
                    </div>
                </div>

                {/* ── Body ── */}
                <div className={styles.body}>
                    {isLoading && (
                        <div className={styles.loadingState}>
                            <span className={styles.spinner} />
                            <p>Loading…</p>
                        </div>
                    )}

                    {!isLoading && notifications.length === 0 && (
                        <div className={styles.emptyState}>
                            <span className={styles.emptyIcon} aria-hidden="true">🔕</span>
                            <p className={styles.emptyTitle}>
                                {unreadOnly ? "No unread notifications" : "All caught up!"}
                            </p>
                            <p className={styles.emptyText}>
                                {unreadOnly
                                    ? "Turn off the filter to see all."
                                    : "You have no notifications yet."}
                            </p>
                        </div>
                    )}

                    {!isLoading && notifications.length > 0 && (
                        <ul className={styles.list} role="list">
                            {notifications.map((n) => {
                                const cfg = TYPE_CONFIG[n.type] ?? { icon: "🔔", color: "#6b7280" };
                                return (
                                    <li
                                        key={n.id}
                                        className={n.is_read ? styles.item : styles.itemUnread}
                                    >
                                        <span
                                            className={styles.typeIcon}
                                            style={{
                                                background: cfg.color + "1a",
                                                color: cfg.color,
                                            }}
                                            aria-hidden="true"
                                        >
                                            {cfg.icon}
                                        </span>

                                        <div className={styles.itemBody}>
                                            <p className={styles.itemTitle}>{n.title}</p>
                                            <p className={styles.itemMsg}>{n.message}</p>
                                            <span className={styles.itemTime}>{timeAgo(n.created_at)}</span>
                                        </div>

                                        <div className={styles.itemActions}>
                                            {!n.is_read && (
                                                <button
                                                    type="button"
                                                    className={styles.readBtn}
                                                    title="Mark as read"
                                                    aria-label="Mark as read"
                                                    onClick={() => markRead(n.id)}
                                                >
                                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                                        <polyline points="20 6 9 17 4 12" />
                                                    </svg>
                                                </button>
                                            )}
                                            <button
                                                type="button"
                                                className={styles.deleteBtn}
                                                title="Delete"
                                                aria-label="Delete notification"
                                                onClick={() => deleteNotif(n.id)}
                                            >
                                                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                                                    <line x1="18" y1="6" x2="6" y2="18" />
                                                    <line x1="6" y1="6" x2="18" y2="18" />
                                                </svg>
                                            </button>
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>
            </aside>
        </>,
        document.body
    );
}
