"use client"

import { useEffect, useRef, useState } from "react";
import styles from "./page.module.css";

export default function UserSelect({
    users = [],
    value,
    onChange,
    loading = false,
    placeholder = "Search for a user...",
}) {
    const [query, setQuery] = useState("");
    const [open, setOpen] = useState(false);
    const containerRef = useRef(null);
    const inputRef = useRef(null);

    const filtered = users.filter(
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
        onChange(user);
        setOpen(false);
        setQuery("");
    };

    const handleClear = (e) => {
        e.stopPropagation();
        onChange(null);
    };

    if (value) {
        return (
            <div className={styles.selectedWrap}>
                <div className={styles.selectedUser}>
                    <div className={styles.avatar}>
                        {(value.full_name?.[0] || value.email?.[0] || "?").toUpperCase()}
                    </div>
                    <div className={styles.userInfo}>
                        <span className={styles.userName}>{value.full_name || value.email}</span>
                        {value.full_name && <span className={styles.userEmail}>{value.email}</span>}
                    </div>
                </div>
                <button
                    type="button"
                    className={styles.clearBtn}
                    onClick={handleClear}
                    aria-label="Clear selection"
                >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                </button>
            </div>
        );
    }

    return (
        <div className={styles.container} ref={containerRef}>
            <div className={styles.inputWrap}>
                <svg className={styles.searchIcon} width="14" height="14" viewBox="0 0 20 20" fill="none">
                    <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="2" />
                    <line x1="14.5" y1="14.5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
                <input
                    ref={inputRef}
                    className={styles.input}
                    value={query}
                    onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
                    onFocus={() => setOpen(true)}
                    placeholder={loading ? "Loading users..." : placeholder}
                    disabled={loading}
                    autoComplete="off"
                    aria-label="Search users"
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
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => handleSelect(u)}
                            >
                                <div className={styles.avatar}>
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
                        <li className={styles.noOptions}>
                            {loading ? "Loading..." : query ? "No users found" : "No users available"}
                        </li>
                    )}
                </ul>
            )}
        </div>
    );
}
