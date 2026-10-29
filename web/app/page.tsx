"use client";

import Link from "next/link";
import { useState } from "react";

interface SampleEvidence {
  question: string;
  speaker: string;
  title: string;
  quote: string;
  decisionState: "decided" | "proposed" | "superseded";
  date: string;
  kind: string;
}

const SAMPLE_DEMOS: Record<string, SampleEvidence> = {
  db: {
    question: "Which deployment provider did we pick?",
    speaker: "Asha",
    title: "Sprint 4 Architecture Sync",
    quote: "Let's stick with AWS ECS for staging and migrate to GCP for production in Q2.",
    decisionState: "decided",
    date: "Oct 24, 2026",
    kind: "Decision",
  },
  websocket: {
    question: "What did Priya commit to regarding WebSockets?",
    speaker: "Priya",
    title: "Real-time Telemetry Review",
    quote: "I will implement the heartbeat ping-pong handler and keep connection latency under 20ms by Friday.",
    decisionState: "decided",
    date: "Oct 22, 2026",
    kind: "Commitment",
  },
  deadline: {
    question: "When is the investor demo deadline?",
    speaker: "Mayur",
    title: "Weekly Founders Huddle",
    quote: "The final slide deck and live sandbox build must be locked by November 2nd at 5 PM.",
    decisionState: "proposed",
    date: "Oct 25, 2026",
    kind: "Date & Milestone",
  },
};

const FAQ_ITEMS = [
  {
    q: "How does Recall guarantee zero hallucinations?",
    a: "Recall enforces strict evidence provenance gating. Every semantic match is evaluated against calibrated cosine similarity and RRF thresholds. If an answer cannot be verified with a timestamped quote from your uploaded transcripts, Recall directly acknowledges the absence of memory rather than fabricating details.",
  },
  {
    q: "How does the voice engine work?",
    a: "Recall integrates the official Bolna WebRTC SDK with single-use session minting. Audio flows in real time with sub-second turn-taking latency. When you ask a question, the Bolna agent invokes authenticated backend retrieval tools, streams live tool execution events, and reads back the exact evidence.",
  },
  {
    q: "Can I receive calls on my phone when away from the desktop?",
    a: "Yes. In Mission Control, you can enter your E.164 phone number. Recall dispatches an outbound telephony call via Bolna directly to your cell phone so you can query your memories hands-free on the go.",
  },
  {
    q: "What transcript and audio formats can I upload?",
    a: "You can import raw text (.txt), Markdown (.md), WebVTT (.vtt), and SubRip (.srt) meeting transcripts from Zoom, Google Meet, Teams, or Otter. Recall automatically extracts speakers, timestamps, and semantic entities.",
  },
];

export default function LandingPage() {
  const [activeDemoKey, setActiveDemoKey] = useState<string>("db");
  const [activePersona, setActivePersona] = useState<"eng" | "pm" | "founder">("eng");
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [isDemoSpeaking, setIsDemoSpeaking] = useState<boolean>(false);

  const currentDemo = SAMPLE_DEMOS[activeDemoKey];

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#050814] text-ink selection:bg-accent/40 selection:text-white">
      {/* Background Aurora */}
      <div className="aurora pointer-events-none" aria-hidden />

      {/* 1. Global Product Navbar */}
      <header className="sticky top-0 z-50 border-b border-line/80 bg-paper/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2.5 font-display text-lg font-bold tracking-tight text-white group">
              <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#3ee6c4] text-sm font-black text-[#061018] shadow-[0_0_20px_rgba(124,92,255,0.7)] group-hover:scale-105 transition">
                R
              </span>
              <span className="flex items-center gap-1.5">
                Recall
                <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent-2 border border-accent/20">
                  v1.0 · Bolna
                </span>
              </span>
            </Link>

            <nav className="hidden lg:flex items-center gap-6 text-xs font-semibold text-muted">
              <a href="#product-sandbox" className="hover:text-white transition">Product Tour</a>
              <a href="#features" className="hover:text-white transition">Capabilities</a>
              <a href="#comparison" className="hover:text-white transition">Why Recall</a>
              <a href="#workflow" className="hover:text-white transition">Workflow</a>
              <a href="#faq" className="hover:text-white transition">FAQ</a>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-full border border-line px-4 py-2 text-xs font-semibold text-ink hover:border-accent hover:text-white hover:bg-white/5 transition"
            >
              Sign In
            </Link>

            <Link
              href="/space"
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[#7c5cff] to-[#3ee6c4] px-5 py-2 text-xs font-bold text-[#061018] shadow-[0_0_25px_rgba(124,92,255,0.6)] transition hover:scale-[1.03] hover:shadow-[0_0_35px_rgba(62,230,196,0.85)]"
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-white" />
              </span>
              <span>Launch Space</span>
              <span className="text-[10px] font-black">→</span>
            </Link>
          </div>
        </div>
      </header>

      {/* 2. Hero Section */}
      <section className="relative px-6 pt-16 pb-20 md:pt-24 md:pb-28 text-center">
        <div className="mx-auto max-w-4xl">
          {/* Release / Innovation Pill */}
          <div className="inline-flex items-center gap-2.5 rounded-full border border-accent/30 bg-surface/80 px-4 py-1.5 text-xs font-medium text-white shadow-lg backdrop-blur-md hover:border-accent transition cursor-pointer">
            <span className="flex h-2 w-2 rounded-full bg-accent-2 animate-pulse" />
            <span className="font-semibold text-accent-2">Bolna Symphony Buildathon</span>
            <span className="text-white/40">|</span>
            <span className="text-muted text-[11px] sm:text-xs">Zero-Hallucination Voice Memory Companion</span>
            <span className="text-accent text-[11px]">→</span>
          </div>

          {/* Product Headline */}
          <h1 className="mt-8 font-display text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white leading-[1.08]">
            Your conversations shouldn&apos;t vanish. <br />
            <span className="text-gradient">Recall turns speech into spatial memory.</span>
          </h1>

          {/* Subtitle */}
          <p className="mx-auto mt-6 max-w-2xl text-base sm:text-lg text-muted leading-relaxed">
            Stop digging through hours of recordings and scattered notes. Recall structures your meetings into an interconnected celestial memory constellation. Speak naturally — Recall cites the verbatim transcript proof in sub-second time.
          </p>

          {/* Action Row */}
          <div className="mt-10 flex flex-wrap justify-center items-center gap-4">
            <Link
              href="/space"
              className="group inline-flex items-center gap-2.5 rounded-full bg-gradient-to-r from-[#7c5cff] to-[#3ee6c4] px-8 py-3.5 font-bold text-sm text-[#061018] shadow-[0_0_40px_rgba(124,92,255,0.7)] transition hover:scale-105 hover:shadow-[0_0_50px_rgba(62,230,196,0.95)]"
            >
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white" />
              </span>
              <span>Enter Memory Universe</span>
              <span className="text-xs transition-transform group-hover:translate-x-1">→</span>
            </Link>

            <a
              href="#product-sandbox"
              className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 px-6 py-3.5 text-sm font-semibold text-ink backdrop-blur hover:bg-white/10 hover:border-accent transition"
            >
              <span>Explore Interactive Demo</span>
              <span className="text-xs text-accent">↓</span>
            </a>
          </div>

          {/* Trust & Proof Badges */}
          <div className="mt-12 flex flex-wrap justify-center items-center gap-6 text-xs text-muted">
            <div className="flex items-center gap-2 rounded-lg bg-surface/40 px-3 py-1.5 border border-line/60">
              <span className="text-emerald-400 font-bold">100%</span>
              <span>Grounded Provenance</span>
            </div>
            <div className="flex items-center gap-2 rounded-lg bg-surface/40 px-3 py-1.5 border border-line/60">
              <span className="text-accent-2 font-bold">&lt; 25ms</span>
              <span>RRF Vector Search</span>
            </div>
            <div className="flex items-center gap-2 rounded-lg bg-surface/40 px-3 py-1.5 border border-line/60">
              <span className="text-accent font-bold">WebRTC</span>
              <span>Powered by Bolna</span>
            </div>
            <div className="flex items-center gap-2 rounded-lg bg-surface/40 px-3 py-1.5 border border-line/60">
              <span className="text-pink-400 font-bold">0%</span>
              <span>Hallucinations</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Interactive Live Product Sandbox / App Window */}
      <section id="product-sandbox" className="relative px-4 sm:px-6 py-12">
        <div className="mx-auto max-w-6xl">
          <div className="text-center mb-8">
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-accent-2">
              Live Product Experience
            </span>
            <h2 className="mt-2 font-display text-2xl sm:text-4xl font-bold text-white">
              Test the Memory Engine Right Here
            </h2>
            <p className="mt-2 text-xs sm:text-sm text-muted max-w-xl mx-auto">
              Select any query below to watch Recall&apos;s voice orb pulse, beam light into the memory field, and retrieve the verbatim quote.
            </p>
          </div>

          {/* Interactive Query Selector Pills */}
          <div className="flex flex-wrap justify-center gap-2 mb-6">
            <button
              onClick={() => {
                setActiveDemoKey("db");
                setIsDemoSpeaking(true);
                setTimeout(() => setIsDemoSpeaking(false), 2400);
              }}
              className={`rounded-full px-4 py-2 text-xs font-semibold transition border ${
                activeDemoKey === "db"
                  ? "bg-accent/20 border-accent text-white shadow-[0_0_15px_rgba(139,123,255,0.4)]"
                  : "bg-surface/60 border-line text-muted hover:text-white hover:border-accent/40"
              }`}
            >
              💬 &ldquo;Which deployment provider did we pick?&rdquo;
            </button>

            <button
              onClick={() => {
                setActiveDemoKey("websocket");
                setIsDemoSpeaking(true);
                setTimeout(() => setIsDemoSpeaking(false), 2400);
              }}
              className={`rounded-full px-4 py-2 text-xs font-semibold transition border ${
                activeDemoKey === "websocket"
                  ? "bg-accent/20 border-accent text-white shadow-[0_0_15px_rgba(139,123,255,0.4)]"
                  : "bg-surface/60 border-line text-muted hover:text-white hover:border-accent/40"
              }`}
            >
              💬 &ldquo;What did Priya commit to regarding WebSockets?&rdquo;
            </button>

            <button
              onClick={() => {
                setActiveDemoKey("deadline");
                setIsDemoSpeaking(true);
                setTimeout(() => setIsDemoSpeaking(false), 2400);
              }}
              className={`rounded-full px-4 py-2 text-xs font-semibold transition border ${
                activeDemoKey === "deadline"
                  ? "bg-accent/20 border-accent text-white shadow-[0_0_15px_rgba(139,123,255,0.4)]"
                  : "bg-surface/60 border-line text-muted hover:text-white hover:border-accent/40"
              }`}
            >
              💬 &ldquo;When is the investor demo deadline?&rdquo;
            </button>
          </div>

          {/* Product Window Shell */}
          <div className="rounded-3xl border border-line/90 bg-[#060a1a] shadow-2xl overflow-hidden backdrop-blur-2xl">
            {/* Window Chrome / Title Bar */}
            <div className="flex items-center justify-between border-b border-line/80 bg-paper/80 px-5 py-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-rose-500/80" />
                <span className="h-3 w-3 rounded-full bg-amber-500/80" />
                <span className="h-3 w-3 rounded-full bg-emerald-500/80" />
                <span className="ml-3 font-mono text-[11px] text-muted">recall://space/universe-v1</span>
              </div>

              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-500/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
                  Bolna Engine Online
                </span>
                <span className="text-muted text-[11px]">48 Memories Indexed</span>
              </div>
            </div>

            {/* Simulated Main Space Viewport */}
            <div className="relative min-h-[440px] sm:min-h-[500px] w-full bg-[#040612] p-6 flex flex-col md:flex-row items-center justify-between gap-6 overflow-hidden">
              {/* Cosmic Stars Canvas Simulation */}
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-accent/15 via-[#050814]/90 to-[#040612]" />

              {/* Orbital guide rings */}
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-72 w-72 rounded-full border border-accent/15 pointer-events-none" />
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[440px] w-[440px] rounded-full border border-accent/10 border-dashed pointer-events-none" />

              {/* Left HUD: The Simulated Live Evidence Card */}
              <div className="relative z-20 w-full md:w-80 rounded-2xl border border-line bg-surface-solid/95 p-4 backdrop-blur-xl shadow-2xl animate-in fade-in slide-in-from-left-4">
                <div className="flex items-center justify-between pb-2 border-b border-line text-xs">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-accent-2 animate-pulse" />
                    <span className="font-semibold text-white uppercase tracking-wider text-[11px]">
                      Retrieved Evidence
                    </span>
                  </div>
                  <span className="rounded bg-accent/20 px-2 py-0.5 text-[10px] font-bold text-accent">
                    {currentDemo.kind}
                  </span>
                </div>

                <div className="mt-3 space-y-2.5">
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-muted">Source Transcript</span>
                    <h4 className="text-xs font-bold text-white mt-0.5">{currentDemo.title}</h4>
                    <span className="text-[10px] text-muted">{currentDemo.date} · Said by {currentDemo.speaker}</span>
                  </div>

                  <div className="rounded-xl border border-accent/30 bg-accent/10 p-3">
                    <span className="text-[10px] uppercase font-bold text-accent-2">Verbatim Proof</span>
                    <blockquote className="mt-1 text-xs text-ink italic leading-relaxed">
                      &ldquo;{currentDemo.quote}&rdquo;
                    </blockquote>
                  </div>

                  <div className="flex items-center justify-between pt-1 text-[11px]">
                    <span className="text-muted">Provenance status:</span>
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      <span>✓</span> Verified Ground Truth
                    </span>
                  </div>
                </div>
              </div>

              {/* Center: The Interactive Voice Orb */}
              <div className="relative z-20 flex flex-col items-center justify-center py-4">
                <button
                  onClick={() => {
                    setIsDemoSpeaking(true);
                    setTimeout(() => setIsDemoSpeaking(false), 2400);
                  }}
                  className="group relative grid h-36 w-36 sm:h-44 sm:w-44 place-items-center rounded-full outline-none transition-transform hover:scale-105"
                  title="Click to simulate voice interaction"
                >
                  <div
                    className={`absolute inset-0 rounded-full bg-gradient-to-tr from-[#7c5cff] via-[#8b7bff] to-[#3ee6c4] blur-2xl opacity-75 group-hover:opacity-100 transition duration-700 ${
                      isDemoSpeaking ? "animate-ping opacity-90 scale-110" : "animate-pulse"
                    }`}
                  />
                  <div className="relative grid h-32 w-32 sm:h-36 sm:w-36 place-items-center rounded-full bg-gradient-to-br from-[#12193b] to-[#080d22] border-2 border-accent-2/60 shadow-[0_0_40px_rgba(62,230,196,0.6)]">
                    <span className="text-xs font-bold uppercase tracking-wider text-white drop-shadow">
                      {isDemoSpeaking ? "Retrieving…" : "Talk to Recall"}
                    </span>
                    <span className="text-[10px] text-accent-2 mt-0.5 font-medium">
                      {isDemoSpeaking ? "Audio Reactive" : "Click Orb"}
                    </span>
                  </div>
                </button>
                <span className="mt-3 text-[11px] font-semibold uppercase tracking-widest text-muted">
                  Powered by Bolna WebRTC
                </span>
              </div>

              {/* Right HUD: Constellation Cluster Breakdown */}
              <div className="relative z-20 w-full md:w-64 rounded-2xl border border-line bg-surface/80 p-4 backdrop-blur-xl">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted">
                  Active Constellations
                </span>
                <ul className="mt-2.5 space-y-2 text-xs">
                  <li className="flex items-center justify-between p-2 rounded-lg bg-paper/70 border border-line/60">
                    <span className="text-white font-medium">Infrastructure & Cloud</span>
                    <span className="text-accent-2 font-bold text-[11px]">18 nodes</span>
                  </li>
                  <li className="flex items-center justify-between p-2 rounded-lg bg-paper/70 border border-line/60">
                    <span className="text-white font-medium">Product Roadmap</span>
                    <span className="text-accent font-bold text-[11px]">14 nodes</span>
                  </li>
                  <li className="flex items-center justify-between p-2 rounded-lg bg-paper/70 border border-line/60">
                    <span className="text-white font-medium">Action Items & Owners</span>
                    <span className="text-pink-400 font-bold text-[11px]">16 nodes</span>
                  </li>
                </ul>

                <Link
                  href="/space"
                  className="mt-3 block w-full rounded-lg bg-accent/20 hover:bg-accent/30 py-2 text-center text-xs font-bold text-accent transition"
                >
                  Explore Full Canvas →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Problem vs Solution: The Product Contrast */}
      <section id="comparison" className="relative px-6 py-20 border-t border-line/60 bg-paper/50">
        <div className="mx-auto max-w-5xl">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-accent">Product Philosophy</span>
            <h2 className="mt-2 font-display text-3xl sm:text-4xl font-bold text-white">
              Why Traditional Note-Taking Fails
            </h2>
            <p className="mt-3 text-sm text-muted">
              Most productivity tools expect you to manually organize, tag, and file meeting notes. Recall treats human memory like a living conversation.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* The Old Way */}
            <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 backdrop-blur-md">
              <div className="flex items-center gap-2 text-rose-400 text-sm font-bold uppercase tracking-wider">
                <span>✕</span>
                <span>The Traditional Way</span>
              </div>
              <ul className="mt-5 space-y-4 text-xs sm:text-sm text-muted">
                <li className="flex items-start gap-3">
                  <span className="text-rose-400 font-bold mt-0.5">•</span>
                  <span>45-minute recording files sitting forgotten in Zoom cloud storage.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-rose-400 font-bold mt-0.5">•</span>
                  <span>Manual note documents that nobody updates or reads after the meeting ends.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-rose-400 font-bold mt-0.5">•</span>
                  <span>Generic LLM summaries that hallucinate decisions or miss crucial nuances.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-rose-400 font-bold mt-0.5">•</span>
                  <span>Decisions superseded weeks ago are lost in Slack threads with zero paper trail.</span>
                </li>
              </ul>
            </div>

            {/* The Recall Way */}
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6 backdrop-blur-md">
              <div className="flex items-center gap-2 text-emerald-400 text-sm font-bold uppercase tracking-wider">
                <span>✓</span>
                <span>The Recall Engine</span>
              </div>
              <ul className="mt-5 space-y-4 text-xs sm:text-sm text-ink">
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                  <span><strong>Zero Manual Tagging</strong>: Decisions, commitments, and facts extracted automatically.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                  <span><strong>Living Superseded Links</strong>: When an earlier agreement changes, Recall links them explicitly.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                  <span><strong>Verifiable Quotation</strong>: Every voice reply points directly to the exact speaker and transcript line.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                  <span><strong>Voice-First Simplicity</strong>: Tap the orb or dial your phone to retrieve answers in seconds.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Product Bento Grid Features */}
      <section id="features" className="relative px-6 py-24 border-t border-line/60">
        <div className="mx-auto max-w-6xl">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-accent-2">
              Capabilities
            </span>
            <h2 className="mt-2 font-display text-3xl sm:text-5xl font-bold text-white">
              Engineered for Instant, Truthful Recall
            </h2>
            <p className="mt-3 text-sm text-muted">
              Built from the ground up for the Bolna Symphony Buildathon using modern WebRTC, asynchronous vector pipelines, and strict provenance gating.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Bento Card 1: Constellation Graph (Span 2) */}
            <div className="md:col-span-2 rounded-3xl border border-line bg-surface/70 p-8 backdrop-blur-xl hover:border-accent/60 transition group flex flex-col justify-between">
              <div>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent/20 text-lg text-accent">
                  🌌
                </span>
                <h3 className="mt-4 font-display text-xl font-bold text-white">
                  Spatial Memory Constellation
                </h3>
                <p className="mt-2 text-xs sm:text-sm text-muted max-w-lg leading-relaxed">
                  Every extracted memory lives in a golden-angle spiral around its topic cluster. Edges highlight semantic similarities, while directional energy lines trace how decisions evolve and supersede older ideas.
                </p>
              </div>

              <div className="mt-6 rounded-2xl border border-line bg-black/40 p-4 font-mono text-xs text-accent-2">
                <code>{`graph.traverse({ links: ["supersedes", "conflicts_with"], mode: "spatial" })`}</code>
              </div>
            </div>

            {/* Bento Card 2: Voice Engine */}
            <div className="rounded-3xl border border-line bg-surface/70 p-8 backdrop-blur-xl hover:border-accent/60 transition flex flex-col justify-between">
              <div>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent-2/20 text-lg text-accent-2">
                  🎙️
                </span>
                <h3 className="mt-4 font-display text-xl font-bold text-white">
                  Bolna Voice Pipeline
                </h3>
                <p className="mt-2 text-xs sm:text-sm text-muted leading-relaxed">
                  Sub-second turn-taking via WebRTC. Real-time audio amplitude analysis drives the pulsating orb with dynamic color-coded state transitions.
                </p>
              </div>

              <div className="mt-6 flex items-center justify-between text-xs text-muted border-t border-line/60 pt-4">
                <span>Latency</span>
                <span className="text-emerald-400 font-bold">&lt; 1000ms end-to-end</span>
              </div>
            </div>

            {/* Bento Card 3: Strict Ground Truth */}
            <div className="rounded-3xl border border-line bg-surface/70 p-8 backdrop-blur-xl hover:border-accent/60 transition flex flex-col justify-between">
              <div>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-400/20 text-lg text-emerald-400">
                  🛡️
                </span>
                <h3 className="mt-4 font-display text-xl font-bold text-white">
                  Proven Ground Truth
                </h3>
                <p className="mt-2 text-xs sm:text-sm text-muted leading-relaxed">
                  Calibrated similarity thresholds prevent conversational guessing. If a detail wasn&apos;t recorded, Recall explicitly says so.
                </p>
              </div>

              <div className="mt-6 flex items-center justify-between text-xs text-muted border-t border-line/60 pt-4">
                <span>Hallucinations</span>
                <span className="text-emerald-400 font-bold">0% Guaranteed</span>
              </div>
            </div>

            {/* Bento Card 4: Mission Control Slide-out (Span 2) */}
            <div className="md:col-span-2 rounded-3xl border border-line bg-surface/70 p-8 backdrop-blur-xl hover:border-accent/60 transition flex flex-col justify-between">
              <div>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-purple-400/20 text-lg text-purple-400">
                  🛸
                </span>
                <h3 className="mt-4 font-display text-xl font-bold text-white">
                  Slide-Out Mission Control Drawer
                </h3>
                <p className="mt-2 text-xs sm:text-sm text-muted max-w-lg leading-relaxed">
                  A side-panel popup houses your complete conversation library, full interactive transcripts with evidence quote scrolling, and outbound phone fallback controls.
                </p>
              </div>

              <div className="mt-6 flex items-center gap-4 text-xs text-muted border-t border-line/60 pt-4">
                <span>✓ Interactive transcripts</span>
                <span>✓ Phone PSTN dialer</span>
                <span>✓ Memory item manager</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Persona Use-Case Matrix */}
      <section className="relative px-6 py-20 border-t border-line/60 bg-paper/40">
        <div className="mx-auto max-w-5xl">
          <div className="text-center max-w-xl mx-auto mb-10">
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-accent">Use Cases</span>
            <h2 className="mt-2 font-display text-3xl font-bold text-white">
              Who Uses Recall Daily
            </h2>
          </div>

          {/* Persona Switcher Tabs */}
          <div className="flex justify-center gap-3 mb-8">
            <button
              onClick={() => setActivePersona("eng")}
              className={`rounded-full px-5 py-2 text-xs font-bold transition border ${
                activePersona === "eng"
                  ? "bg-accent border-accent text-white shadow-lg"
                  : "bg-surface border-line text-muted hover:text-white"
              }`}
            >
              Engineering Leads
            </button>
            <button
              onClick={() => setActivePersona("pm")}
              className={`rounded-full px-5 py-2 text-xs font-bold transition border ${
                activePersona === "pm"
                  ? "bg-accent border-accent text-white shadow-lg"
                  : "bg-surface border-line text-muted hover:text-white"
              }`}
            >
              Product Managers
            </button>
            <button
              onClick={() => setActivePersona("founder")}
              className={`rounded-full px-5 py-2 text-xs font-bold transition border ${
                activePersona === "founder"
                  ? "bg-accent border-accent text-white shadow-lg"
                  : "bg-surface border-line text-muted hover:text-white"
              }`}
            >
              Founders & Executives
            </button>
          </div>

          {/* Persona Card Content */}
          <div className="rounded-3xl border border-line bg-surface/80 p-8 backdrop-blur-xl">
            {activePersona === "eng" && (
              <div className="space-y-4">
                <h3 className="font-display text-xl font-bold text-white">
                  &ldquo;Did we agree to deprecate the REST endpoint before v2 launch?&rdquo;
                </h3>
                <p className="text-sm text-muted leading-relaxed">
                  Engineering teams make hundreds of micro-architectural decisions across daily standups and RFC reviews. Recall creates an instant, search-free memory record so new teammates or busy tech leads can verify API contracts and schema choices without searching Jira tickets.
                </p>
                <div className="pt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-md bg-accent/15 px-2.5 py-1 text-accent font-semibold">Decisions tracking</span>
                  <span className="rounded-md bg-accent-2/15 px-2.5 py-1 text-accent-2 font-semibold">Tech debt commitments</span>
                  <span className="rounded-md bg-white/10 px-2.5 py-1 text-white font-semibold">Architecture changelog</span>
                </div>
              </div>
            )}

            {activePersona === "pm" && (
              <div className="space-y-4">
                <h3 className="font-display text-xl font-bold text-white">
                  &ldquo;What exact pain point did Sarah from Stripe report during onboarding?&rdquo;
                </h3>
                <p className="text-sm text-muted leading-relaxed">
                  Instead of scrubbing through twenty 30-minute customer interview recordings, product managers can ask Recall directly. Recall cites the user&apos;s exact feedback quote and links it to feature requests.
                </p>
                <div className="pt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-md bg-accent/15 px-2.5 py-1 text-accent font-semibold">Customer verbatim quotes</span>
                  <span className="rounded-md bg-accent-2/15 px-2.5 py-1 text-accent-2 font-semibold">Feature priorities</span>
                  <span className="rounded-md bg-white/10 px-2.5 py-1 text-white font-semibold">Roadmap sync</span>
                </div>
              </div>
            )}

            {activePersona === "founder" && (
              <div className="space-y-4">
                <h3 className="font-display text-xl font-bold text-white">
                  &ldquo;What valuation cap did we discuss with the lead investor on Tuesday?&rdquo;
                </h3>
                <p className="text-sm text-muted leading-relaxed">
                  Founders manage dozens of high-stakes conversations across fundraising, legal, hiring, and board alignments. Recall ensures critical numbers, promised deliverables, and contractual understandings are never misremembered.
                </p>
                <div className="pt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-md bg-accent/15 px-2.5 py-1 text-accent font-semibold">Investor commitments</span>
                  <span className="rounded-md bg-accent-2/15 px-2.5 py-1 text-accent-2 font-semibold">Board resolutions</span>
                  <span className="rounded-md bg-white/10 px-2.5 py-1 text-white font-semibold">Action items owner</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 7. Workflow Walkthrough */}
      <section id="workflow" className="relative px-6 py-20 border-t border-line/60">
        <div className="mx-auto max-w-5xl">
          <div className="text-center max-w-xl mx-auto mb-14">
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-accent-2">Process</span>
            <h2 className="mt-2 font-display text-3xl font-bold text-white">
              Three Steps from Raw Audio to Infinite Recall
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <div className="rounded-2xl border border-line bg-surface/50 p-6 relative">
              <span className="text-3xl font-display font-extrabold text-accent/30">01</span>
              <h3 className="mt-3 text-base font-bold text-white">Import Transcripts</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Upload or paste meeting transcripts (.txt, .md, .vtt). Recall parses speaker turns, timestamps, and segments without manual formatting.
              </p>
            </div>

            <div className="rounded-2xl border border-line bg-surface/50 p-6 relative">
              <span className="text-3xl font-display font-extrabold text-accent-2/30">02</span>
              <h3 className="mt-3 text-base font-bold text-white">Graph Synthesis</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Background pipelines extract decisions, promises, and facts, computing vector embeddings and clustering them into starry orbital systems.
              </p>
            </div>

            <div className="rounded-2xl border border-line bg-surface/50 p-6 relative">
              <span className="text-3xl font-display font-extrabold text-purple-400/30">03</span>
              <h3 className="mt-3 text-base font-bold text-white">Ambient Voice Recall</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Speak directly to the Voice Orb or query in space. Recall illuminates the matching stars and cites verbatim proof instantly.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 8. Frequently Asked Questions (FAQ) Accordion */}
      <section id="faq" className="relative px-6 py-20 border-t border-line/60 bg-paper/40">
        <div className="mx-auto max-w-4xl">
          <div className="text-center mb-12">
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-accent">Knowledge Base</span>
            <h2 className="mt-2 font-display text-3xl font-bold text-white">
              Frequently Asked Questions
            </h2>
          </div>

          <div className="space-y-3">
            {FAQ_ITEMS.map((item, idx) => {
              const isOpen = openFaq === idx;
              return (
                <div
                  key={idx}
                  className="rounded-2xl border border-line bg-surface/70 overflow-hidden transition"
                >
                  <button
                    onClick={() => setOpenFaq(isOpen ? null : idx)}
                    className="w-full flex items-center justify-between p-5 text-left text-sm font-semibold text-white hover:text-accent transition"
                  >
                    <span>{item.q}</span>
                    <span className="ml-4 text-xs text-muted">{isOpen ? "▲" : "▼"}</span>
                  </button>
                  {isOpen && (
                    <div className="px-5 pb-5 text-xs sm:text-sm text-muted leading-relaxed border-t border-line/40 pt-3 animate-in fade-in">
                      {item.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* 9. Final High-Conversion Product CTA */}
      <section className="relative px-6 py-24 border-t border-line/60 bg-gradient-to-b from-paper to-[#030612]">
        <div className="mx-auto max-w-4xl rounded-3xl border border-line/90 bg-surface/80 p-10 sm:p-16 text-center backdrop-blur-2xl shadow-2xl relative overflow-hidden">
          <div className="absolute -top-32 -left-32 h-64 w-64 rounded-full bg-accent/20 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-32 -right-32 h-64 w-64 rounded-full bg-accent-2/20 blur-3xl pointer-events-none" />

          <span className="text-xs font-bold uppercase tracking-[0.25em] text-accent-2">
            Get Started with Recall
          </span>
          <h2 className="mt-3 font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Step into your conversation universe.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm sm:text-base text-muted">
            Never lose another decision, action item, or crucial agreement. Experience voice-first memory with ground-truth accuracy.
          </p>

          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link
              href="/space"
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[#7c5cff] to-[#3ee6c4] px-8 py-3.5 font-bold text-sm text-[#061018] shadow-[0_0_35px_rgba(124,92,255,0.7)] transition hover:scale-105"
            >
              <span>Launch Recall Space</span>
              <span>→</span>
            </Link>

            <Link
              href="/login"
              className="rounded-full border border-line bg-white/5 px-7 py-3.5 text-sm font-semibold text-white hover:bg-white/10 hover:border-accent transition"
            >
              Sign In to Account
            </Link>
          </div>
        </div>
      </section>

      {/* 10. Product Footer */}
      <footer className="border-t border-line px-6 py-10 text-xs text-muted">
        <div className="mx-auto max-w-7xl flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <span className="grid h-6 w-6 place-items-center rounded-lg bg-gradient-to-br from-[#7c5cff] to-[#3ee6c4] text-[10px] font-black text-[#061018]">
              R
            </span>
            <span className="font-semibold text-white">Recall Engine</span>
            <span>· Built for the Bolna Symphony Buildathon</span>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-muted">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>All Systems Operational</span>
            <span className="mx-2 text-line">|</span>
            <span>WebRTC Voice Gateway Active</span>
          </div>

          <div className="flex items-center gap-6">
            <Link href="/space" className="hover:text-white transition">Live Space Canvas</Link>
            <Link href="/login" className="hover:text-white transition">Sign In</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
