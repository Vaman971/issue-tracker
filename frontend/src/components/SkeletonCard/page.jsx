import styles from "./page.module.css"

export default function SkeletonCard() {
  return (
    <article className={styles.card}>
      <div className={styles.title} />
      <div className={styles.line} />
      <div className={styles.lineShort} />
      <div className={styles.meta} />
    </article>
  );
}