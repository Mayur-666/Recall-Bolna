"use client";

import Link from "next/link";

import { Card, Chip, DecisionStateChip, EmptyState, ErrorState, Spinner, StatusBadge, formatDate } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { Overview } from "@/lib/types";

export default function DashboardPage() {
  const { data, error, loading, reload } = useApi<Overview>("/api/v1/overview");

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-6 rounded-2xl border border-line bg-surface p-8 shadow-sm md:flex-row md:items-center md:justify-between">
        <div className="max-w-xl">
          <h1 className="text-3xl font-semibold tracking-tight">Your conversations, on call.</h1>
          <p className="mt-2 text-muted">
            Recall turns past conversations into searchable memory: decisions, who said what, promises and deadlines. Ask out
            loud and it answers with the source, or tells you when it doesn&apos;t know.
          </p>
        </div>
        <Link
          href="/ask"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-5 py-3 font-medium text-white shadow hover:opacity-90"
        >
          <span aria-hidden>🎙</span> Talk to Recall
        </Link>
      </section>

      {loading && !data && <Spinner />}
      {error && <ErrorState message={error.message} onRetry={reload} />}

      {data && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <p className="text-sm text-muted">Conversations</p>
              <p data-testid="stat-conversations" className="mt-1 text-3xl font-semibold">
                {data.conversation_count}
              </p>
            </Card>
            <Card>
              <p className="text-sm text-muted">Memories extracted</p>
              <p data-testid="stat-memories" className="mt-1 text-3xl font-semibold">
                {data.memory_count}
              </p>
            </Card>
            <Card>
              <p className="text-sm text-muted">Needs attention</p>
              <p className="mt-1 text-3xl font-semibold">{data.needs_attention.length}</p>
            </Card>
          </div>

          {data.needs_attention.length > 0 && (
            <Card>
              <h2 className="font-semibold">Needs attention</h2>
              <ul className="mt-3 divide-y divide-line">
                {data.needs_attention.map((c) => (
                  <li key={c.id} className="flex items-center justify-between gap-4 py-2 text-sm">
                    <Link href={`/conversations/${c.id}`} className="font-medium hover:underline">
                      {c.title}
                    </Link>
                    <span className="flex items-center gap-2 text-muted">
                      {c.error && <span className="max-w-sm truncate">{c.error}</span>}
                      <StatusBadge status={c.status} />
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <h2 className="font-semibold">Recent decisions</h2>
              {data.recent_decisions.length === 0 ? (
                <div className="mt-3">
                  <EmptyState title="No decisions yet">Add a conversation and Recall will pull them out.</EmptyState>
                </div>
              ) : (
                <ul className="mt-3 space-y-3">
                  {data.recent_decisions.map((d) => (
                    <li key={d.id} className="text-sm">
                      <div className="flex items-start justify-between gap-3">
                        <p className={d.decision_state === "superseded" ? "text-muted line-through" : ""}>{d.statement}</p>
                        <DecisionStateChip state={d.decision_state} />
                      </div>
                      <Link href={`/conversations/${d.conversation_id}`} className="text-xs text-muted hover:underline">
                        {d.conversation_title} · {formatDate(d.conversation_date)}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card>
              <h2 className="font-semibold">Commitments &amp; action items</h2>
              {data.open_action_items.length === 0 ? (
                <div className="mt-3">
                  <EmptyState title="Nothing outstanding" />
                </div>
              ) : (
                <ul className="mt-3 space-y-3">
                  {data.open_action_items.map((a) => (
                    <li key={a.id} className="text-sm">
                      <div className="flex items-start justify-between gap-3">
                        <p>{a.statement}</p>
                        {a.owner_is_user ? <Chip tone="accent">you</Chip> : a.owner ? <Chip>{a.owner}</Chip> : null}
                      </div>
                      <Link href={`/conversations/${a.conversation_id}`} className="text-xs text-muted hover:underline">
                        {a.conversation_title} · {formatDate(a.conversation_date)}
                        {a.due_date && ` · due ${formatDate(a.due_date)}`}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
