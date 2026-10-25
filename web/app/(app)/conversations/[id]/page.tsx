"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { TranscriptView } from "@/components/transcript-view";
import { Card, Chip, DecisionStateChip, EmptyState, ErrorState, Spinner, StatusBadge, formatDate } from "@/components/ui";
import { apiFetch, useApi } from "@/lib/api";
import type { ConversationDetail, MemoryItem } from "@/lib/types";

const STATE_ORDER = ["decided", "proposed", "unresolved", "rejected", "superseded"];

function ItemRow({ item, onShow, extra }: { item: MemoryItem; onShow: (id: string) => void; extra?: React.ReactNode }) {
  return (
    <li className="space-y-1 py-2 text-sm">
      <div className="flex items-start justify-between gap-3">
        <p className={item.decision_state === "superseded" ? "text-muted line-through" : ""}>{item.statement}</p>
        <span className="flex shrink-0 items-center gap-1">
          <DecisionStateChip state={item.decision_state} />
          {extra}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
        {item.speaker && <span>said by {item.speaker}</span>}
        {item.due_date && <span>due {formatDate(item.due_date)}</span>}
        <button onClick={() => onShow(item.id)} className="text-accent hover:underline">
          Show in transcript
        </button>
      </div>
    </li>
  );
}

export default function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error, loading, reload } = useApi<ConversationDetail>(`/api/v1/conversations/${id}`);
  const [active, setActive] = useState<string | null>(null);

  const processing = data && (data.status === "queued" || data.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(() => void reload(), 3000);
    return () => clearInterval(t);
  }, [processing, reload]);

  useEffect(() => {
    if (active) document.getElementById(`ev-${active}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [active]);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return null;

  const items = data.memory_items;
  const decisions = items.filter((i) => i.kind === "decision").sort((a, b) => STATE_ORDER.indexOf(a.decision_state ?? "") - STATE_ORDER.indexOf(b.decision_state ?? ""));
  const actions = items.filter((i) => i.kind === "commitment" || i.kind === "action_item");
  const facts = items.filter((i) => i.kind === "fact" || i.kind === "date");
  const people = items.filter((i) => i.kind === "person");

  async function del() {
    if (!window.confirm("Delete this conversation and everything Recall extracted from it?")) return;
    await apiFetch(`/api/v1/conversations/${id}`, { method: "DELETE" });
    router.push("/conversations");
  }

  async function retry() {
    await apiFetch(`/api/v1/conversations/${id}/retry`, { method: "POST" });
    await reload();
  }

  return (
    <div className="space-y-6">
      <Link href="/conversations" className="text-sm text-muted hover:text-ink">
        ← Conversations
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>
          <p className="mt-1 text-sm text-muted">
            {formatDate(data.conversation_date)}
            {data.participants.length > 0 && ` · ${data.participants.join(", ")}`}
            {data.self_speaker && ` · you are ${data.self_speaker}`}
            {data.is_sample && " · sample conversation"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={data.status} />
          <button onClick={del} className="rounded-md border border-line px-3 py-1 text-sm text-rose-300 hover:bg-rose-500/10">
            Delete
          </button>
        </div>
      </header>

      {data.status === "failed" && (
        <ErrorState message={`Processing failed: ${data.error_message ?? "unknown error"}. Searches won't find this conversation until it succeeds.`} onRetry={retry} />
      )}
      {processing && <Spinner label="Processing: extracting decisions, people and commitments…" />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <Card>
            <h2 className="font-semibold">Decisions</h2>
            <div data-testid="decisions">
              {decisions.length === 0 ? (
                <p className="mt-2 text-sm text-muted">No decisions found.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {decisions.map((d) => (
                    <ItemRow key={d.id} item={d} onShow={setActive} extra={d.superseded_by_id ? <Chip tone="rose">see newer</Chip> : null} />
                  ))}
                </ul>
              )}
            </div>
          </Card>
          <Card>
            <h2 className="font-semibold">Commitments &amp; action items</h2>
            {actions.length === 0 ? (
              <p className="mt-2 text-sm text-muted">None found.</p>
            ) : (
              <ul className="divide-y divide-line">
                {actions.map((a) => (
                  <ItemRow
                    key={a.id}
                    item={a}
                    onShow={setActive}
                    extra={a.owner_is_user ? <Chip tone="accent">you</Chip> : a.owner ? <Chip>{a.owner}</Chip> : null}
                  />
                ))}
              </ul>
            )}
          </Card>
          {(facts.length > 0 || people.length > 0) && (
            <Card>
              <h2 className="font-semibold">Facts, dates &amp; people</h2>
              <ul className="divide-y divide-line">
                {[...facts, ...people].map((f) => (
                  <ItemRow key={f.id} item={f} onShow={setActive} />
                ))}
              </ul>
            </Card>
          )}
        </div>
        <div className="space-y-2">
          <h2 className="font-semibold">Original transcript</h2>
          {data.transcript_text ? (
            <TranscriptView text={data.transcript_text} items={items} activeId={active} />
          ) : (
            <EmptyState title="No transcript text" />
          )}
          <p className="text-xs text-muted">Highlighted passages are the exact evidence each memory was extracted from.</p>
        </div>
      </div>
    </div>
  );
}
