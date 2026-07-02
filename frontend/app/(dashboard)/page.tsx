import { redirect } from "next/navigation";

export default function DashboardRootRedirectPage() {
  redirect("/home");
}
