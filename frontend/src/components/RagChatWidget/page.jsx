"use client"

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useSendChatMessageMutation } from "@/store/features/rag/ragApi";
import styles from "./page.module.css";

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

export default function RagChatWidget() {
    const [isOpen, setIsOpen] = useState(false);
    const [mounted, setMounted] = useState(false);

    // the exchange so far, kept for as long as the page lives
    const [messages, setMessages] = useState([]);
    const [draft, setDraft] = useState("");

    // the answer currently arriving, token by token; separate from `messages`
    // so a half-written reply is never mistaken for a finished one
    const [streamingText, setStreamingText] = useState("");
    const [error, setError] = useState(null);

    // set from the first reply, then sent back so follow-ups resolve
    // references like "and the critical ones?" against the same conversation
    const [conversationId, setConversationId] = useState(null);

    const [sendChatMessage, { isLoading }] = useSendChatMessageMutation();

    const listRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => { setMounted(true); }, []);

    // follow the conversation as it grows, including during streaming
    useEffect(() => {
        const list = listRef.current;

        if (list) {
            list.scrollTop = list.scrollHeight;
        }
    }, [messages, streamingText, isOpen]);

    useEffect(() => {
        if (isOpen) {
            inputRef.current?.focus();
        }
    }, [isOpen]);

    // Escape closes, matching the notification drawer
    useEffect(() => {
        if (!isOpen) return;

        const onKey = (event) => {
            if (event.key === "Escape") setIsOpen(false);
        };

        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [isOpen]);

    const handleSubmit = async (event) => {
        event.preventDefault();

        const question = draft.trim();

        if (!question || isLoading) return;

        setDraft("");
        setError(null);
        setStreamingText("");
        setMessages((current) => [...current, { role: "user", content: question }]);

        const result = await sendChatMessage({
            question,
            conversationId,
            onDelta: (_chunk, textSoFar) => setStreamingText(textSoFar),
        });

        setStreamingText("");

        if (result.error) {
            // a failure can still carry a complete answer: `not_persisted`
            // means the reply was generated and delivered but not saved
            if (result.error.answer) {
                setMessages((current) => [
                    ...current,
                    { role: "assistant", content: result.error.answer },
                ]);
            }

            if (result.error.conversationId) {
                setConversationId(result.error.conversationId);
            }

            setError(readError(result.error));
            return;
        }

        setMessages((current) => [
            ...current,
            { role: "assistant", content: result.data.answer },
        ]);

        setConversationId(result.data.conversationId);
    };

    if (!mounted) return null;

    // waiting on retrieval: the request is in flight but no token has landed
    const isThinking = isLoading && !streamingText;

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

                    <div className={styles.body} ref={listRef}>
                        {messages.length === 0 && !isThinking && (
                            <div className={styles.emptyState}>
                                <span className={styles.emptyIcon} aria-hidden="true">🔎</span>
                                <p className={styles.emptyTitle}>Ask about your issues</p>
                                <p className={styles.emptyText}>
                                    Try &ldquo;which issues involve failed webhook deliveries?&rdquo;
                                </p>
                            </div>
                        )}

                        {messages.map((message, index) => (
                            <div
                                key={index}
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
