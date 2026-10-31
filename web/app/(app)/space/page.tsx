"use client";

import type { BolnaWebCall as BolnaWebCallType, CallError, Session } from "@bolna/web-call";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from "react";

import { EvidencePanel } from "@/components/evidence-panel";
import { Logo } from "@/components/logo";
import { SideDrawer, type DrawerTab } from "@/components/side-drawer";
import { SpaceCanvas } from "@/components/space-canvas";
import { Spinner } from "@/components/ui";
import { type OrbState } from "@/components/voice-orb";
import { ApiError, apiFetch, useApi } from "@/lib/api";
import type { CallEvent, MemoryGraph, SearchResult } from "@/lib/types";
import { useCallEvents } from "@/lib/use-call-events";
import { useMemoryEvents } from "@/lib/use-memory-events";
import { canSpeak, speak, stopSpeaking } from "@/lib/speech";
import { micConstraints, useMicrophones } from "@/lib/use-microphones";

const SETUP_HINT = " See docs/bolna-setup.md.";
// Mic level (0..1) that counts as "the user made a sound".
const VOICE_THRESHOLD = 0.04;
// How long into a call we wait for any sound before warning that the mic is silent.
const SILENT_MIC_MS = 7000;

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

function audioSender(call: BolnaWebCallType | null): RTCRtpSender | null {
  // peerConnection() is not in the SDK's public types, but it is a plain method at runtime.
  const pc = (call as unknown as { peerConnection?: () => RTCPeerConnection | null } | null)?.peerConnection?.();
  return pc?.getSenders().find((s) => s.track?.kind === "audio") ?? null;
}

export default function SpacePage() {
  return (
    <Suspense fallback={<div className="grid h-screen place-items-center bg-paper"><Spinner label="Loading your memories…" /></div>}>
      <SpacePageContent />
    </Suspense>
  );
}

function SpacePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const graph = useApi<MemoryGraph>("/api/v1/memories/graph");
  const mic = useMicrophones();

  // Call & WebRTC Voice State
  const [callId, setCallId] = useState<string | null>(null);
  const [sdkState, setSdkState] = useState<"idle" | "connecting" | "ringing" | "active" | "ended" | "error">("idle");
  const [level, setLevel] = useState(0);
  const [userMicLevel, setUserMicLevel] = useState(0);
  const [callError, setCallError] = useState<string | null>(null);
  const [micProblem, setMicProblem] = useState<string | null>(null);
  const [micLabel, setMicLabel] = useState<string>("");
  // Typed-question answers read aloud (see handleAskText); drives the orb while speaking.
  const [speaking, setSpeaking] = useState(false);
  const [speechLevel, setSpeechLevel] = useState(0);
  const callRef = useRef<BolnaWebCallType | null>(null);
  const mintMessage = useRef<string | null>(null);
  const callIdRef = useRef<string | null>(null);
  const micAudioCtxRef = useRef<AudioContext | null>(null);
  const micIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heardUserRef = useRef(false);
  // When the mic last carried speech; the "Hearing you" label holds briefly so it doesn't flicker between words.
  const lastVoiceAtRef = useRef(0);
  const callStartedAtRef = useRef<number | null>(null);

  async function monitorTrack(track: MediaStreamTrack) {
    stopMicMonitoring(false);
    setMicLabel(track.label);
    if (track.readyState !== "live") {
      setMicProblem(`The microphone “${track.label || "default"}” isn't delivering audio. Pick another one below.`);
      return;
    }
    track.onmute = () => setMicProblem(`“${track.label || "Your microphone"}” was muted by the system or browser.`);
    track.onunmute = () => setMicProblem(null);
    try {
      const AudioCtxClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtxClass) return;
      const audioCtx = new AudioCtxClass();
      // Created after awaits, so it may start suspended and read silence forever unless resumed.
      await audioCtx.resume().catch(() => undefined);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      audioCtx.createMediaStreamSource(new MediaStream([track])).connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      micAudioCtxRef.current = audioCtx;
      micIntervalRef.current = setInterval(() => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.min(1, Math.sqrt(sum / data.length) * 4);
        setUserMicLevel(rms);
        if (rms > VOICE_THRESHOLD) lastVoiceAtRef.current = Date.now();
        if (rms > VOICE_THRESHOLD && !heardUserRef.current) {
          heardUserRef.current = true;
          setMicProblem(null);
        }
      }, 100);
    } catch (err) {
      console.warn("Could not attach local microphone monitor:", err);
    }
  }

  function stopMicMonitoring(resetHeard = true) {
    if (micIntervalRef.current) clearInterval(micIntervalRef.current);
    micIntervalRef.current = null;
    if (micAudioCtxRef.current) void micAudioCtxRef.current.close().catch(() => undefined);
    micAudioCtxRef.current = null;
    setUserMicLevel(0);
    if (resetHeard) {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }

  function armSilenceCheck() {
    heardUserRef.current = false;
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = setTimeout(() => {
      if (!heardUserRef.current) {
        setMicProblem(
          "Recall isn't receiving any sound from your microphone. Pick a different input below, or check that it isn't muted in Windows/macOS sound settings.",
        );
      }
    }, SILENT_MIC_MS);
  }

  // Swap the live call's microphone without hanging up.
  async function switchMic(id: string) {
    mic.setDeviceId(id);
    const sender = audioSender(callRef.current);
    if (!sender) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: micConstraints(id), video: false });
      const next = stream.getAudioTracks()[0];
      const prev = sender.track;
      await sender.replaceTrack(next);
      prev?.stop();
      setMicProblem(null);
      armSilenceCheck();
      await monitorTrack(next);
    } catch (err) {
      setMicProblem(`Couldn't switch microphone: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  // Events streamed from Bolna execution
  const { events } = useCallEvents(callId);

  // Text search state (Floating Bottom HUD)
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [textResult, setTextResult] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [pulse, setPulse] = useState(0);

  // Side Drawer state
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
  const toolCalls = useMemo(() => {
    const started = events.filter((e): e is Started => e.type === "tool_call_started");
    return started.map((s) => ({
      started: s,
      done: events.find((e): e is Completed => e.type === "tool_call_completed" && e.tool_call_id === s.tool_call_id),
      failed: events.some((e) => e.type === "tool_call_failed" && e.tool_call_id === s.tool_call_id),
    }));
  }, [events]);

  // The orb follows whatever the agent did last; the evidence panel and lit memories follow searches only.
  const lastTool = toolCalls[toolCalls.length - 1];
  const searches = toolCalls.filter((t) => t.started.tool === "search_memories");
  const lastSearch = searches[searches.length - 1];
  const lastDone = lastSearch?.done;
  const saves = toolCalls.filter((t) => t.started.tool === "save_memory" && t.done);
  const lastSave = saves[saves.length - 1]?.done;

  // A voice answer shows its evidence in the same panel as a typed question.
  useEffect(() => {
    if (!lastDone || !lastSearch) return;
    setAnswer(null);
    setAskedQuestion(lastSearch.started.question ?? lastSearch.started.standalone_query ?? "");
    setTextResult({
      status: (lastDone.status as SearchResult["status"] | undefined) ?? "found",
      results: lastDone.results ?? [],
      memory_count: 0,
      conversation_count: 0,
      pending_conversations: [],
      failed_conversations: [],
      guidance: "",
      timings_ms: lastDone.timings_ms ?? {},
      degraded: lastDone.degraded ?? false,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDone]);

  // Live memories. A saved voice note appears on the field instantly as a pending node; the moment the
  // worker finishes, /memories/events pushes the real memories, which replace it and get a beam.
  // Uploaded transcripts arrive the same way, whether or not a call is running.
  type LiveToast = { tone: "saving" | "ready" | "already" | "failed"; headline: string; text: string };
  const [liveToast, setLiveToast] = useState<LiveToast | null>(null);
  const [pendingNotes, setPendingNotes] = useState<{ conversationId: string; note: string }[]>([]);
  const [freshRefs, setFreshRefs] = useState<string[]>([]);
  const [freshKey, setFreshKey] = useState(0);
  const [memoryVersion, setMemoryVersion] = useState(0);

  function flash(refs: string[]) {
    setFreshRefs(refs);
    setFreshKey((k) => k + 1);
  }

  useEffect(() => {
    if (!lastSave?.note) return;
    const note = lastSave.note;
    const convId = lastSave.conversation_id;
    if (lastSave.status === "saved" && convId) {
      setPendingNotes((p) => (p.some((n) => n.conversationId === convId) ? p : [...p, { conversationId: convId, note }]));
      flash([`pending:${convId}`]);
      setLiveToast({ tone: "saving", headline: "Saved — pulling out the details…", text: note });
    } else {
      setLiveToast({ tone: "already", headline: "Already remembered", text: note });
    }
  }, [lastSave]);

  useMemoryEvents((e) => {
    setMemoryVersion((v) => v + 1);
    if (e.type === "conversation_processing") return;
    setPendingNotes((p) => p.filter((n) => n.conversationId !== e.conversation_id));
    if (e.type === "conversation_ready") {
      void graph.reload().then(() => flash(e.memories.map((m) => m.id)));
      const [first, ...rest] = e.memories;
      setLiveToast(
        first
          ? {
              tone: "ready",
              headline: rest.length ? `${e.memories.length} new memories` : "New memory",
              text: `${first.statement}${rest.length ? ` (+${rest.length} more)` : ""}`,
            }
          : { tone: "ready", headline: "Saved", text: `${e.title} — searchable now, nothing to extract.` },
      );
    } else {
      void graph.reload();
      setLiveToast({ tone: "failed", headline: "Couldn't process", text: `${e.title}: ${e.error}` });
    }
  });

  // Toasts and beams fade on their own.
  useEffect(() => {
    if (!liveToast) return;
    const t = setTimeout(() => setLiveToast(null), liveToast.tone === "saving" ? 20000 : 7000);
    return () => clearTimeout(t);
  }, [liveToast]);
  useEffect(() => {
    if (!freshRefs.length) return;
    const t = setTimeout(() => setFreshRefs([]), 6000);
    return () => clearTimeout(t);
  }, [freshKey, freshRefs.length]);

  const fieldGraph = useMemo<MemoryGraph | null>(() => {
    if (!graph.data || pendingNotes.length === 0) return graph.data;
    const today = new Date().toISOString().slice(0, 10);
    return {
      ...graph.data,
      nodes: [
        ...graph.data.nodes,
        ...pendingNotes.map((n) => ({
          id: `pending:${n.conversationId}`,
          kind: "fact" as const,
          statement: n.note,
          topic: "",
          decision_state: null,
          owner_is_user: true,
          speaker: null,
          conversation_id: n.conversationId,
          conversation_title: "Voice note (processing…)",
          conversation_date: today,
          chunk_ref: null,
          cluster: null,
          pending: true,
        })),
      ],
    };
  }, [graph.data, pendingNotes]);

  const inCall = sdkState === "connecting" || sdkState === "ringing" || sdkState === "active";
  const orbState: OrbState = callError
    ? "error"
    : sdkState === "connecting" || sdkState === "ringing"
      ? sdkState
      : sdkState === "active"
        ? lastTool && !lastTool.done && !lastTool.failed
          ? lastTool.started.tool === "save_memory"
            ? "saving"
            : "searching"
          : lastTool?.started.tool === "save_memory" && lastTool.done
            ? "saved"
            : lastSearch?.done?.status === "no_reliable_memory"
              ? "no-memory"
              : lastSearch?.done
                ? "found"
                : "listening"
        : speaking
          ? "found"
          : sdkState === "ended"
            ? "ended"
            : "idle";

  // Highlighted memory references (from voice search or text search)
  const voiceLit = lastSearch?.done && lastSearch.done.status !== "no_reliable_memory"
    ? lastSearch.done.results?.map((r) => r.ref) ?? []
    : [];
  const textLit = textResult && textResult.status !== "no_reliable_memory"
    ? textResult.results.map((r) => r.ref)
    : [];
  const litRefs = Array.from(new Set([...voiceLit, ...textLit, ...freshRefs]));

  async function toggleWebCall() {
    // A second click while connecting used to hang the call up immediately; ignore it.
    if (sdkState === "connecting") return;
    if (inCall) {
      stopMicMonitoring();
      await callRef.current?.stop();
      return;
    }

    setCallError(null);
    setMicProblem(null);
    stopSpeaking();
    setSpeaking(false);
    mintMessage.current = null;
    setSdkState("connecting");

    try {
      const { BolnaWebCall } = await import("@bolna/web-call");
      const call = new BolnaWebCall({
        debug: true,
        audio: micConstraints(mic.deviceId),
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
      call.on("media-permission", () => void mic.refresh());
      call.on("call-start", () => {
        callStartedAtRef.current = Date.now();
        const track = audioSender(call)?.track;
        if (!track) {
          setMicProblem("The call connected but no microphone track was sent. Pick a microphone below and try again.");
          return;
        }
        armSilenceCheck();
        void monitorTrack(track);
      });
      call.on("error", (e) => {
        stopMicMonitoring();
        setCallError(sdkErrorMessage(e, mintMessage.current));
        setSdkState("error");
      });
      call.on("call-end", async ({ reason }) => {
        const heard = heardUserRef.current;
        stopMicMonitoring();
        setLevel(0);
        setSdkState("ended");
        const startedAt = callStartedAtRef.current;
        callStartedAtRef.current = null;
        const seconds = startedAt ? (Date.now() - startedAt) / 1000 : 0;
        // Bolna's silence hang-up can't fire for ~20 s, so a very short agent hang-up is an agent-side
        // failure (voice/LLM provider, credits), not the microphone.
        if (reason === "remote-hangup" && startedAt && seconds < 8) {
          setCallError(
            `The voice agent ended the call after ${seconds.toFixed(1)} s, before it spoke. That's on the Bolna side — check the agent's voice and LLM settings and your credits in the Bolna dashboard.`,
          );
        } else if (reason === "remote-hangup" && !heard) {
          setCallError("Recall hung up because it only heard silence from your microphone. Pick another microphone below, or check your system's input settings.");
        } else if (reason === "failed") {
          setCallError("The call dropped (network or media failure). Try again.");
        }
        const id = callIdRef.current;
        if (id) await apiFetch(`/api/v1/calls/${id}/end`, { method: "POST" }).catch(() => undefined);
      });

      await call.start();
    } catch (e) {
      stopMicMonitoring();
      const fallback = e instanceof Error ? e.message : "The call could not start.";
      setCallError((prev) => prev ?? (mintMessage.current ?? fallback) + SETUP_HINT);
      setSdkState("error");
    }
  }

  // Typed questions get a spoken answer too: evidence shows first (fast search), then a short answer
  // written from those results is read aloud. During a call the agent already speaks, so we only show it.
  const [answer, setAnswer] = useState<{ text: string | null } | null>(null);
  const [speakOn, setSpeakOn] = useState(true);
  const askSeq = useRef(0);
  useEffect(() => {
    try {
      setSpeakOn(window.localStorage.getItem("recall.speakAnswers") !== "0");
    } catch {
      // storage blocked: keep speaking on
    }
    return () => stopSpeaking();
  }, []);

  function toggleSpeak() {
    setSpeakOn((on) => {
      try {
        window.localStorage.setItem("recall.speakAnswers", on ? "0" : "1");
      } catch {
        // not remembered
      }
      if (on) {
        stopSpeaking();
        setSpeaking(false);
      }
      return !on;
    });
  }

  function sayAloud(text: string) {
    if (!speakOn || inCall || !canSpeak()) return;
    speak(text, {
      onStart: () => setSpeaking(true),
      onEnd: () => {
        setSpeaking(false);
        setSpeechLevel(0);
      },
      onLevel: setSpeechLevel,
    });
  }

  async function handleAskText(q: string) {
    if (!q.trim()) return;
    const seq = ++askSeq.current;
    stopSpeaking();
    setSpeaking(false);
    setQuestion(q);
    setSearching(true);
    setSearchError(null);
    try {
      const r = await apiFetch<SearchResult>("/api/v1/search", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      if (seq !== askSeq.current) return;
      setAskedQuestion(q);
      setTextResult(r);
      setAnswer({ text: null });
      setPulse((p) => p + 1);
    } catch (e) {
      setSearchError(e instanceof ApiError ? e.message : "Search failed. Is the backend running?");
      return;
    } finally {
      setSearching(false);
    }
    try {
      const a = await apiFetch<{ answer: string }>("/api/v1/search/answer", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      if (seq !== askSeq.current) return;
      setAnswer({ text: a.answer });
      sayAloud(a.answer);
    } catch {
      if (seq === askSeq.current) setAnswer(null);
    }
  }

  async function handleLogout() {
    try {
      await apiFetch("/api/v1/auth/logout", { method: "POST" });
    } finally {
      router.push("/login");
    }
  }

  const openTranscript = (convId: string, memId?: string) => {
    setDrawerTab("conversations");
    setSelectedConversationId(convId);
    setHighlightMemoryId(memId ?? null);
    setDrawerOpen(true);
  };

  const orbButtonLabel = inCall ? "End call" : "Talk to Recall";
  // Only offered when a call reports a microphone problem.
  const showMicPicker = micProblem !== null && mic.devices.length > 0;

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-paper text-ink font-sans">
      {/* Header */}
      <header className="pointer-events-none absolute top-0 inset-x-0 z-30 flex items-center justify-between gap-3 p-4 md:px-6">
        <div className="pointer-events-auto flex items-center gap-3">
          <button
            onClick={() => router.push("/")}
            className="rounded-lg border border-line bg-surface px-3 py-1.5 backdrop-blur-md transition hover:border-white/20"
            title="Go to landing page"
          >
            <Logo size={20} className="text-sm" />
          </button>

          {graph.data && (
            <span className="hidden sm:inline font-mono text-[11px] text-muted">
              {graph.data.nodes.length} memories · {graph.data.clusters.length} topics
            </span>
          )}
        </div>

        <div className="pointer-events-auto flex items-center gap-2">
          {callError && (
            <div role="alert" className="shake max-w-md rounded-lg border border-[#e07a6e]/40 bg-[#e07a6e]/10 px-3 py-1.5 text-xs text-[#f0b2a9] backdrop-blur-md">
              {callError}
            </div>
          )}

          {inCall && (
            <div className="animate-in flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs backdrop-blur-md">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#86c79a] opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[#86c79a]" />
              </span>
              <span className="text-ink-sub">{Date.now() - lastVoiceAtRef.current < 800 ? "Hearing you" : "Listening"}</span>
              <MicMeter level={userMicLevel} />
            </div>
          )}

          <button
            onClick={() => setDrawerOpen(true)}
            aria-label="Open mission control menu"
            className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink backdrop-blur-md transition hover:border-white/20"
          >
            <span className="text-sm leading-none">☰</span>
            <span>Library</span>
          </button>
        </div>
      </header>

      {/* Memory field with the voice orb at its centre */}
      <main className="h-full w-full">
        {graph.loading && !graph.data && (
          <div className="grid h-full w-full place-items-center bg-paper">
            <Spinner label="Loading your memories…" />
          </div>
        )}

        {graph.data && (
          <SpaceCanvas
            graph={fieldGraph ?? graph.data}
            highlightRefs={litRefs}
            pulseKey={pulse + (lastSearch?.done ? 1 : 0) + freshKey * 7919}
            orbState={orbState}
            audioLevel={inCall ? level : speechLevel}
            onOrbClick={() => void toggleWebCall()}
            orbLabel={orbButtonLabel}
            onInspectTranscript={openTranscript}
          />
        )}
      </main>

      {textResult && (
        <EvidencePanel
          question={askedQuestion}
          result={textResult}
          answer={answer?.text}
          answering={answer !== null && answer.text === null}
          speaking={speaking}
          speakOn={speakOn && canSpeak()}
          onToggleSpeak={canSpeak() ? toggleSpeak : undefined}
          onReplay={answer?.text ? () => sayAloud(answer.text!) : undefined}
          onClose={() => {
            stopSpeaking();
            setSpeaking(false);
            setAnswer(null);
            setTextResult(null);
          }}
          onOpen={(e) => openTranscript(e.conversation_id, e.ref)}
          className="pointer-events-auto absolute left-4 top-16 z-30 max-h-[calc(100vh-150px)] w-[calc(100vw-2rem)] sm:left-6 sm:w-96 rise-in"
        />
      )}

      {/* Bottom HUD: live toasts, mic problems, ask bar */}
      <div className="pointer-events-none absolute bottom-6 inset-x-0 z-30 flex flex-col items-center gap-2 px-4">
        {liveToast && (
          <div
            key={liveToast.headline + liveToast.text}
            role="status"
            aria-live="polite"
            className={`rise-in pointer-events-auto flex max-w-xl items-start gap-2.5 rounded-lg border bg-surface-solid px-3.5 py-2.5 text-xs shadow-xl ${
              liveToast.tone === "failed" ? "border-[#e07a6e]/40" : liveToast.tone === "saving" ? "border-accent/40" : "border-[#86c79a]/40"
            }`}
          >
            {liveToast.tone === "saving" ? (
              <span className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-accent/30 border-t-accent" aria-hidden />
            ) : (
              <span
                className={`pop mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full text-[10px] font-bold ${
                  liveToast.tone === "failed" ? "bg-[#e07a6e] text-[#1d0d0a]" : "bg-[#86c79a] text-[#0f1a12]"
                }`}
                aria-hidden
              >
                {liveToast.tone === "failed" ? "!" : "✓"}
              </span>
            )}
            <span className="text-ink-sub">
              <span className="font-medium text-ink">{liveToast.headline}</span>
              {" — "}
              <mark className="hl sweep" style={{ "--delay": "150ms" } as CSSProperties}>{liveToast.text}</mark>
            </span>
          </div>
        )}

        {inCall && micProblem && (
          <div role="alert" className="rise-in pointer-events-auto max-w-xl rounded-lg border border-accent/40 bg-surface-solid px-4 py-2.5 text-xs text-ink-sub shadow-xl">
            <p>{micProblem}</p>
            {micLabel && <p className="mt-1 font-mono text-[11px] text-muted">Current input: {micLabel}</p>}
          </div>
        )}

        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            void handleAskText(question);
          }}
          className="pointer-events-auto flex w-full max-w-xl items-center gap-2 rounded-xl border border-line bg-surface-solid px-3 py-2 shadow-2xl focus-within:border-accent/60"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Type a question, or tap the orb and ask out loud"
            aria-label="Try a question"
            className="flex-1 bg-transparent px-1 text-sm text-ink outline-none placeholder:text-muted"
          />
          <button
            type="submit"
            disabled={searching}
            className="rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-on-accent transition hover:brightness-105 disabled:opacity-60"
          >
            {searching ? (
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 animate-spin rounded-full border-[1.5px] border-on-accent/30 border-t-on-accent" />
                Searching
              </span>
            ) : (
              "Ask"
            )}
          </button>
        </form>

        {searchError && (
          <p role="alert" className="pointer-events-auto text-xs text-[#f0b2a9]">{searchError}</p>
        )}

        {showMicPicker && (
          <div className="pointer-events-auto">
          <label className="flex items-center gap-2 font-mono text-[11px] text-muted">
            Mic
            <select
              value={mic.deviceId}
              onChange={(e) => (inCall ? void switchMic(e.target.value) : mic.setDeviceId(e.target.value))}
              className="max-w-[240px] truncate rounded-md border border-line bg-surface-solid px-2 py-1 text-[11px] text-ink-sub outline-none focus:border-accent/60"
            >
              <option value="">System default</option>
              {mic.devices.map((d, i) => (
                <option key={d.deviceId} value={d.deviceId}>
                  {d.label || `Microphone ${i + 1}`}
                </option>
              ))}
            </select>
          </label>
          </div>
        )}
      </div>

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
        refreshKey={memoryVersion}
        onLogout={handleLogout}
      />
    </div>
  );
}

function MicMeter({ level }: { level: number }) {
  return (
    <span className="flex h-3 items-end gap-0.5" aria-hidden>
      {[0.15, 0.35, 0.6].map((t) => (
        <span
          key={t}
          className="w-1 rounded-sm transition-all duration-100"
          style={{ height: `${level > t * 0.3 ? 4 + t * 12 : 3}px`, background: level > t * 0.3 ? "#86c79a" : "rgba(237,235,230,0.2)" }}
        />
      ))}
    </span>
  );
}
