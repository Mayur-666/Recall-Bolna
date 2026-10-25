"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ApiError, apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Invalid email or password." : "Could not sign in. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-accent text-xl font-semibold text-white">R</span>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">Sign in to Recall</h1>
          <p className="mt-1 text-sm text-muted">Remember every important conversation. Just ask.</p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-surface p-6 shadow-sm">
          <label className="block text-sm font-medium">
            Email
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
            />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
            />
          </label>
          {error && (
            <p role="alert" className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-accent px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-center text-xs text-muted">Demo credentials are in the project README.</p>
      </div>
    </main>
  );
}
