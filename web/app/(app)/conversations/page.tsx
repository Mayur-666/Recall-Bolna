"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { AddConversationForm } from "@/components/add-conversation-form";
import { EvidenceCard } from "@/components/evidence-card";
import { EmptyState, ErrorState, Spinner, StatusBadge, formatDate } from "@/components/ui";
import { ApiError, apiFetch, useApi } from "@/lib/api";
import type { Conversation, SearchResult } from "@/lib/types";

const STATUS_COPY: Record<SearchResult["status"], string> = {
  found: "Found",
  ambiguous: "Several conversations match — Recall would ask which one you mean.",
  no_reliable_memory: "No reliable memory of that.",
  error: "Search failed.",
};

export default function ConversationsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const listPath = `/api/v1/conversations${statusFilter ? `?status=${statusFilter}` : ""}`;
  const { data, error, loading, reload } = useApi<Conversation[]>(listPath);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchResult | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  // Poll while anything is still being processed.
  const busy = data?.some((c) => c.status === "queued" || c.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => void reload(), 3000);
    return () => clearInterval(t);
  }, [busy, reload]);

  async function runSearch(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError(null);
    try {
      setSearch(await apiFetch<SearchResult>("/api/v1/search", { method: "POST", body: JSON.stringify({ question: query }) }));
    } catch (err) {
      setSearchError(err instanceof ApiError ? err.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  async function retry(id: string) {
    await apiFetch(`/api/v1/conversations/${id}/retry`, { method: "POST" });
    await reload();
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight">Conversations</h1>
          <p className="text-sm text-muted">Your memory library. Add transcripts; Recall extracts decisions, promises and people.</p>
        </div>
        {!adding && (
          <button onClick={() => setAdding(true)} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90">
            Add conversation
          </button>
        )}
      </div>

      {adding && (
        <AddConversationForm
          onCancel={() => setAdding(false)}
          onCreated={() => {
            setAdding(false);
            void reload();
          }}
        />
      )}

      <section className="space-y-3">
        <form onSubmit={runSearch} className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your memories"
            className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          />
          <button type="submit" disabled={searching} className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium hover:bg-white/5">
            {searching ? "Searching…" : "Search"}
          </button>
        </form>
        {searchError && <ErrorState message={searchError} />}
        {search && (
          <div className="space-y-2">
            <p className="text-sm text-muted">
              {STATUS_COPY[search.status]} · {search.timings_ms.total} ms{search.degraded && " · keyword-only (embedding service unavailable)"}
              {search.pending_conversations.length > 0 && ` · still processing: ${search.pending_conversations.join(", ")}`}
              {search.failed_conversations.length > 0 && ` · failed: ${search.failed_conversations.join(", ")}`}
            </p>
            <div className="grid gap-2 md:grid-cols-2">
              {search.results.map((e) => (
                <EvidenceCard key={e.ref} e={e} />
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Library</h2>
          <select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-line bg-surface px-2 py-1 text-sm"
          >
            <option value="">All statuses</option>
            <option value="ready">Ready</option>
            <option value="processing">Processing</option>
            <option value="queued">Queued</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        {loading && !data && <Spinner />}
        {error && <ErrorState message={error.message} onRetry={reload} />}
        {data && data.length === 0 && (
          <EmptyState title="No conversations yet">Add a transcript to start building your memory.</EmptyState>
        )}
        {data && data.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-line bg-surface">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-2">Title</th>
                  <th className="px-4 py-2">Date</th>
                  <th className="hidden px-4 py-2 md:table-cell">Participants</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-2">
                      <Link href={`/conversations/${c.id}`} className="font-medium hover:underline">
                        {c.title}
                      </Link>
                      {c.is_sample && <span className="ml-2 text-xs text-muted">sample</span>}
                      {c.status === "failed" && c.error_message && <p className="text-xs text-rose-300">{c.error_message}</p>}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-muted">{formatDate(c.conversation_date)}</td>
                    <td className="hidden px-4 py-2 text-muted md:table-cell">{c.participants.join(", ") || "—"}</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-4 py-2 text-right">
                      {c.status === "failed" && (
                        <button onClick={() => void retry(c.id)} className="rounded-md border border-line px-2 py-1 text-xs font-medium hover:bg-white/5">
                          Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
