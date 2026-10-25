import type { ReactNode } from "react";

import type { ConversationStatus, DecisionState } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`glass rounded-2xl p-5 shadow-[0_8px_40px_-12px_rgba(0,0,0,0.6)] ${className}`}>{children}</div>;
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
    <div className="rounded-2xl border border-dashed border-line px-6 py-10 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-4 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="rounded-md border border-rose-300/40 px-3 py-1 font-medium hover:bg-rose-400/10">
          Retry
        </button>
      )}
    </div>
  );
}

const STATUS_STYLES: Record<ConversationStatus, string> = {
  queued: "bg-slate-400/10 text-slate-300 ring-slate-400/30",
  processing: "bg-sky-400/10 text-sky-300 ring-sky-400/30",
  ready: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/30",
  failed: "bg-rose-400/10 text-rose-300 ring-rose-400/30",
};

export function StatusBadge({ status }: { status: ConversationStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${STATUS_STYLES[status]}`}>
      {status === "processing" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-300" />}
      {status}
    </span>
  );
}

// One colour language shared by chips, the Memory Field and the live evidence stream.
export const STATE_COLORS: Record<DecisionState, string> = {
  decided: "#3ee6a0",
  proposed: "#ffc857",
  unresolved: "#8fa8ff",
  rejected: "#8a8fa8",
  superseded: "#ff6b9a",
};

const STATE_LABELS: Record<DecisionState, string> = {
  decided: "Decided",
  proposed: "Suggested",
  unresolved: "Left open",
  rejected: "Turned down",
  superseded: "Changed later",
};

export function DecisionStateChip({ state }: { state: DecisionState | null }) {
  if (!state) return null;
  const c = STATE_COLORS[state];
  return (
    <span
      className="rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ color: c, background: `${c}1f`, boxShadow: `inset 0 0 0 1px ${c}55` }}
    >
      {STATE_LABELS[state]}
    </span>
  );
}

export function Chip({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "accent" | "rose" }) {
  const cls =
    tone === "accent"
      ? "bg-accent-soft text-[#c7bfff] ring-accent/40"
      : tone === "rose"
        ? "bg-rose-400/10 text-rose-300 ring-rose-400/30"
        : "bg-white/5 text-muted ring-white/10";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${cls}`}>{children}</span>;
}

export function formatDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
