import { redirect } from "next/navigation";

/* This page does not need browser interactivity, state, or event handlers. so it can stay as a server component*/
export default function Home() {
  redirect("/login")
}