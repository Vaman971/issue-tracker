"use client"

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useVerifyEmailMutation } from "@/store/features/auth/authApi";
import styles from "./page.module.css";

function VerifyEmailContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const token = searchParams.get("token") || "";

    const [verifyEmail, { isLoading, isSuccess, error }] = useVerifyEmailMutation();
    const [attempted, setAttempted] = useState(false);

    useEffect(() => {
        if (token && !attempted) {
            setAttempted(true);
            verifyEmail({ token });
        }
    }, [token, attempted, verifyEmail]);

    if (!token) {
        return (
            <section className={styles.card}>
                <div className={styles.icon}>✉</div>
                <h1 className={styles.title}>Email Verification</h1>
                <p className={styles.message}>
                    Check your inbox for a verification link. Click the link to verify your email address.
                </p>
                <Link className={styles.link} href="/login">
                    Back to Login
                </Link>
            </section>
        );
    }

    if (isLoading) {
        return (
            <section className={styles.card}>
                <div className={styles.spinner} />
                <h1 className={styles.title}>Verifying...</h1>
                <p className={styles.message}>Please wait while we verify your email.</p>
            </section>
        );
    }

    if (isSuccess) {
        return (
            <section className={styles.card}>
                <div className={styles.iconSuccess}>✓</div>
                <h1 className={styles.title}>Email Verified!</h1>
                <p className={styles.message}>
                    Your email address has been verified successfully. You can now enjoy all features.
                </p>
                <button
                    className={styles.button}
                    onClick={() => router.push("/projects")}
                >
                    Go to Projects
                </button>
            </section>
        );
    }

    if (error) {
        return (
            <section className={styles.card}>
                <div className={styles.iconError}>✕</div>
                <h1 className={styles.title}>Verification Failed</h1>
                <p className={styles.message}>
                    {error.data?.detail || "The verification link is invalid or has expired."}
                </p>
                <Link className={styles.link} href="/login">
                    Back to Login
                </Link>
            </section>
        );
    }

    return null;
}

export default function VerifyEmailPage() {
    return (
        <main className={styles.page}>
            <Suspense fallback={<div className={styles.card}><p>Loading...</p></div>}>
                <VerifyEmailContent />
            </Suspense>
        </main>
    );
}
