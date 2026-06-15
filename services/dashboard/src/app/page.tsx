import { redirect } from "next/navigation";
import { withBasePath } from "@/lib/base-path";

export default function HomePage() {
  redirect(withBasePath("/meetings"));
}
