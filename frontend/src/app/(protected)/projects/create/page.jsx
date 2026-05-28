"use client"

import { zodResolver } from "@hookform/resolvers/zod";
import { redirect } from "next/navigation";
import { useForm } from "react-hook-form"
import { z } from "zod"

import { useCreateProjectMutation } from "@/store/features/projects/projectsApi";

import styles from "./page.module.css"

const projectSchema = z.object({
    name: z.string().min(2, "Project name is too short"),
    description: z.string().optional(),
    leader_id: z.coerce.number().min(1, "leader ID is required") // converts html "1" string to number
});

export default function CreateProjectPage() {

    const [createProject, {isLoading, error}] = useCreateProjectMutation();

    const {
        register,
        handleSubmit,
        formState: {errors},
    } = useForm({
        resolver: zodResolver(projectSchema),
    });

    const onSubmit = async (formData) => {
        await createProject(formData).unwrap();

        redirect("/projects");
    }

    return (
        <main className={styles.page}>
            <section className={styles.card}>
                <h1 className={styles.title}>Create project</h1>

                <form onSubmit={handleSubmit(onSubmit)}>
                    <div className={styles.field}>
                        <label className={styles.label}>
                            Project name
                        </label>
                        <input 
                        className={styles.input}
                        type="text" 
                        {...register("name")}
                        />
                        {errors.name && (
                            <p className={styles.error}>
                                {errors.name.message}
                            </p>
                        )}
                    </div>

                    <div className={styles.field}>
                        <label className={styles.label}>
                            Description
                        </label>

                        <textarea 
                        className={styles.textarea} 
                        {...register("description")}
                        />
                    </div>

                    <div className={styles.field}>
                        <label className={styles.label}>
                            Leader Id
                        </label>

                        <input 
                        type="number" 
                        className={styles.input}
                        {...register("leader_id")}
                        />

                        {errors.leader_id && (
                            <p className={styles.error}>
                                {errors.leader_id.message}
                            </p>
                        )}
                    </div>

                    {error && (
                        <p className={styles.error}>
                            Failed to create project
                        </p>
                    )}

                    <button
                     className={styles.button}
                     type="submit"
                     disabled={isLoading}
                    >
                        { isLoading
                         ? "Creating..."
                         : "Create project"
                        }
                    </button>
                </form>
            </section>
        </main>
    );
}