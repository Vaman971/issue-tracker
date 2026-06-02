"use client"

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useResetPasswordMutation } from "@/store/features/auth/authApi";
import styles from "./page.module.css";

const schema = z
    .object({
        new_password: z.string().min(8, "Password must be at least 8 characters"),
        confirm_password: z.string().min(8, "Confirm your password"),
    })
    .refine((data) => data.new_password === data.confirm_password, {
        message: "Passwords do not match",
        path: ["confirm_password"],
    });

function ResetPasswordForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const token = searchParams.get("token") || "";

    const [resetPassword, { isLoading, isSuccess, error }] = useResetPasswordMutation();

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm({ resolver: zodResolver(schema) });

    const onSubmit = async (data) => {
        try {
            await resetPassword({ token, new_password: data.new_password }).unwrap();
        } catch {
            // error handled by RTK Query state
        }
    };

    if (!token) {
        return (
            <section className={styles.card}>
                <h1 className={styles.title}>Invalid Link</h1>
                <p className={styles.message}>
                    This password reset link is invalid or missing. Please request a new one.
                </p>
                <Link className={styles.backLink} href="/forgot-password">
                    Request New Link
                </Link>
            </section>
        );
    }

    if (isSuccess) {
        return (
            <section className={styles.card}>
                <h1 className={styles.title}>Password Reset!</h1>
                <p className={styles.message}>
                    Your password has been updated successfully. You can now log in with your new password.
                </p>
                <Link className={styles.backLink} href="/login">
                    Go to Login
                </Link>
            </section>
        );
    }

    return (
        <section className={styles.card}>
            <h1 className={styles.title}>Reset Password</h1>
            <p className={styles.subtitle}>Enter your new password below.</p>

            <form onSubmit={handleSubmit(onSubmit)}>
                <div className={styles.field}>
                    <label className={styles.label}>New Password</label>
                    <input
                        className={styles.input}
                        type="password"
                        {...register("new_password")}
                    />
                    {errors.new_password && (
                        <p className={styles.error}>{errors.new_password.message}</p>
                    )}
                </div>

                <div className={styles.field}>
                    <label className={styles.label}>Confirm Password</label>
                    <input
                        className={styles.input}
                        type="password"
                        {...register("confirm_password")}
                    />
                    {errors.confirm_password && (
                        <p className={styles.error}>{errors.confirm_password.message}</p>
                    )}
                </div>

                {error && (
                    <p className={styles.error}>
                        {error.data?.detail || "Reset link is invalid or expired."}
                    </p>
                )}

                <button
                    className={styles.button}
                    type="submit"
                    disabled={isLoading}
                >
                    {isLoading ? "Resetting..." : "Reset Password"}
                </button>
            </form>

            <p className={styles.footerText}>
                <Link className={styles.link} href="/login">
                    Back to Login
                </Link>
            </p>
        </section>
    );
}

export default function ResetPasswordPage() {
    return (
        <main className={styles.page}>
            <Suspense fallback={<div className={styles.card}><p>Loading...</p></div>}>
                <ResetPasswordForm />
            </Suspense>
        </main>
    );
}
