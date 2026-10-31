"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { LogoMark } from "@/components/logo";
import { apiFetch } from "@/lib/api";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/conversations", label: "Conversations" },
  { href: "/ask", label: "Ask Recall" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    try {
      await apiFetch("/api/v1/auth/logout", { method: "POST" });
    } finally {
      router.push("/login");
    }
  }

  return (
    <header className="sticky top-0 z-10 border-b border-line bg-paper/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/dashboard" className="flex items-center gap-2 font-semibold tracking-tight">
          <LogoMark size={24} />
          Recall
        </Link>
        <nav className="flex flex-1 gap-1 text-sm">
          {LINKS.map((l) => {
            const active = pathname === l.href || pathname.startsWith(`${l.href}/`);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`rounded-md px-3 py-1.5 ${active ? "bg-surface font-medium shadow-sm" : "text-muted hover:text-ink"}`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <button onClick={logout} className="text-sm text-muted hover:text-ink">
          Log out
        </button>
      </div>
    </header>
  );
}
