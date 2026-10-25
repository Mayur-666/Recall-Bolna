"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { EvidenceCard } from "@/components/evidence-card";
import { FieldLegend, MemoryField } from "@/components/memory-field";
import { Card, Chip, DecisionStateChip, EmptyState, ErrorState, Spinner, StatusBadge, formatDate } from "@/components/ui";
import { ApiError, apiFetch, useApi } from "@/lib/api";
import type { MemoryGraph, Overview, SearchResult } from "@/lib/types";

const SUGGESTIONS = ["Which deployment provider did we pick?", "What did Priya say about WebSockets?", "What did I promise to do?", "When is the launch date?"];

const VERDICT: Record<SearchResult["status"], { text: string; cls: string }> = {
  found: { text: "Found it", cls: "text-emerald-300" },
  ambiguous: { text: "Which conversation do you mean?", cls: "text-amber-300" },
  no_reliable_memory: { text: "No reliable memory of that. Recall won't guess.", cls: "text-sky-300" },
  error: { text: "Search failed", cls: "text-rose-300" },
};

export default function DashboardPage() {
  const router = useRouter();
  const overview = useApi<Overview>("/api/v1/overview");
  const graph = useApi<MemoryGraph>("/api/v1/memories/graph");
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [pulse, setPulse] = useState(0);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  async function ask(q: string) {
    if (!q.trim()) return;
    setQuestion(q);
    setAsking(true);
    setAskError(null);
    try {
      const r = await apiFetch<SearchResult>("/api/v1/search", { method: "POST", body: JSON.stringify({ question: q }) });
      setResult(r);
      setPulse((p) => p + 1);
    } catch (e) {
      setAskError(e instanceof ApiError ? e.message : "Search failed.");
    } finally {
      setAsking(false);
    }
  }

  const data = overview.data;
  const lit = result && result.status !== "no_reliable_memory" ? result.results.map((e) => e.ref) : [];

  return (
    <div className="space-y-10">
      <section className="relative overflow-hidden rounded-3xl glass px-6 pb-6 pt-10 md:px-10">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-accent-2">Voice memory for your conversations</p>
          <h1 className="mt-3 font-display text-4xl font-bold tracking-tight md:text-6xl">
            Ask your past. <span className="text-gradient">It answers with proof.</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-muted">
            Every decision, promise and deadline from your conversations, alive in one field. Talk to Recall and watch it reach
            for the exact moment something was said, or admit when it simply doesn&apos;t know.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link
              href="/ask"
              className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[#7c5cff] to-[#3ee6c4] px-6 py-3 font-semibold text-[#061018] shadow-[0_0_40px_-6px_rgba(124,92,255,0.8)] transition hover:scale-[1.03]"
            >
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white/80" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white" />
              </span>
              Talk to Recall
            </Link>
            <Link href="/conversations" className="rounded-full border border-line px-6 py-3 font-medium text-ink hover:bg-white/5">
              Add a conversation
            </Link>
          </div>
        </div>

        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            void ask(question);
          }}
          className="mx-auto mt-8 flex max-w-2xl gap-2"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Try a question, and watch the memories light up"
            aria-label="Try a question"
            className="flex-1 rounded-full border border-line bg-black/30 px-5 py-3 text-sm outline-none placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent-soft"
          />
          <button type="submit" disabled={asking} className="rounded-full bg-accent px-5 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60">
            {asking ? "…" : "Ask"}
          </button>
        </form>
        <div className="mx-auto mt-3 flex max-w-3xl flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => void ask(s)} className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-accent hover:text-ink">
              {s}
            </button>
          ))}
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div>
            {graph.loading && !graph.data && <Spinner label="Gathering your memories…" />}
            {graph.error && <ErrorState message={graph.error.message} onRetry={graph.reload} />}
            {graph.data && graph.data.nodes.length === 0 && (
              <EmptyState title="Your memory field is empty">Add a conversation and watch it fill with stars.</EmptyState>
            )}
            {graph.data && graph.data.nodes.length > 0 && (
              <MemoryField
                graph={graph.data}
                highlight={lit}
                pulseKey={pulse}
                height={500}
                centerLabel={asking ? "searching…" : undefined}
                onSelect={(n) => router.push(`/conversations/${n.conversation_id}`)}
              />
            )}
            <div className="mt-3 flex justify-center">
              <FieldLegend />
            </div>
          </div>
          <aside className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
              {!result && !askError && (
                <div className="rounded-2xl border border-dashed border-line p-5 text-sm text-muted">
                  <p className="font-display text-base font-semibold text-ink">How to read the field</p>
                  <p className="mt-2">Each star is a memory Recall pulled from a conversation. Stars cluster by topic. Pink dashed arrows mean a decision was later changed.</p>
                  <p className="mt-2">Ask something and the evidence lights up, with the exact quotes listed here. If nothing reliable matches, the field stays dark and Recall says so.</p>
                </div>
              )}
              {askError && <ErrorState message={askError} />}
              {result && (
                <>
                  <p className={`text-sm font-semibold ${VERDICT[result.status].cls}`}>
                    {VERDICT[result.status].text}
                    <span className="ml-2 text-xs font-normal text-muted">
                      {result.results.length} source{result.results.length === 1 ? "" : "s"} · {result.timings_ms.total} ms
                      {result.degraded && " · keyword-only"}
                    </span>
                  </p>
                  {result.results.map((e, i) => (
                    <div key={`${pulse}-${e.ref}`} className="rise-in" style={{ animationDelay: `${300 + i * 110}ms` }}>
                      <EvidenceCard e={e} />
                    </div>
                  ))}
                </>
              )}
          </aside>
        </div>
      </section>

      {overview.error && <ErrorState message={overview.error.message} onRetry={overview.reload} />}
      {data && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              ["Conversations", data.conversation_count, "stat-conversations"],
              ["Memories extracted", data.memory_count, "stat-memories"],
              ["Needs attention", data.needs_attention.length, "stat-attention"],
            ].map(([label, value, id]) => (
              <Card key={id as string}>
                <p className="text-sm text-muted">{label}</p>
                <p data-testid={id as string} className="mt-1 font-display text-4xl font-bold">
                  {value}
                </p>
              </Card>
            ))}
          </div>

          {data.needs_attention.length > 0 && (
            <Card>
              <h2 className="font-display font-semibold">Needs attention</h2>
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
              <h2 className="font-display font-semibold">Recent decisions</h2>
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
              <h2 className="font-display font-semibold">Commitments &amp; action items</h2>
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
