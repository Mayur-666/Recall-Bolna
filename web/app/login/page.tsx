"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { LogoMark } from "@/components/logo";
import { ApiError, apiFetch } from "@/lib/api";

type AuthMode = "signin" | "signup";

// Common disposable domain stems for instant client-side feedback
const DISPOSABLE_STEMS = [
  "mailinator",
  "10minutemail",
  "10minmail",
  "guerrillamail",
  "sharklasers",
  "tempmail",
  "temp-mail",
  "trashmail",
  "yopmail",
  "dispostable",
  "fakeinbox",
  "burnermail",
  "dropmail",
  "throwawaymail",
  "moakt",
  "nada.ltd",
  "emailondeck",
  "mytemp",
  "inboxbear",
  "fakemail",
];

function checkEmailRisk(email: string): string | null {
  const trimmed = email.trim().toLowerCase();
  if (!trimmed) return null;

  if (trimmed === "demo@recall.local") return null;

  if (trimmed.includes("@")) {
    const [local, domain] = trimmed.split("@");
    if (!domain) return null;

    for (const stem of DISPOSABLE_STEMS) {
      if (domain.includes(stem)) {
        return "Temporary and disposable email addresses are not allowed. Please use your personal or work email.";
      }
    }

    if (local.startsWith("bot_") || local.startsWith("crawler_") || local.startsWith("spambot")) {
      return "Automated or bot-patterned email addresses are blocked.";
    }

    if (local.includes("paypal_billing") || local.includes("bank_security") || local.includes("crypto_support")) {
      return "High-risk impersonation email pattern detected.";
    }
  }

  return null;
}

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("signin");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Google OAuth state
  const [googleClientId, setGoogleClientId] = useState<string>("");
  const [showGoogleModal, setShowGoogleModal] = useState(false);
  const [googleSimEmail, setGoogleSimEmail] = useState("mayur@gmail.com");
  const [googleSimName, setGoogleSimName] = useState("Mayur");
  const [gsiReady, setGsiReady] = useState(false);
  const googleBtnRef = useRef<HTMLDivElement>(null);

  // Fetch backend auth config to see if Google Client ID is configured
  useEffect(() => {
    apiFetch<{ google_client_id: string }>("/api/v1/auth/config")
      .then((cfg) => {
        if (cfg.google_client_id) {
          setGoogleClientId(cfg.google_client_id);
        }
      })
      .catch(() => undefined);
  }, []);

  // Initialize Google Identity Services if client ID exists
  useEffect(() => {
    if (!googleClientId) return;

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => {
      const google = (window as unknown as { google?: { accounts?: { id?: { initialize: (opts: unknown) => void } } } }).google;
      if (google?.accounts?.id) {
        google.accounts.id.initialize({
          client_id: googleClientId,
          callback: async (response: { credential?: string }) => {
            if (response.credential) {
              await handleGoogleCredential(response.credential);
            }
          },
        });
        setGsiReady(true);
      }
    };
    script.onerror = () => setError("Couldn't load Google sign-in. Check your connection or use email instead.");
    document.body.appendChild(script);

    return () => {
      script.remove();
    };
  }, [googleClientId]);

  async function handleGoogleCredential(credential: string, fallbackEmail?: string, fallbackName?: string) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/google", {
        method: "POST",
        body: JSON.stringify({
          credential,
          email: fallbackEmail,
          name: fallbackName,
        }),
      });
      window.location.href = "/space";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete Google authentication.");
    } finally {
      setBusy(false);
      setShowGoogleModal(false);
    }
  }

  // Google's own rendered button (popup flow). One Tap's prompt() was used before, but Chrome silently
  // suppresses it after a dismissal, so the button looked dead. Re-rendered when the mode label changes.
  useEffect(() => {
    const el = googleBtnRef.current;
    if (!gsiReady || !el) return;
    const google = (window as unknown as { google?: { accounts?: { id?: { renderButton: (el: HTMLElement, opts: unknown) => void } } } }).google;
    el.innerHTML = "";
    google?.accounts?.id?.renderButton(el, {
      type: "standard",
      theme: "filled_black",
      size: "large",
      shape: "rectangular",
      text: mode === "signup" ? "signup_with" : "continue_with",
      width: Math.min(400, el.offsetWidth || 400),
    });
  }, [gsiReady, mode]);

  // Without GOOGLE_CLIENT_ID (local dev) the backend accepts a simulated Google sign-in instead.
  function onGoogleClick() {
    setShowGoogleModal(true);
  }

  const emailWarning = checkEmailRisk(email);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (emailWarning) {
      setError(emailWarning);
      return;
    }

    setBusy(true);
    setError(null);

    try {
      if (mode === "signin") {
        await apiFetch("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: email.trim(), password }),
        });
      } else {
        await apiFetch("/api/v1/auth/register", {
          method: "POST",
          body: JSON.stringify({
            display_name: displayName.trim(),
            email: email.trim(),
            password,
          }),
        });
      }
      window.location.href = "/space";
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("Invalid email or password.");
        } else if (err.status === 409) {
          setError("An account with this email already exists. Please sign in instead.");
        } else if (err.status === 422) {
          setError(err.message || "Invalid or restricted email address.");
        } else {
          setError(err.message || "Authentication failed.");
        }
      } else {
        setError("Could not connect to Recall backend. Is the server running?");
      }
    } finally {
      setBusy(false);
    }
  }

  function fillDemo() {
    setEmail("demo@recall.local");
    setPassword("recall-demo-75287f");
    setError(null);
  }

  return (
    <main className="relative min-h-screen w-full flex items-center justify-center p-4 bg-paper text-ink overflow-hidden">

      <div className="relative w-full max-w-md animate-in fade-in zoom-in-95 duration-200">
        {/* Header / Logo */}
        <div className="mb-6 text-center">
          <Link href="/" className="inline-flex items-center gap-2.5 group mb-3">
            <LogoMark size={32} />
            <span className="font-display text-xl font-semibold tracking-tight text-ink">Recall</span>
          </Link>
          <h1 className="text-xl font-semibold text-ink tracking-tight">
            {mode === "signin" ? "Sign in to Recall" : "Create your Recall account"}
          </h1>
          <p className="mt-1 text-xs text-muted">
            {mode === "signin"
              ? "Ask your meetings what was decided."
              : "Upload a transcript, then ask about it out loud."}
          </p>
        </div>

        {/* Card Box */}
        <div className="rounded-2xl border border-line bg-surface-solid p-6 md:p-8">
          {/* Mode Tabs */}
          <div className="relative flex rounded-xl bg-paper p-1 mb-6 border border-line">
            {/* sliding indicator behind the active tab */}
            <span
              aria-hidden
              className={`absolute inset-y-1 left-1 w-[calc(50%-4px)] rounded-lg bg-raised transition-transform duration-300 ease-[cubic-bezier(0.2,0.7,0.2,1)] ${
                mode === "signup" ? "translate-x-full" : "translate-x-0"
              }`}
            />
            <button
              type="button"
              onClick={() => {
                setMode("signin");
                setError(null);
              }}
              className={`relative flex-1 rounded-lg py-2 text-xs font-semibold transition-colors ${
                mode === "signin" ? "text-ink" : "text-muted hover:text-ink"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setError(null);
              }}
              className={`relative flex-1 rounded-lg py-2 text-xs font-semibold transition-colors ${
                mode === "signup" ? "text-ink" : "text-muted hover:text-ink"
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Google Button: the real one when a client ID is configured, the dev simulation otherwise */}
          {googleClientId ? (
            <div ref={googleBtnRef} className="flex min-h-[44px] w-full justify-center [color-scheme:normal]">
              {!gsiReady && <span className="self-center text-xs text-muted">Loading Google sign-in…</span>}
            </div>
          ) : (
          <button
            type="button"
            onClick={onGoogleClick}
            disabled={busy}
            className="w-full flex items-center justify-center gap-3 rounded-xl border border-line bg-raised hover:bg-raised/70 py-2.5 px-4 text-xs font-semibold text-ink transition hover:border-white/30 shadow-sm disabled:opacity-50"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span>Continue with Google</span>
          </button>
          )}

          {/* Divider */}
          <div className="relative my-5 flex items-center justify-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-line/60" />
            </div>
            <span className="relative bg-surface-solid px-3 text-[11px] uppercase tracking-wider text-muted">
              or continue with email
            </span>
          </div>

          {/* Main Form */}
          <form onSubmit={submit} className="space-y-4">
            {mode === "signup" && (
              <div className="rise-in">
                <label htmlFor="login-name" className="block text-xs font-medium text-ink-sub mb-1">
                  Full Name
                </label>
                <input
                  id="login-name"
                  type="text"
                  required
                  autoComplete="name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Mayur Patel"
                  className="w-full rounded-xl border border-line bg-paper px-3.5 py-2 text-xs text-ink placeholder:text-muted/60 outline-none focus:border-accent focus:ring-2 focus:ring-accent/30 transition"
                />
              </div>
            )}

            <div>
              <label htmlFor="login-email" className="block text-xs font-medium text-ink-sub mb-1">
                Email Address
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setError(null);
                }}
                placeholder="name@company.com"
                className={`w-full rounded-xl border px-3.5 py-2 text-xs text-ink placeholder:text-muted/60 outline-none transition ${
                  emailWarning
                    ? "border-amber-400/80 bg-amber-500/10 focus:border-amber-400 focus:ring-2 focus:ring-amber-400/30"
                    : "border-line bg-paper focus:border-accent focus:ring-2 focus:ring-accent/30"
                }`}
              />
              {emailWarning && (
                <p className="mt-1.5 text-[11px] leading-snug text-amber-300 flex items-start gap-1">
                                    <span>{emailWarning}</span>
                </p>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="login-password" className="text-xs font-medium text-ink-sub">
                  Password
                </label>
                {mode === "signup" && (
                  <span className="text-[10px] text-muted">Min. 6 characters</span>
                )}
              </div>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-line bg-paper px-3.5 py-2 pr-10 text-xs text-ink placeholder:text-muted/60 outline-none focus:border-accent focus:ring-2 focus:ring-accent/30 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink text-xs transition"
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && (
              <div
                role="alert"
                key={error}
                className="shake rounded-xl border border-[#e07a6e]/40 bg-[#e07a6e]/10 px-3.5 py-2.5 text-xs text-[#f0b2a9]"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy || Boolean(emailWarning)}
              className="w-full rounded-xl bg-accent py-2.5 text-xs font-semibold text-on-accent hover:brightness-105 transition disabled:opacity-50"
            >
              {busy ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-3 w-3 animate-spin rounded-full border-[1.5px] border-on-accent/30 border-t-on-accent" />
                  Signing in…
                </span>
              ) : mode === "signin" ? "Sign In" : "Create Account"}
            </button>
          </form>

          {/* Quick Demo Fill helper for reviewers / testers */}
          {mode === "signin" && (
            <div className="mt-5 pt-4 border-t border-line/60 flex items-center justify-between text-[11px] text-muted">
              <span>Testing locally?</span>
              <button
                type="button"
                onClick={fillDemo}
                className="text-accent hover:text-accent-2 transition font-medium hover:underline flex items-center gap-1"
              >
                <span>Use demo account</span>
              </button>
            </div>
          )}
        </div>

        {/* Security Trust Note */}
      </div>

      {/* Google Sign-in Interactive Modal (for dev/demo when GOOGLE_CLIENT_ID isn't set yet) */}
      {showGoogleModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 animate-in fade-in">
          <div className="w-full max-w-sm rounded-2xl border border-line bg-surface-solid p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <h3 className="font-display text-sm font-semibold text-ink">Sign in with Google</h3>
              </div>
              <button
                onClick={() => setShowGoogleModal(false)}
                className="text-muted hover:text-ink text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-muted mb-4">
              Select or enter your Google account details to sign in:
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-muted mb-1">
                  Google Display Name
                </label>
                <input
                  type="text"
                  value={googleSimName}
                  onChange={(e) => setGoogleSimName(e.target.value)}
                  className="w-full rounded-lg border border-line bg-paper px-3 py-1.5 text-xs text-ink outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-muted mb-1">
                  Google Email
                </label>
                <input
                  type="email"
                  value={googleSimEmail}
                  onChange={(e) => setGoogleSimEmail(e.target.value)}
                  className="w-full rounded-lg border border-line bg-paper px-3 py-1.5 text-xs text-ink outline-none focus:border-accent"
                />
              </div>

              <div className="pt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowGoogleModal(false)}
                  className="flex-1 rounded-lg border border-line py-2 text-xs font-medium text-muted hover:text-ink transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleGoogleCredential(
                      `demo_google:${googleSimEmail}`,
                      googleSimEmail,
                      googleSimName
                    )
                  }
                  disabled={busy}
                  className="flex-1 rounded-lg bg-accent py-2 text-xs font-semibold text-on-accent hover:brightness-105 transition"
                >
                  {busy ? "Signing in..." : "Continue"}
                </button>
              </div>

              <p className="text-[10px] text-muted/70 text-center mt-2">
                To enable live Google OAuth popup, add <code>GOOGLE_CLIENT_ID</code> to your <code>.env</code> file.
              </p>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
