"use client";

import { useEffect, useState } from "react";
import { AddConversationForm } from "@/components/add-conversation-form";
import { TranscriptView } from "@/components/transcript-view";
import {
  DecisionStateChip,
  EmptyState,
  ErrorState,
  Spinner,
  StatusBadge,
  formatDate,
} from "@/components/ui";
import { ApiError, apiFetch, useApi } from "@/lib/api";
import type {
  CallSession,
  Conversation,
  ConversationDetail,
  Overview,
  User,
} from "@/lib/types";

export type DrawerTab = "conversations" | "add" | "calls" | "overview";

const STATE_ORDER = ["decided", "proposed", "unresolved", "rejected", "superseded"];
const E164 = /^\+[1-9]\d{7,14}$/;

interface SideDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab: DrawerTab;
  onTabChange: (tab: DrawerTab) => void;
  selectedConversationId: string | null;
  onSelectConversation: (id: string | null) => void;
  highlightMemoryId?: string | null;
  onMemoryGraphChanged?: () => void;
  onLogout?: () => void;
}

export function SideDrawer({
  isOpen,
  onClose,
  activeTab,
  onTabChange,
  selectedConversationId,
  onSelectConversation,
  highlightMemoryId,
  onMemoryGraphChanged,
  onLogout,
}: SideDrawerProps) {
  // Listen for Escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-300 ${
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out Drawer Panel */}
      <aside
        role="dialog"
        aria-label="Mission Control Panel"
        aria-modal="true"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-xl md:max-w-2xl flex-col border-l border-line bg-paper/95 backdrop-blur-xl shadow-2xl transition-transform duration-300 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-[#7c5cff] to-[#3ee6c4] text-xs font-bold text-[#061018]">
              R
            </span>
            <span className="font-display font-semibold tracking-tight text-white">
              Mission Control
            </span>
          </div>

          <button
            onClick={onClose}
            aria-label="Close panel"
            className="grid h-8 w-8 place-items-center rounded-lg border border-line text-muted hover:border-accent hover:text-white transition"
          >
            ✕
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-line px-6 pt-3 text-sm gap-2 overflow-x-auto">
          <button
            onClick={() => {
              onSelectConversation(null);
              onTabChange("conversations");
            }}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-medium transition ${
              activeTab === "conversations" || selectedConversationId
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            <span>💬 Conversations</span>
          </button>

          <button
            onClick={() => {
              onSelectConversation(null);
              onTabChange("add");
            }}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-medium transition ${
              activeTab === "add" && !selectedConversationId
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            <span>➕ Add Transcript</span>
          </button>

          <button
            onClick={() => {
              onSelectConversation(null);
              onTabChange("calls");
            }}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-medium transition ${
              activeTab === "calls" && !selectedConversationId
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            <span>📞 Voice Calls</span>
          </button>

          <button
            onClick={() => {
              onSelectConversation(null);
              onTabChange("overview");
            }}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 font-medium transition ${
              activeTab === "overview" && !selectedConversationId
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            <span>📊 Overview</span>
          </button>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6 custom-scrollbar">
          {selectedConversationId ? (
            <ConversationDetailDrawer
              id={selectedConversationId}
              highlightMemoryId={highlightMemoryId}
              onBack={() => onSelectConversation(null)}
              onDeleted={() => {
                onSelectConversation(null);
                onMemoryGraphChanged?.();
              }}
            />
          ) : activeTab === "conversations" ? (
            <ConversationsListDrawer
              onSelect={(id) => onSelectConversation(id)}
              onAddNew={() => onTabChange("add")}
            />
          ) : activeTab === "add" ? (
            <div className="space-y-4">
              <h2 className="font-display text-lg font-semibold text-white">Add a Conversation</h2>
              <p className="text-xs text-muted">
                Paste meeting transcripts or upload .txt / .vtt. Recall automatically extracts key
                decisions, promises, and facts into the constellation.
              </p>
              <AddConversationForm
                onCreated={(c) => {
                  onMemoryGraphChanged?.();
                  onSelectConversation(c.id);
                }}
                onCancel={() => onTabChange("conversations")}
              />
            </div>
          ) : activeTab === "calls" ? (
            <CallsDrawer />
          ) : (
            <OverviewDrawer onSelectConversation={onSelectConversation} />
          )}
        </div>

        {/* Drawer Footer */}
        <DrawerFooter onLogout={onLogout} />
      </aside>
    </>
  );
}

// ---------------------------------------------------------
// Sub-views
// ---------------------------------------------------------

function ConversationsListDrawer({
  onSelect,
  onAddNew,
}: {
  onSelect: (id: string) => void;
  onAddNew: () => void;
}) {
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");
  const listPath = `/api/v1/conversations${filter ? `?status=${filter}` : ""}`;
  const { data, loading, error, reload } = useApi<Conversation[]>(listPath);

  const busy = data?.some((c) => c.status === "queued" || c.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => void reload(), 3000);
    return () => clearInterval(t);
  }, [busy, reload]);

  const filtered = (data ?? []).filter((c) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      c.title.toLowerCase().includes(q) ||
      c.participants.some((p) => p.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold text-white">Conversations</h2>
        <button
          onClick={onAddNew}
          className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
        >
          Add conversation
        </button>
      </div>

      <div className="flex items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter conversations or people..."
          className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-xs outline-none focus:border-accent"
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-line bg-surface px-2.5 py-2 text-xs text-muted outline-none focus:border-accent"
        >
          <option value="">All statuses</option>
          <option value="ready">Ready</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {loading && !data && <Spinner label="Loading conversation memory..." />}
      {error && <ErrorState message={error.message} onRetry={reload} />}

      {!loading && filtered.length === 0 && (
        <EmptyState title="No conversations found">
          {query ? "Try matching a different keyword." : "Add a transcript to populate the memory field."}
        </EmptyState>
      )}

      <ul className="space-y-2">
        {filtered.map((c) => (
          <li
            key={c.id}
            role="row"
            aria-label={c.title}
            onClick={() => onSelect(c.id)}
            className="group cursor-pointer rounded-xl border border-line bg-surface/80 p-3.5 transition hover:border-accent/60 hover:bg-surface"
          >
            <div className="flex items-start justify-between gap-3">
              <a
                role="link"
                onClick={(e) => {
                  e.preventDefault();
                  onSelect(c.id);
                }}
                className="text-sm font-medium text-white group-hover:text-accent transition"
              >
                {c.title}
              </a>
              <StatusBadge status={c.status} />
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span>{formatDate(c.conversation_date)}</span>
              {c.participants.length > 0 && (
                <>
                  <span>·</span>
                  <span>{c.participants.join(", ")}</span>
                </>
              )}
              {c.is_sample && (
                <>
                  <span>·</span>
                  <span className="rounded bg-accent/20 px-1 text-[10px] text-accent">Sample</span>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConversationDetailDrawer({
  id,
  highlightMemoryId,
  onBack,
  onDeleted,
}: {
  id: string;
  highlightMemoryId?: string | null;
  onBack: () => void;
  onDeleted: () => void;
}) {
  const { data, loading, error, reload } = useApi<ConversationDetail>(`/api/v1/conversations/${id}`);
  const [activeMemory, setActiveMemory] = useState<string | null>(highlightMemoryId ?? null);
  const [detailTab, setDetailTab] = useState<"transcript" | "memories">("transcript");

  const processing = data && (data.status === "queued" || data.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(() => void reload(), 3000);
    return () => clearInterval(t);
  }, [processing, reload]);

  useEffect(() => {
    if (highlightMemoryId) {
      setActiveMemory(highlightMemoryId);
      setDetailTab("transcript");
    }
  }, [highlightMemoryId, id]);

  useEffect(() => {
    if (activeMemory && detailTab === "transcript") {
      setTimeout(() => {
        document.getElementById(`ev-${activeMemory}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 50);
    }
  }, [activeMemory, detailTab]);

  if (loading && !data) return <Spinner label="Reading transcript & memories..." />;
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return null;

  async function handleDelete() {
    if (!window.confirm("Delete this conversation and its extracted memories from the constellation?")) return;
    await apiFetch(`/api/v1/conversations/${id}`, { method: "DELETE" });
    onDeleted();
  }

  const items = data.memory_items;
  const decisions = items
    .filter((i) => i.kind === "decision")
    .sort((a, b) => STATE_ORDER.indexOf(a.decision_state ?? "") - STATE_ORDER.indexOf(b.decision_state ?? ""));
  const actions = items.filter((i) => i.kind === "commitment" || i.kind === "action_item");
  const facts = items.filter((i) => i.kind === "fact" || i.kind === "date");

  return (
    <div className="space-y-5">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-white transition"
      >
        ← Back to list
      </button>

      <div>
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-display text-xl font-bold text-white">{data.title}</h2>
          <StatusBadge status={data.status} />
        </div>
        <p className="mt-1 text-xs text-muted">
          {formatDate(data.conversation_date)} · Participants: {data.participants.join(", ") || "None listed"}
        </p>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-3 border-b border-line pb-4 text-xs">
        <button
          onClick={handleDelete}
          className="text-rose-400 hover:text-rose-300 transition"
        >
          Delete conversation
        </button>
      </div>

      {/* View Switcher: Transcript vs Extracted Memories */}
      <div className="flex border-b border-line gap-4 text-xs font-medium">
        <button
          onClick={() => setDetailTab("transcript")}
          className={`pb-2.5 border-b-2 transition flex items-center gap-1.5 ${
            detailTab === "transcript"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-muted hover:text-white"
          }`}
        >
          <span>📜 Full Transcript</span>
          {activeMemory && (
            <span className="h-1.5 w-1.5 rounded-full bg-accent-2 animate-ping" />
          )}
        </button>
        <button
          onClick={() => setDetailTab("memories")}
          className={`pb-2.5 border-b-2 transition ${
            detailTab === "memories"
              ? "border-accent text-accent font-semibold"
              : "border-transparent text-muted hover:text-white"
          }`}
        >
          💡 Extracted Memories ({items.length})
        </button>
      </div>

      {detailTab === "transcript" ? (
        /* Transcript with Evidence Highlights */
        <div className="space-y-2 animate-in fade-in">
          <p className="text-xs text-muted">
            Highlighted text corresponds to extracted memories and verified quotes.
          </p>
          <TranscriptView
            text={data.transcript_text}
            items={data.memory_items}
            activeId={activeMemory}
          />
        </div>
      ) : (
        /* Extracted Memories Summary */
        <div className="space-y-4 animate-in fade-in">
          {decisions.length > 0 && (
            <div data-testid="decisions" className="space-y-1.5">
              <span className="text-xs font-medium uppercase tracking-wider text-muted">Decisions</span>
              <ul className="space-y-1.5">
                {decisions.map((d) => (
                  <li
                    key={d.id}
                    onClick={() => {
                      setActiveMemory(d.id);
                      setDetailTab("transcript");
                    }}
                    className={`cursor-pointer rounded-lg border p-2 text-xs transition ${
                      activeMemory === d.id
                        ? "border-accent bg-accent/15"
                        : "border-line bg-surface hover:border-accent/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className={d.decision_state === "superseded" ? "text-muted line-through" : "text-ink"}>
                        {d.statement}
                      </p>
                      <DecisionStateChip state={d.decision_state} />
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
                      <span>{d.speaker ? `by ${d.speaker}` : ""}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMemory(d.id);
                          setDetailTab("transcript");
                        }}
                        className="text-accent hover:underline"
                      >
                        Show in transcript →
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {actions.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-xs font-medium uppercase tracking-wider text-muted">Action Items & Commitments</span>
              <ul className="space-y-1.5">
                {actions.map((a) => (
                  <li
                    key={a.id}
                    onClick={() => {
                      setActiveMemory(a.id);
                      setDetailTab("transcript");
                    }}
                    className={`cursor-pointer rounded-lg border p-2 text-xs transition ${
                      activeMemory === a.id
                        ? "border-accent bg-accent/15"
                        : "border-line bg-surface hover:border-accent/50"
                    }`}
                  >
                    <p className="text-ink">{a.statement}</p>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
                      <span>{a.owner ? `Owner: ${a.owner}` : ""}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMemory(a.id);
                          setDetailTab("transcript");
                        }}
                        className="text-accent hover:underline"
                      >
                        Show in transcript →
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {facts.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-xs font-medium uppercase tracking-wider text-muted">Key Facts</span>
              <ul className="space-y-1.5">
                {facts.map((f) => (
                  <li
                    key={f.id}
                    onClick={() => {
                      setActiveMemory(f.id);
                      setDetailTab("transcript");
                    }}
                    className={`cursor-pointer rounded-lg border p-2 text-xs transition ${
                      activeMemory === f.id
                        ? "border-accent bg-accent/15"
                        : "border-line bg-surface hover:border-accent/50"
                    }`}
                  >
                    <p className="text-ink">{f.statement}</p>
                    <div className="mt-1 flex justify-end text-[11px]">
                      <span className="text-accent hover:underline">Show in transcript →</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CallsDrawer() {
  const calls = useApi<CallSession[]>("/api/v1/calls");
  const [phone, setPhone] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSuccess, setPhoneSuccess] = useState<string | null>(null);
  const [calling, setCalling] = useState(false);
  const [selectedCall, setSelectedCall] = useState<CallSession | null>(null);

  async function handlePhoneCall(e: React.FormEvent) {
    e.preventDefault();
    setPhoneError(null);
    setPhoneSuccess(null);
    const cleaned = phone.replace(/[\s-]/g, "");
    if (!E164.test(cleaned)) {
      setPhoneError("Use international E.164 format with + and country code, e.g. +919876543210.");
      return;
    }
    setCalling(true);
    try {
      await apiFetch<{ call_session_id: string; execution_id: string }>("/api/v1/calls/phone", {
        method: "POST",
        body: JSON.stringify({ phone: cleaned }),
      });
      setPhoneSuccess("Call initiated! Your phone will ring shortly.");
      void calls.reload();
    } catch (err) {
      setPhoneError(err instanceof ApiError ? err.message : "The phone call could not be placed.");
    } finally {
      setCalling(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Phone Call Fallback Form */}
      <details className="rounded-xl border border-line bg-surface p-4 text-sm" open>
        <summary className="cursor-pointer font-semibold text-white hover:text-accent transition">
          Call my phone instead
        </summary>
        <p className="mt-1 text-xs text-muted">
          If browser audio or WebRTC isn&apos;t convenient, Recall can dial your phone directly via Bolna.
        </p>
        <form onSubmit={handlePhoneCall} className="mt-3 flex flex-col gap-2">
          <input
            type="tel"
            aria-label="Phone number"
            placeholder="+1 555 123 4567"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="rounded-lg border border-line bg-paper px-3 py-2 text-xs outline-none focus:border-accent"
          />
          {phoneError && (
            <p role="alert" className="text-xs text-rose-300">
              {phoneError}
            </p>
          )}
          {phoneSuccess && (
            <p className="text-xs text-emerald-300">
              {phoneSuccess}
            </p>
          )}
          <button
            type="submit"
            disabled={calling}
            className="rounded-lg bg-accent/80 hover:bg-accent px-4 py-2 text-xs font-semibold text-white disabled:opacity-50 transition"
          >
            {calling ? "Dialing..." : "Call me"}
          </button>
        </form>
      </details>

      {/* Past Voice Calls */}
      <div className="space-y-3">
        <h2 className="font-display text-sm font-semibold text-white">Past calls</h2>
        {calls.loading && !calls.data && <Spinner label="Loading call logs..." />}
        {calls.data && calls.data.length === 0 && (
          <EmptyState title="No calls yet">
            Tap the orb in the center of the space canvas to have your first voice conversation.
          </EmptyState>
        )}

        <ul className="space-y-2">
          {calls.data?.map((c) => (
            <li
              key={c.id}
              onClick={() => setSelectedCall(selectedCall?.id === c.id ? null : c)}
              className="cursor-pointer rounded-xl border border-line bg-surface/80 p-3 text-xs transition hover:border-accent"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-white">
                  {c.channel === "phone" ? "📞 Phone call" : "🌐 Web call"}
                </span>
                <span className="text-muted">{formatDate(c.created_at)}</span>
              </div>
              <div className="mt-1 text-muted">
                Status: {c.status} {c.ended_at ? `· ${Math.max(1, Math.round((new Date(c.ended_at).getTime() - new Date(c.created_at).getTime()) / 1000))}s` : ""}
              </div>

              {selectedCall?.id === c.id && c.transcript && (
                <div className="mt-3 rounded-lg border border-line bg-black/40 p-3 text-ink whitespace-pre-wrap font-sans text-xs">
                  <div className="text-[11px] font-semibold text-accent mb-1 uppercase tracking-wider">
                    Bolna Call Transcript
                  </div>
                  {c.transcript}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function OverviewDrawer({
  onSelectConversation,
}: {
  onSelectConversation: (id: string) => void;
}) {
  const { data, loading, error, reload } = useApi<Overview>("/api/v1/overview");

  if (loading && !data) return <Spinner label="Loading memory metrics..." />;
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-lg font-semibold text-white">Memory Overview</h2>
        <p className="text-xs text-muted">High-level status of your remembered universe.</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-line bg-surface p-3.5">
          <div data-testid="stat-conversations" className="text-2xl font-bold text-white">{data.conversation_count}</div>
          <div className="text-xs text-muted">Conversations</div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-3.5">
          <div className="text-2xl font-bold text-accent-2">{data.memory_count}</div>
          <div className="text-xs text-muted">Extracted Memories</div>
        </div>
      </div>

      {data.recent_decisions.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-display text-xs font-semibold uppercase tracking-wider text-muted">
            Recent decisions
          </h2>
          <ul className="space-y-2">
            {data.recent_decisions.slice(0, 5).map((d) => (
              <li
                key={d.id}
                onClick={() => onSelectConversation(d.conversation_id)}
                className="cursor-pointer rounded-lg border border-line bg-surface p-2.5 text-xs transition hover:border-accent"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-white">{d.statement}</span>
                  <DecisionStateChip state={d.decision_state} />
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  in {d.conversation_title} · {d.speaker ? `by ${d.speaker}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.open_action_items.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-display text-xs font-semibold uppercase tracking-wider text-muted">
            Open Action Items
          </h3>
          <ul className="space-y-2">
            {data.open_action_items.slice(0, 5).map((a) => (
              <li
                key={a.id}
                onClick={() => onSelectConversation(a.conversation_id)}
                className="cursor-pointer rounded-lg border border-line bg-surface p-2.5 text-xs transition hover:border-accent"
              >
                <p className="font-medium text-white">{a.statement}</p>
                <div className="mt-1 text-[11px] text-muted">
                  Owner: {a.owner_is_user ? "You" : a.owner ?? "unassigned"}
                  {a.due_date ? ` · Due ${formatDate(a.due_date)}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function DrawerFooter({ onLogout }: { onLogout?: () => void }) {
  const { data: user } = useApi<User>("/api/v1/auth/me");

  return (
    <div className="border-t border-line px-6 py-4 flex items-center justify-between text-xs text-muted">
      <div>
        {user?.email ? (
          <div>
            <span className="font-medium text-white">{user.display_name || user.email}</span>
            <div className="text-[11px] text-muted">{user.email}</div>
          </div>
        ) : (
          <span>Recall Space</span>
        )}
      </div>

      <button
        onClick={onLogout}
        className="rounded-lg border border-line px-3 py-1.5 text-muted hover:border-rose-400/50 hover:text-rose-300 transition"
      >
        Sign Out
      </button>
    </div>
  );
}
