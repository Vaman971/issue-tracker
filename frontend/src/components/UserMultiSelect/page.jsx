"use client"

import { useEffect, useRef, useState } from "react";
import styles from "./page.module.css";

export default function UserMultiSelect({
    users = [],
    value = [],
    onChange,
    loading = false,
    placeholder = "Search users...",
}) {
    const [query, setQuery] = useState("");
    const [open, setOpen] = useState(false);
    const containerRef = useRef(null);
    const inputRef = useRef(null);

    const selectedIds = new Set(value.map((u) => u.id));

    const filtered = users
        .filter((u) => !selectedIds.has(u.id))
        .filter(
            (u) =>
                (u.full_name || "").toLowerCase().includes(query.toLowerCase()) ||
                u.email.toLowerCase().includes(query.toLowerCase())
        );

    useEffect(() => {
        const handler = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setOpen(false);
                setQuery("");
            }
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    const handleSelect = (user) => {
        onChange([...value, user]);
        setQuery("");
        inputRef.current?.focus();
    };

    const handleRemove = (userId, e) => {
        e.stopPropagation();
        onChange(value.filter((u) => u.id !== userId));
    };

    const noOptionsText = () => {
        if (loading) return "Loading...";
        if (query) return "No users found";
        if (selectedIds.size > 0 && filtered.length === 0) return "All available users selected";
        return "No users available";
    };

    return (
        <div className={styles.container} ref={containerRef}>
            <div
                className={`${styles.inputWrap} ${open ? styles.inputWrapOpen : ""}`}
                onClick={() => { setOpen(true); inputRef.current?.focus(); }}
            >
                {value.map((u) => (
                    <span key={u.id} className={styles.pill}>
                        <span className={styles.pillAvatar} aria-hidden="true">
                            {(u.full_name?.[0] || u.email?.[0] || "?").toUpperCase()}
                        </span>
                        <span className={styles.pillName}>{u.full_name || u.email}</span>
                        <button
                            type="button"
                            className={styles.pillRemove}
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={(e) => handleRemove(u.id, e)}
                            aria-label={`Remove ${u.full_name || u.email}`}
                        >
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    </span>
                ))}
                <input
                    ref={inputRef}
                    className={styles.input}
                    value={query}
                    onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
                    onFocus={() => setOpen(true)}
                    placeholder={value.length === 0 ? (loading ? "Loading users..." : placeholder) : ""}
                    disabled={loading}
                    autoComplete="off"
                    aria-label="Search users to add"
                />
            </div>

            {open && (
                <ul className={styles.dropdown} role="listbox">
                    {filtered.length > 0 ? (
                        filtered.map((u) => (
                            <li
                                key={u.id}
                                className={styles.option}
                                role="option"
                                aria-selected={false}
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => handleSelect(u)}
                            >
                                <div className={styles.avatar} aria-hidden="true">
                                    {(u.full_name?.[0] || u.email?.[0] || "?").toUpperCase()}
                                </div>
                                <div className={styles.userInfo}>
                                    <span className={styles.userName}>{u.full_name || u.email}</span>
                                    {u.full_name && <span className={styles.userEmail}>{u.email}</span>}
                                </div>
                                {u.role && <span className={styles.userRole}>{u.role}</span>}
                            </li>
                        ))
                    ) : (
                        <li className={styles.noOptions}>{noOptionsText()}</li>
                    )}
                </ul>
            )}
        </div>
    );
}
