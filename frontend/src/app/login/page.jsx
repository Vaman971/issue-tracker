"use client"

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { useDispatch } from "react-redux";
import Link from "next/link";
import { z } from "zod";

import { useLoginMutation } from "@/store/features/auth/authApi";
import { setCredentials } from "@/store/features/auth/authSlice";

import styles from "./page.module.css";

const loginSchema = z.object({
    email: z.email("Enter a valid email address"),
    password: z.string().min(8, "Password must be atleast 8 characters"),
});

export default function LoginPage() {
    const router = useRouter();
    const dispatch = useDispatch();

    const [login, {isLoading, error}] = useLoginMutation();

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm({
        resolver: zodResolver(loginSchema)
    });

    const onSubmit = async (formData) => {
        // converts RTK query object to normal json
        const response = await login(formData).unwrap();

        dispatch(
            setCredentials({
                accessToken: response.access_token,
                refreshToken: response.refresh_token,
            })
        );
        router.push("/projects");
    }

    return (
    <main className={styles.page}>
        <section className={styles.card}>
            <h1 className={styles.title}>Login</h1>

            <form onSubmit={handleSubmit(onSubmit)}>
            <div className={styles.field}>
                <label className={styles.label}>Email</label>
                <input
                className={styles.input}
                type="email"
                {...register("email")}
                />
                {errors.email && (
                <p className={styles.error}>{errors.email.message}</p>
                )}
            </div>

            <div className={styles.field}>
                <label className={styles.label}>Password</label>
                <input
                className={styles.input}
                type="password"
                {...register("password")}
                />
                {errors.password && (
                <p className={styles.error}>{errors.password.message}</p>
                )}
            </div>

            {error && (
                <p className={styles.error}>Login failed. Check your credentials.</p>
            )}

            <div className={styles.forgotRow}>
                <Link className={styles.link} href="/forgot-password">
                    Forgot password?
                </Link>
            </div>

            <button
                className={styles.button}
                type="submit"
                disabled={isLoading}
            >
                {isLoading ? "Logging in..." : "Login"}
            </button>
            </form>
            <p className={styles.footerText}>
                Dont have an account? <Link className={styles.link} href="/register">Register</Link>
            </p>
        </section>
    </main>
    )
}
