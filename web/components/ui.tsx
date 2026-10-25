import type { ReactNode } from "react";

import type { ConversationStatus, DecisionState } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-line bg-surface p-5 shadow-sm ${className}`}>{children}</div>;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />
      {label}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-surface/60 px-6 py-10 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="rounded-md border border-red-300 bg-white px-3 py-1 font-medium hover:bg-red-100">
          Retry
        </button>
      )}
    </div>
  );
}

const STATUS_STYLES: Record<ConversationStatus, string> = {
  queued: "bg-slate-100 text-slate-700",
  processing: "bg-blue-50 text-blue-700",
  ready: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-700",
};

export function StatusBadge({ status }: { status: ConversationStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {status === "processing" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />}
      {status}
    </span>
  );
}

const STATE_STYLES: Record<DecisionState, { label: string; cls: string }> = {
  decided: { label: "Decided", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  proposed: { label: "Suggested", cls: "bg-amber-50 text-amber-800 border-amber-200" },
  unresolved: { label: "Left open", cls: "bg-slate-50 text-slate-700 border-slate-200" },
  rejected: { label: "Turned down", cls: "bg-zinc-100 text-zinc-600 border-zinc-200" },
  superseded: { label: "Changed later", cls: "bg-rose-50 text-rose-700 border-rose-200" },
};

export function DecisionStateChip({ state }: { state: DecisionState | null }) {
  if (!state) return null;
  const s = STATE_STYLES[state];
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${s.cls}`}>{s.label}</span>;
}

export function Chip({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "accent" | "rose" }) {
  const cls =
    tone === "accent"
      ? "bg-accent-soft text-accent"
      : tone === "rose"
        ? "bg-rose-50 text-rose-700"
        : "bg-slate-100 text-slate-700";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

export function formatDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
