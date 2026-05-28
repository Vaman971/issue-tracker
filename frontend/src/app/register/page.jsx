"use client"

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod"

import { useRegisterMutation } from "@/store/features/auth/authApi";

import styles from "./page.module.css"

const registerSchema = z.object({
    email: z.email("Enter a valid email address"),
    password: z.string().min(8, "Password must be at least 8 characters")
});

export default function RegisterPage() {
    const router = useRouter();

    const [registerUser, {isLoading, error}] = useRegisterMutation();

    const {
        register,
        handleSubmit,
        formState: {errors},
    } = useForm({
        resolver: zodResolver(registerSchema)
    });

   const onSubmit = async (formData) => {
    await registerUser(formData).unwrap();
    router.push("/login");
   }

   return (
    <main className={styles.page}>
        <section className={styles.card}>
            <h1 className={styles.title}>Create account</h1>

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
                    <p className={styles.error}>Register failed</p>
                )}

                <button
                className={styles.button}
                type="submit"
                disabled={isLoading}
                >
                    {isLoading ? "Creating account...": "Register"}
                </button>
            </form>

            <p className={styles.footerText}>
                Already have an account? <Link className={styles.link} href="/login">Login</Link>
            </p>
        </section>
    </main>
   )
}
