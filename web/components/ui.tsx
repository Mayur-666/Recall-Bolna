import type { ReactNode } from "react";

import type { ConversationStatus, DecisionState } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-line bg-surface-solid p-5 ${className}`}>{children}</div>;
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
  queued: "bg-white/5 text-muted ring-white/10",
  processing: "bg-accent-soft text-accent ring-accent/30",
  ready: "bg-[#86c79a]/10 text-[#a6d8b4] ring-[#86c79a]/30",
  failed: "bg-[#e07a6e]/10 text-[#eea59b] ring-[#e07a6e]/30",
};

export function StatusBadge({ status }: { status: ConversationStatus }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${STATUS_STYLES[status]}`}>
      {status === "processing" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
      {status}
    </span>
  );
}

// One colour language shared by chips, the Memory Field and the live evidence stream.
export const STATE_COLORS: Record<DecisionState, string> = {
  decided: "#86c79a",
  proposed: "#e8975a",
  unresolved: "#93a7c4",
  rejected: "#7d7a73",
  superseded: "#e07a6e",
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
      ? "bg-accent-soft text-accent ring-accent/40"
      : tone === "rose"
        ? "bg-rose-400/10 text-rose-300 ring-rose-400/30"
        : "bg-white/5 text-muted ring-white/10";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${cls}`}>{children}</span>;
}

export function formatDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
