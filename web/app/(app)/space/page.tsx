"use client";

import type { BolnaWebCall as BolnaWebCallType, CallError, Session } from "@bolna/web-call";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { SideDrawer, type DrawerTab } from "@/components/side-drawer";
import { SpaceCanvas } from "@/components/space-canvas";
import { Spinner } from "@/components/ui";
import { type OrbState } from "@/components/voice-orb";
import { ApiError, apiFetch, useApi } from "@/lib/api";
import type { CallEvent, MemoryGraph, SearchResult } from "@/lib/types";
import { useCallEvents } from "@/lib/use-call-events";

const SETUP_HINT = " See docs/bolna-setup.md.";
const SUGGESTIONS = [
  "Which deployment provider did we pick?",
  "What did Priya say about WebSockets?",
  "What did I promise to do?",
  "When is the launch date?",
];

function sdkErrorMessage(e: CallError, mintMessage: string | null): string {
  if (e.code === "mint_failed") return (mintMessage ?? "Recall couldn't start a Bolna web call.") + SETUP_HINT;
  if (e.code === "at_capacity" && e.scope === "not_enabled")
    return "Web Call isn't enabled on this Bolna account yet. Ask Bolna support to enable it, or use “Call my phone instead”." + SETUP_HINT;
  if (e.code === "at_capacity") return `Bolna is at its concurrent web-call limit (${e.scope ?? "unknown"}). Try again in a moment.`;
  if (e.code === "microphone_denied") return "Microphone access was blocked. Allow the microphone for this site and try again.";
  if (e.code === "autoplay_blocked") return "The browser blocked audio playback. Click the orb again to start.";
  if (e.code === "already_active") return "A call is already active.";
  return `${e.message || "The call failed."} (${e.code})`;
}

type Completed = Extract<CallEvent, { type: "tool_call_completed" }>;
type Started = Extract<CallEvent, { type: "tool_call_started" }>;

export default function SpacePage() {
  return (
    <Suspense fallback={<div className="grid h-screen place-items-center bg-[#050814]"><Spinner label="Loading space constellation..." /></div>}>
      <SpacePageContent />
    </Suspense>
  );
}

function SpacePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Data fetching for memory constellation
  const graph = useApi<MemoryGraph>("/api/v1/memories/graph");

  // Call & WebRTC Voice State
  const [callId, setCallId] = useState<string | null>(null);
  const [sdkState, setSdkState] = useState<"idle" | "connecting" | "ringing" | "active" | "ended" | "error">("idle");
  const [level, setLevel] = useState(0);
  const [callError, setCallError] = useState<string | null>(null);
  const callRef = useRef<BolnaWebCallType | null>(null);
  const mintMessage = useRef<string | null>(null);
  const callIdRef = useRef<string | null>(null);

  // Events streamed from Bolna execution
  const { events } = useCallEvents(callId);

  // Text search state (Floating Bottom HUD)
  const [question, setQuestion] = useState("");
  const [textResult, setTextResult] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [pulse, setPulse] = useState(0);

  // Side Drawer ("popup from side") state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("conversations");
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [highlightMemoryId, setHighlightMemoryId] = useState<string | null>(null);

  // Handle URL query parameters (e.g. ?drawer=conversations, ?conversationId=xxx)
  useEffect(() => {
    const dTab = searchParams.get("drawer");
    const convId = searchParams.get("conversationId");
    if (convId) {
      setSelectedConversationId(convId);
      setDrawerOpen(true);
    } else if (dTab === "conversations" || dTab === "add" || dTab === "calls" || dTab === "overview") {
      setDrawerTab(dTab);
      setDrawerOpen(true);
    }
  }, [searchParams]);

  useEffect(() => {
    callIdRef.current = callId;
  }, [callId]);

  useEffect(() => () => void callRef.current?.stop(), []);

  // Compute tool calls from voice agent
  const searches = useMemo(() => {
    const started = events.filter((e): e is Started => e.type === "tool_call_started");
    return started.map((s) => ({
      started: s,
      done: events.find((e): e is Completed => e.type === "tool_call_completed" && e.tool_call_id === s.tool_call_id),
      failed: events.some((e) => e.type === "tool_call_failed" && e.tool_call_id === s.tool_call_id),
    }));
  }, [events]);

  const lastSearch = searches[searches.length - 1];

  // Orb status determination
  const inCall = sdkState === "connecting" || sdkState === "ringing" || sdkState === "active";
  const orbState: OrbState = callError
    ? "error"
    : sdkState === "connecting" || sdkState === "ringing"
      ? sdkState
      : sdkState === "active"
        ? lastSearch && !lastSearch.done && !lastSearch.failed
          ? "searching"
          : lastSearch?.done?.status === "no_reliable_memory"
            ? "no-memory"
            : lastSearch?.done
              ? "found"
              : "listening"
        : sdkState === "ended"
          ? "ended"
          : "idle";

  // Determine highlighted memory references (from voice search or text search)
  const voiceLit = lastSearch?.done && lastSearch.done.status !== "no_reliable_memory"
    ? lastSearch.done.results?.map((r) => r.ref) ?? []
    : [];
  const textLit = textResult && textResult.status !== "no_reliable_memory"
    ? textResult.results.map((r) => r.ref)
    : [];
  const litRefs = Array.from(new Set([...voiceLit, ...textLit]));

  // Voice Web Call Action
  async function toggleWebCall() {
    if (inCall) {
      await callRef.current?.stop();
      return;
    }

    setCallError(null);
    mintMessage.current = null;
    setSdkState("connecting");

    try {
      const { BolnaWebCall } = await import("@bolna/web-call");
      const call = new BolnaWebCall({
        getSession: async () => {
          try {
            const r = await apiFetch<{ call_session_id: string; session: Session }>("/api/v1/calls/web-session", { method: "POST" });
            setCallId(r.call_session_id);
            return r.session;
          } catch (e) {
            mintMessage.current = e instanceof ApiError ? e.message : "Could not reach Recall backend.";
            throw e;
          }
        },
      });

      callRef.current = call;
      call.on("state-change", (s) => setSdkState(s === "idle" ? "idle" : s));
      call.on("volume-level", (v) => setLevel(v));
      call.on("error", (e) => {
        setCallError(sdkErrorMessage(e, mintMessage.current));
        setSdkState("error");
      });
      call.on("call-end", async () => {
        setLevel(0);
        setSdkState("ended");
        const id = callIdRef.current;
        if (id) await apiFetch(`/api/v1/calls/${id}/end`, { method: "POST" }).catch(() => undefined);
      });

      await call.start();
    } catch (e) {
      const fallback = e instanceof Error ? e.message : "The call could not start.";
      setCallError((prev) => prev ?? (mintMessage.current ?? fallback) + SETUP_HINT);
      setSdkState("error");
    }
  }

  // Text query action
  async function handleAskText(q: string) {
    if (!q.trim()) return;
    setQuestion(q);
    setSearching(true);
    try {
      const r = await apiFetch<SearchResult>("/api/v1/search", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      setTextResult(r);
      setPulse((p) => p + 1);
    } catch (e) {
      // Show error
      console.error("Text search failed:", e);
    } finally {
      setSearching(false);
    }
  }

  // Handle logout
  async function handleLogout() {
    try {
      await apiFetch("/api/v1/auth/logout", { method: "POST" });
    } finally {
      router.push("/login");
    }
  }

  // Open transcript in side drawer
  const openTranscript = (convId: string, memId?: string) => {
    setDrawerTab("conversations");
    setSelectedConversationId(convId);
    setHighlightMemoryId(memId ?? null);
    setDrawerOpen(true);
  };

  const orbButtonLabel = inCall ? "End call" : "Talk to Recall";

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#050814] text-ink font-sans">
      {/* 1. Header Bar Floating Over Canvas */}
      <header className="pointer-events-none absolute top-0 inset-x-0 z-30 flex items-center justify-between p-4 md:px-6">
        {/* Logo and Constellation Metrics */}
        <div className="pointer-events-auto flex items-center gap-4">
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-2.5 rounded-full border border-line bg-surface/70 px-3.5 py-1.5 backdrop-blur-md shadow-lg hover:border-accent transition group"
            title="Go to Landing Page"
          >
            <span className="grid h-6 w-6 place-items-center rounded-lg bg-gradient-to-br from-[#7c5cff] to-[#3ee6c4] text-xs font-bold text-[#061018]">
              R
            </span>
            <span className="font-display font-semibold tracking-tight text-white text-sm group-hover:text-accent transition">
              Recall
            </span>
          </button>

          <h1 className="font-display text-xs sm:text-sm font-semibold text-white/90">
            Talk to <span className="text-gradient">Recall</span>
          </h1>

          {graph.data && (
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-line bg-surface/50 px-3 py-1 text-xs text-muted backdrop-blur-md">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-2 animate-pulse" />
              <span>
                {graph.data.nodes.length} memories · {graph.data.clusters.length} clusters
              </span>
            </div>
          )}
        </div>

        {/* Live Call or Alert Toast & Hamburger Menu Button */}
        <div className="pointer-events-auto flex items-center gap-3">
          {callError && (
            <div role="alert" className="max-w-xs rounded-full border border-rose-400/40 bg-rose-500/20 px-3.5 py-1.5 text-xs text-rose-200 backdrop-blur-md truncate shadow-lg">
              {callError}
            </div>
          )}

          {inCall && (
            <div className="flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 backdrop-blur-md">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              <span>Voice Session Active</span>
            </div>
          )}

          {/* Hamburger Menu Button */}
          <button
            onClick={() => setDrawerOpen(true)}
            aria-label="Open mission control menu"
            className="group flex items-center gap-2.5 rounded-full border border-line bg-surface/80 px-4 py-2 text-xs font-semibold text-white backdrop-blur-md shadow-xl hover:border-accent hover:bg-surface transition"
          >
            <span className="text-base leading-none">☰</span>
            <span className="font-display tracking-wide">Menu</span>
            <span className="rounded-full bg-accent/30 px-1.5 py-0.2 text-[10px] text-accent font-bold">
              ✦
            </span>
          </button>
        </div>
      </header>

      {/* 2. Full-Screen Spatial Memory Map with Central Voice Orb */}
      <main className="h-full w-full">
        {graph.loading && !graph.data && (
          <div className="grid h-full w-full place-items-center bg-[#050814]">
            <Spinner label="Rendering celestial memory space..." />
          </div>
        )}

        {graph.data && (
          <SpaceCanvas
            graph={graph.data}
            highlightRefs={litRefs}
            pulseKey={pulse + (lastSearch?.done ? 1 : 0)}
            orbState={orbState}
            audioLevel={level}
            onOrbClick={() => void toggleWebCall()}
            orbLabel={orbButtonLabel}
            onSelectNode={() => {
              // Can select or highlight
            }}
            onInspectTranscript={openTranscript}
          />
        )}
      </main>

      {/* 3. Floating Left Side HUD for Retrieved Info & Evidence */}
      {textResult && (
        <aside
          aria-label="Retrieved Evidence"
          className="pointer-events-auto absolute left-6 top-20 z-30 flex max-h-[calc(100vh-140px)] w-80 md:w-96 flex-col rounded-2xl border border-line bg-surface-solid/95 backdrop-blur-xl shadow-2xl animate-in fade-in slide-in-from-left-4 overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-line bg-paper/50 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-accent-2 animate-pulse" />
              <span className="font-display text-xs font-semibold uppercase tracking-wider text-white">
                {textResult.status === "no_reliable_memory"
                  ? "Search Result"
                  : `Retrieved Info (${textResult.results.length})`}
              </span>
            </div>
            <button
              onClick={() => setTextResult(null)}
              className="grid h-6 w-6 place-items-center rounded-md text-muted hover:bg-white/10 hover:text-white transition"
              title="Close retrieved info"
            >
              ✕
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
            {question && (
              <div className="rounded-lg bg-black/40 px-3 py-2 text-xs border border-line/60">
                <span className="text-muted">Question: </span>
                <span className="font-medium text-white">&ldquo;{question}&rdquo;</span>
              </div>
            )}

            {textResult.status === "no_reliable_memory" ? (
              <div className="rounded-xl border border-sky-400/30 bg-sky-500/10 p-3.5 text-xs text-sky-200">
                No reliable memory of that in your conversations. Recall will not hallucinate.
              </div>
            ) : (
              <div className="space-y-2.5">
                {textResult.results.map((e) => (
                  <div
                    key={e.ref}
                    onClick={() => openTranscript(e.conversation_id, e.ref)}
                    className="group cursor-pointer rounded-xl border border-line bg-surface/90 p-3 text-xs transition hover:border-accent hover:bg-surface shadow-sm"
                  >
                    <div className="flex items-center justify-between text-muted text-[11px]">
                      <span className="font-semibold text-white group-hover:text-accent transition truncate max-w-[200px]">
                        {e.conversation_title}
                      </span>
                      <span>{e.speaker ? `by ${e.speaker}` : ""}</span>
                    </div>

                    {e.statement && (
                      <p className="mt-1 font-medium text-ink leading-snug">
                        {e.statement}
                      </p>
                    )}

                    <blockquote className="mt-1.5 border-l-2 border-accent-2/70 pl-2 text-muted italic text-[11px] line-clamp-3">
                      &ldquo;{e.excerpt}&rdquo;
                    </blockquote>

                    <div className="mt-2.5 flex items-center justify-between text-[11px]">
                      <span className="rounded bg-accent/20 px-1.5 py-0.5 text-[10px] uppercase font-semibold text-accent">
                        {e.kind}
                      </span>
                      <span className="text-accent hover:underline flex items-center gap-1 font-medium">
                        Open in transcript →
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* 4. Floating Bottom HUD / Search Pill */}
      <div className="pointer-events-none absolute bottom-6 inset-x-0 z-30 flex flex-col items-center gap-2 px-4">

        {/* Search input form */}
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            void handleAskText(question);
          }}
          className="pointer-events-auto flex w-full max-w-xl items-center gap-2 rounded-full border border-line bg-surface/90 px-4 py-2 backdrop-blur-xl shadow-2xl focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/40"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask anything or click the orb to speak..."
            aria-label="Try a question"
            className="flex-1 bg-transparent text-xs md:text-sm text-white outline-none placeholder:text-muted"
          />
          <button
            type="submit"
            disabled={searching}
            className="rounded-full bg-accent px-4 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90 disabled:opacity-60 transition"
          >
            {searching ? "Searching…" : "Ask"}
          </button>
        </form>

        {/* Suggestion Pills */}
        <div className="pointer-events-auto hidden sm:flex flex-wrap justify-center gap-1.5 max-w-2xl">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => void handleAskText(s)}
              className="rounded-full border border-line bg-surface/60 px-2.5 py-0.5 text-[11px] text-muted backdrop-blur hover:border-accent hover:text-white transition"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* 4. Hamburger Side Drawer ("popup from side") */}
      <SideDrawer
        isOpen={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedConversationId(null);
        }}
        activeTab={drawerTab}
        onTabChange={(tab) => setDrawerTab(tab)}
        selectedConversationId={selectedConversationId}
        onSelectConversation={(id) => setSelectedConversationId(id)}
        highlightMemoryId={highlightMemoryId}
        onMemoryGraphChanged={() => void graph.reload()}
        onLogout={handleLogout}
      />
    </div>
  );
}
