"use client"

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
    useDeleteConversationMutation,
    useGetConversationMessagesQuery,
    useGetConversationsQuery,
    useRenameConversationMutation,
    useSendChatMessageMutation,
} from "@/store/features/rag/ragApi";
import styles from "./page.module.css";

// which conversation to reopen on the next load
const ACTIVE_CONVERSATION_KEY = "ragActiveConversationId";

/**
 * Turn a failed request into something worth showing a user.
 *
 * The backend already writes readable messages for the failures it knows
 * about ("The answer model is unavailable right now"), whether they arrive as
 * an HTTP status before the stream or as an error event partway through it.
 * Those are used as-is; only the cases it cannot describe get a fallback.
 */
function readError(error) {
    const detail = error?.data?.detail;

    // a string is the backend talking; an array is a validation payload,
    // which is for developers rather than users
    if (typeof detail === "string") {
        return detail;
    }

    if (error?.status === "FETCH_ERROR") {
        return "Could not reach the assistant. Check your connection and try again.";
    }

    return "Something went wrong. Please try again.";
}

/**
 * Relative time, matching NotificationDrawer.
 *
 * The "Z" matters: the API serialises naive UTC timestamps, so without it the
 * browser reads them as local time and everything looks hours out.
 */
function timeAgo(value) {
    if (!value) return "";

    const seconds = Math.floor((Date.now() - new Date(value + "Z").getTime()) / 1000);
    if (seconds < 60) return "Just now";

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;

    return new Date(value + "Z").toLocaleDateString();
}

export default function RagChatWidget() {
    const [isOpen, setIsOpen] = useState(false);
    const [mounted, setMounted] = useState(false);

    // "chat" shows the current conversation, "history" the list of past ones
    const [view, setView] = useState("chat");

    // null means an unsaved conversation: the backend creates one on the first
    // question and returns its id
    const [activeConversationId, setActiveConversationId] = useState(null);

    const [messages, setMessages] = useState([]);
    const [draft, setDraft] = useState("");

    // the answer currently arriving, token by token; separate from `messages`
    // so a half-written reply is never mistaken for a finished one
    const [streamingText, setStreamingText] = useState("");
    const [error, setError] = useState(null);

    // the conversation whose title is being edited in place, and the text in
    // that input. null means no row is in edit mode.
    const [editingId, setEditingId] = useState(null);
    const [titleDraft, setTitleDraft] = useState("");

    const [sendChatMessage, { isLoading }] = useSendChatMessageMutation();
    const [renameConversation] = useRenameConversationMutation();
    const [deleteConversation] = useDeleteConversationMutation();

    const listRef = useRef(null);
    const inputRef = useRef(null);
    const titleInputRef = useRef(null);

    // keys for messages that exist only locally, until the saved
    // transcript replaces them with rows that carry real ids
    const localKey = useRef(0);
    const nextLocalKey = () => `local-${(localKey.current += 1)}`;

    useEffect(() => { setMounted(true); }, []);

    // ── Restore the last conversation on load ──
    useEffect(() => {
        const stored = localStorage.getItem(ACTIVE_CONVERSATION_KEY);

        if (stored) {
            setActiveConversationId(stored);
        }
    }, []);

    useEffect(() => {
        if (activeConversationId) {
            localStorage.setItem(ACTIVE_CONVERSATION_KEY, activeConversationId);
        } else {
            localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
        }
    }, [activeConversationId]);

    // ── Server state ──
    const {
        data: transcript,
        isFetching: isLoadingTranscript,
        error: transcriptError,
    } = useGetConversationMessagesQuery(activeConversationId, {
        skip: !activeConversationId || !isOpen,
    });

    const {
        data: conversations = [],
        isFetching: isLoadingConversations,
    } = useGetConversationsQuery(
        { skip: 0, limit: 20 },
        { skip: !isOpen || view !== "history" },
    );

    /*
    The transcript is the source of truth for a saved conversation, so it
    replaces the local copy rather than merging into it — the two cannot
    disagree, since every turn goes through this component.

    Not while a send is in flight: the refetch that a completed send triggers
    would otherwise land mid-stream and wipe the question the user just asked.
    */
    useEffect(() => {
        if (!transcript || isLoading) return;

        setMessages(
            transcript.map((message) => ({
                key: message.id,
                role: message.role,
                content: message.content,
            })),
        );
    }, [transcript, isLoading]);

    // a stored id can outlive the conversation it points at — deleted, or
    // belonging to an account that has since signed out here
    useEffect(() => {
        if (transcriptError?.status === 404) {
            setActiveConversationId(null);
            setMessages([]);
        }
    }, [transcriptError]);

    // ── Scroll and focus ──
    useEffect(() => {
        const list = listRef.current;

        if (list && view === "chat") {
            list.scrollTop = list.scrollHeight;
        }
    }, [messages, streamingText, isOpen, view]);

    useEffect(() => {
        if (isOpen && view === "chat") {
            inputRef.current?.focus();
        }
    }, [isOpen, view]);

    useEffect(() => {
        if (!isOpen) return;

        const onKey = (event) => {
            if (event.key !== "Escape") return;

            // innermost first: Escape abandons a rename before it closes the
            // panel. Clearing editingId unmounts the input, and React fires no
            // blur on unmount, so the edit is discarded rather than saved.
            if (editingId) {
                setEditingId(null);
                return;
            }

            setIsOpen(false);
        };

        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [isOpen, editingId]);

    // select the existing title so typing replaces it
    useEffect(() => {
        if (editingId) {
            titleInputRef.current?.focus();
            titleInputRef.current?.select();
        }
    }, [editingId]);

    // ── Actions ──
    const startNewConversation = () => {
        setActiveConversationId(null);
        setMessages([]);
        setStreamingText("");
        setError(null);
        setView("chat");
    };

    const openConversation = (conversationId) => {
        // cleared first so the previous conversation is not left on screen
        // while this one loads
        setMessages([]);
        setStreamingText("");
        setError(null);
        setActiveConversationId(conversationId);
        setView("chat");
    };

    const startEditing = (conversation) => {
        setEditingId(conversation.id);
        setTitleDraft(conversation.title || "");
    };

    /**
     * Save the edited title.
     *
     * Called from onBlur, which covers both ways of finishing. Enter blurs the
     * input rather than saving directly, so the save happens in exactly one
     * place and cannot run twice.
     */
    const commitTitle = async () => {
        const conversationId = editingId;

        if (!conversationId) return;

        const title = titleDraft.trim();
        const current = conversations.find(
            (item) => item.id === conversationId,
        )?.title ?? "";

        setEditingId(null);

        // nothing worth a request: unchanged, or emptied — and the backend
        // rejects a blank title anyway
        if (!title || title === current) return;

        await renameConversation({ conversationId, title });
    };

    const handleTitleKeyDown = (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            event.currentTarget.blur();
        }
    };

    const handleDeleteConversation = async (conversationId) => {
        await deleteConversation(conversationId);

        // the conversation on screen just went away; start fresh rather than
        // leaving the widget pointing at a row that no longer exists
        if (conversationId === activeConversationId) {
            setActiveConversationId(null);
            setMessages([]);
        }
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        const question = draft.trim();

        if (!question || isLoading) return;

        setDraft("");
        setError(null);
        setStreamingText("");
        setMessages((current) => [
            ...current,
            { key: nextLocalKey(), role: "user", content: question },
        ]);

        const result = await sendChatMessage({
            question,
            conversationId: activeConversationId,
            onDelta: (_chunk, textSoFar) => setStreamingText(textSoFar),
        });

        setStreamingText("");

        if (result.error) {
            // a failure can still carry a complete answer: `not_persisted`
            // means the reply was generated and delivered but not saved
            if (result.error.answer) {
                setMessages((current) => [
                    ...current,
                    { key: nextLocalKey(), role: "assistant", content: result.error.answer },
                ]);
            }

            if (result.error.conversationId) {
                setActiveConversationId(result.error.conversationId);
            }

            setError(readError(result.error));
            return;
        }

        setMessages((current) => [
            ...current,
            { key: nextLocalKey(), role: "assistant", content: result.data.answer },
        ]);

        setActiveConversationId(result.data.conversationId);
    };

    if (!mounted) return null;

    const isHistory = view === "history";

    // waiting on retrieval: the request is in flight but no token has landed
    const isThinking = isLoading && !streamingText;

    // nothing to start fresh from when the conversation is already empty
    const canStartNew = Boolean(activeConversationId) || messages.length > 0;

    return createPortal(
        <>
            {isOpen && (
                <section
                    className={styles.panel}
                    role="dialog"
                    aria-label="Ask the issue assistant"
                >
                    <header className={styles.header}>
                        <div className={styles.headerLeft}>
                            <span className={styles.headerIcon} aria-hidden="true">💬</span>
                            <div>
                                <h2 className={styles.headerTitle}>Issue Assistant</h2>
                                <p className={styles.headerSubtitle}>
                                    Ask about issues you can access
                                </p>
                            </div>
                        </div>

                        <button
                            type="button"
                            className={styles.closeBtn}
                            onClick={() => setIsOpen(false)}
                            aria-label="Close assistant"
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    </header>

                    <div className={styles.controls}>
                        <button
                            type="button"
                            className={styles.ghostBtn}
                            onClick={() => setView(isHistory ? "chat" : "history")}
                            aria-label={isHistory ? "Back to conversation" : "Show past conversations"}
                        >
                            {isHistory ? (
                                <>
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                        <polyline points="15 18 9 12 15 6" />
                                    </svg>
                                    Back
                                </>
                            ) : (
                                <>
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                        <circle cx="12" cy="12" r="9" />
                                        <polyline points="12 7 12 12 15.5 14" />
                                    </svg>
                                    History
                                </>
                            )}
                        </button>

                        <button
                            type="button"
                            className={styles.ghostBtn}
                            onClick={startNewConversation}
                            disabled={!canStartNew || isLoading}
                        >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                <line x1="12" y1="5" x2="12" y2="19" />
                                <line x1="5" y1="12" x2="19" y2="12" />
                            </svg>
                            New chat
                        </button>
                    </div>

                    {isHistory ? (
                        <div className={styles.body}>
                            {isLoadingConversations && conversations.length === 0 && (
                                <div className={styles.loadingState}>
                                    <span className={styles.spinner} />
                                </div>
                            )}

                            {!isLoadingConversations && conversations.length === 0 && (
                                <div className={styles.emptyState}>
                                    <span className={styles.emptyIcon} aria-hidden="true">🗂️</span>
                                    <p className={styles.emptyTitle}>No conversations yet</p>
                                    <p className={styles.emptyText}>
                                        Ask a question and it will be saved here.
                                    </p>
                                </div>
                            )}

                            {conversations.length > 0 && (
                                <ul className={styles.historyList}>
                                    {conversations.map((conversation) => {
                                        const isEditing = editingId === conversation.id;

                                        return (
                                            <li
                                                key={conversation.id}
                                                className={
                                                    conversation.id === activeConversationId
                                                        ? styles.historyItemActive
                                                        : styles.historyItem
                                                }
                                            >
                                                {isEditing ? (
                                                    <input
                                                        ref={titleInputRef}
                                                        className={styles.titleInput}
                                                        value={titleDraft}
                                                        onChange={(event) => setTitleDraft(event.target.value)}
                                                        onKeyDown={handleTitleKeyDown}
                                                        onBlur={commitTitle}
                                                        maxLength={255}
                                                        aria-label="Conversation title"
                                                    />
                                                ) : (
                                                    <button
                                                        type="button"
                                                        className={styles.historyOpen}
                                                        onClick={() => openConversation(conversation.id)}
                                                    >
                                                        <span className={styles.historyTitle}>
                                                            {conversation.title || "Untitled conversation"}
                                                        </span>
                                                        <span className={styles.historyTime}>
                                                            {timeAgo(conversation.updated_at || conversation.created_at)}
                                                        </span>
                                                    </button>
                                                )}

                                                {!isEditing && (
                                                    <div className={styles.historyActions}>
                                                        <button
                                                            type="button"
                                                            className={styles.renameBtn}
                                                            title="Rename"
                                                            aria-label="Rename conversation"
                                                            onClick={() => startEditing(conversation)}
                                                        >
                                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                                                <path d="M12 20h9" />
                                                                <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
                                                            </svg>
                                                        </button>

                                                        <button
                                                            type="button"
                                                            className={styles.removeBtn}
                                                            title="Delete"
                                                            aria-label="Delete conversation"
                                                            onClick={() => handleDeleteConversation(conversation.id)}
                                                        >
                                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                                                <path d="M3 6h18" />
                                                                <path d="M8 6V4h8v2" />
                                                                <path d="M19 6l-1 14H6L5 6" />
                                                            </svg>
                                                        </button>
                                                    </div>
                                                )}
                                            </li>
                                        );
                                    })}
                                </ul>
                            )}
                        </div>
                    ) : (
                        <div className={styles.body} ref={listRef}>
                            {isLoadingTranscript && messages.length === 0 && (
                                <div className={styles.loadingState}>
                                    <span className={styles.spinner} />
                                </div>
                            )}

                            {!isLoadingTranscript && messages.length === 0 && !isThinking && (
                                <div className={styles.emptyState}>
                                    <span className={styles.emptyIcon} aria-hidden="true">🔎</span>
                                    <p className={styles.emptyTitle}>Ask about your issues</p>
                                    <p className={styles.emptyText}>
                                        Try &ldquo;which issues involve failed webhook deliveries?&rdquo;
                                    </p>
                                </div>
                            )}

                            {messages.map((message) => (
                                <div
                                    key={message.key}
                                    className={
                                        message.role === "user"
                                            ? styles.userRow
                                            : styles.assistantRow
                                    }
                                >
                                    <div
                                        className={
                                            message.role === "user"
                                                ? styles.userBubble
                                                : styles.assistantBubble
                                        }
                                    >
                                        {message.content}
                                    </div>
                                </div>
                            ))}

                            {streamingText && (
                                <div className={styles.assistantRow}>
                                    <div className={styles.assistantBubble}>
                                        {streamingText}
                                        <span className={styles.caret} aria-hidden="true" />
                                    </div>
                                </div>
                            )}

                            {isThinking && (
                                <div className={styles.assistantRow}>
                                    <div className={styles.thinkingBubble} aria-label="Searching issues">
                                        <span className={styles.dot} />
                                        <span className={styles.dot} />
                                        <span className={styles.dot} />
                                    </div>
                                </div>
                            )}

                            {error && (
                                <p className={styles.error} role="alert">{error}</p>
                            )}
                        </div>
                    )}

                    {!isHistory && (
                        <form className={styles.composer} onSubmit={handleSubmit}>
                            <input
                                ref={inputRef}
                                className={styles.input}
                                value={draft}
                                onChange={(event) => setDraft(event.target.value)}
                                placeholder="Ask a question…"
                                aria-label="Your question"
                                maxLength={2000}
                                disabled={isLoading}
                            />

                            <button
                                type="submit"
                                className={styles.sendBtn}
                                disabled={isLoading || !draft.trim()}
                                aria-label="Send question"
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="22" y1="2" x2="11" y2="13" />
                                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                                </svg>
                            </button>
                        </form>
                    )}
                </section>
            )}

            <button
                type="button"
                className={styles.launcher}
                onClick={() => setIsOpen((open) => !open)}
                aria-label={isOpen ? "Close assistant" : "Open assistant"}
                aria-expanded={isOpen}
            >
                {isOpen ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                ) : (
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                    </svg>
                )}
            </button>
        </>,
        document.body
    );
}
