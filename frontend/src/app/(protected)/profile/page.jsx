"use client"

import { zodResolver } from "@hookform/resolvers/zod";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useGetMeQuery } from "@/store/features/auth/authApi";
import {
    useChangePasswordMutation,
    useResendVerificationMutation,
} from "@/store/features/auth/authApi";
import { useUpdateProfileMutation, useUploadAvatarMutation } from "@/store/features/users/usersApi";
import styles from "./page.module.css";

const profileSchema = z.object({
    full_name: z.string().max(255).optional().or(z.literal("")),
});

const passwordSchema = z
    .object({
        current_password: z.string().min(8, "Current password required"),
        new_password: z.string().min(8, "New password must be at least 8 characters"),
        confirm_password: z.string().min(8, "Confirm your new password"),
    })
    .refine((d) => d.new_password === d.confirm_password, {
        message: "Passwords do not match",
        path: ["confirm_password"],
    });

export default function ProfilePage() {
    const { data: user, isLoading } = useGetMeQuery();
    const [updateProfile, { isLoading: isSavingProfile }] = useUpdateProfileMutation();
    const [uploadAvatar, { isLoading: isUploadingAvatar }] = useUploadAvatarMutation();
    const [changePassword, { isLoading: isChangingPw }] = useChangePasswordMutation();
    const [resendVerification, { isLoading: isResending, isSuccess: resendSent }] =
        useResendVerificationMutation();

    const [profileMsg, setProfileMsg] = useState("");
    const [pwMsg, setPwMsg] = useState("");
    const [avatarMsg, setAvatarMsg] = useState("");
    const fileRef = useRef(null);

    const profileForm = useForm({
        resolver: zodResolver(profileSchema),
        values: { full_name: user?.full_name || "" },
    });

    const pwForm = useForm({ resolver: zodResolver(passwordSchema) });

    const handleProfileSave = async (data) => {
        try {
            await updateProfile(data).unwrap();
            setProfileMsg("Profile updated.");
        } catch {
            setProfileMsg("Failed to update profile.");
        }
    };

    const handleAvatarChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        try {
            await uploadAvatar(formData).unwrap();
            setAvatarMsg("Avatar updated.");
        } catch {
            setAvatarMsg("Avatar upload failed. Max 10 MB, images only.");
        }
    };

    const handlePasswordChange = async (data) => {
        try {
            await changePassword({
                current_password: data.current_password,
                new_password: data.new_password,
            }).unwrap();
            setPwMsg("Password changed successfully.");
            pwForm.reset();
        } catch (err) {
            setPwMsg(err?.data?.detail || "Failed to change password.");
        }
    };

    if (isLoading) {
        return (
            <main className={styles.page}>
                <p className={styles.loadingText}>Loading profile...</p>
            </main>
        );
    }

    return (
        <main className={styles.page}>
            <header className={styles.header}>
                <p className={styles.eyebrow}>Account</p>
                <h1 className={styles.title}>Your Profile</h1>
            </header>

            <div className={styles.grid}>
                {/* --- Profile Info --- */}
                <section className={styles.card}>
                    <h2 className={styles.sectionTitle}>Profile Information</h2>

                    <div className={styles.avatarRow}>
                        <div className={styles.avatarPlaceholder}>
                            {user?.full_name?.[0]?.toUpperCase() ||
                                user?.email?.[0]?.toUpperCase() ||
                                "?"}
                        </div>
                        <div>
                            <button
                                className={styles.secondaryButton}
                                type="button"
                                disabled={isUploadingAvatar}
                                onClick={() => fileRef.current?.click()}
                            >
                                {isUploadingAvatar ? "Uploading..." : "Change Avatar"}
                            </button>
                            <input
                                ref={fileRef}
                                type="file"
                                accept="image/*"
                                style={{ display: "none" }}
                                onChange={handleAvatarChange}
                            />
                            {avatarMsg && <p className={styles.infoMsg}>{avatarMsg}</p>}
                        </div>
                    </div>

                    <div className={styles.infoRow}>
                        <span className={styles.infoLabel}>Email</span>
                        <span className={styles.infoValue}>{user?.email}</span>
                    </div>
                    <div className={styles.infoRow}>
                        <span className={styles.infoLabel}>Role</span>
                        <span className={styles.badge}>{user?.role}</span>
                    </div>
                    <div className={styles.infoRow}>
                        <span className={styles.infoLabel}>Email Verified</span>
                        <span
                            className={
                                user?.is_email_verified
                                    ? styles.badgeSuccess
                                    : styles.badgeWarn
                            }
                        >
                            {user?.is_email_verified ? "Verified" : "Not Verified"}
                        </span>
                    </div>

                    {!user?.is_email_verified && (
                        <button
                            className={styles.secondaryButton}
                            type="button"
                            disabled={isResending || resendSent}
                            onClick={() => resendVerification()}
                        >
                            {resendSent
                                ? "Verification email sent!"
                                : isResending
                                ? "Sending..."
                                : "Resend Verification Email"}
                        </button>
                    )}

                    <form
                        onSubmit={profileForm.handleSubmit(handleProfileSave)}
                        className={styles.form}
                    >
                        <div className={styles.field}>
                            <label className={styles.label}>Display Name</label>
                            <input
                                className={styles.input}
                                type="text"
                                placeholder="Your full name"
                                {...profileForm.register("full_name")}
                            />
                        </div>

                        {profileMsg && <p className={styles.infoMsg}>{profileMsg}</p>}

                        <button
                            className={styles.primaryButton}
                            type="submit"
                            disabled={isSavingProfile}
                        >
                            {isSavingProfile ? "Saving..." : "Save Changes"}
                        </button>
                    </form>
                </section>

                {/* --- Change Password --- */}
                <section className={styles.card}>
                    <h2 className={styles.sectionTitle}>Change Password</h2>

                    <form
                        onSubmit={pwForm.handleSubmit(handlePasswordChange)}
                        className={styles.form}
                    >
                        <div className={styles.field}>
                            <label className={styles.label} htmlFor="pw-current">Current Password</label>
                            <input
                                id="pw-current"
                                className={styles.input}
                                type="password"
                                {...pwForm.register("current_password")}
                            />
                            {pwForm.formState.errors.current_password && (
                                <p className={styles.error}>
                                    {pwForm.formState.errors.current_password.message}
                                </p>
                            )}
                        </div>

                        <div className={styles.field}>
                            <label className={styles.label} htmlFor="pw-new">New Password</label>
                            <input
                                id="pw-new"
                                className={styles.input}
                                type="password"
                                {...pwForm.register("new_password")}
                            />
                            {pwForm.formState.errors.new_password && (
                                <p className={styles.error}>
                                    {pwForm.formState.errors.new_password.message}
                                </p>
                            )}
                        </div>

                        <div className={styles.field}>
                            <label className={styles.label}>Confirm New Password</label>
                            <input
                                className={styles.input}
                                type="password"
                                {...pwForm.register("confirm_password")}
                            />
                            {pwForm.formState.errors.confirm_password && (
                                <p className={styles.error}>
                                    {pwForm.formState.errors.confirm_password.message}
                                </p>
                            )}
                        </div>

                        {pwMsg && (
                            <p
                                className={
                                    pwMsg.includes("success") ? styles.infoMsg : styles.error
                                }
                            >
                                {pwMsg}
                            </p>
                        )}

                        <button
                            className={styles.primaryButton}
                            type="submit"
                            disabled={isChangingPw}
                        >
                            {isChangingPw ? "Changing..." : "Change Password"}
                        </button>
                    </form>
                </section>
            </div>
        </main>
    );
}
