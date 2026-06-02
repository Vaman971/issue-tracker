"use client"

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useForgotPasswordMutation } from "@/store/features/auth/authApi";
import styles from "./page.module.css";

const schema = z.object({
    email: z.email("Enter a valid email address"),
});

export default function ForgotPasswordPage() {
    const [forgotPassword, { isLoading, isSuccess }] = useForgotPasswordMutation();

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm({ resolver: zodResolver(schema) });

    const onSubmit = async (data) => {
        await forgotPassword(data);
    };

    if (isSuccess) {
        return (
            <main className={styles.page}>
                <section className={styles.card}>
                    <h1 className={styles.title}>Check your email</h1>
                    <p className={styles.message}>
                        If an account with that email exists, a password reset link has been sent.
                        Check your inbox and follow the link to reset your password.
                    </p>
                    <Link className={styles.backLink} href="/login">
                        Back to Login
                    </Link>
                </section>
            </main>
        );
    }

    return (
        <main className={styles.page}>
            <section className={styles.card}>
                <h1 className={styles.title}>Forgot Password</h1>
                <p className={styles.subtitle}>
                    Enter your email address and we&apos;ll send you a reset link.
                </p>

                <form onSubmit={handleSubmit(onSubmit)}>
                    <div className={styles.field}>
                        <label className={styles.label} htmlFor="fp-email">Email</label>
                        <input
                            id="fp-email"
                            className={styles.input}
                            type="email"
                            placeholder="you@example.com"
                            {...register("email")}
                        />
                        {errors.email && (
                            <p className={styles.error}>{errors.email.message}</p>
                        )}
                    </div>

                    <button
                        className={styles.button}
                        type="submit"
                        disabled={isLoading}
                    >
                        {isLoading ? "Sending..." : "Send Reset Link"}
                    </button>
                </form>

                <p className={styles.footerText}>
                    Remembered it?{" "}
                    <Link className={styles.link} href="/login">
                        Login
                    </Link>
                </p>
            </section>
        </main>
    );
}
