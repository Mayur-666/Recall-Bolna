"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#050814] text-ink selection:bg-accent/40 selection:text-white">
      {/* Cosmic background effects */}
      <div className="aurora pointer-events-none" aria-hidden />

      {/* Floating navigation */}
      <header className="sticky top-0 z-50 border-b border-line bg-paper/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2.5 font-display text-lg font-bold tracking-tight text-white">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#3ee6c4] text-sm font-black text-[#061018] shadow-[0_0_20px_rgba(124,92,255,0.6)]">
              R
            </span>
            Recall
          </Link>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-muted">
            <a href="#constellation" className="hover:text-white transition">Constellation</a>
            <a href="#voice" className="hover:text-white transition">Voice AI</a>
            <a href="#proof" className="hover:text-white transition">Proof Engine</a>
            <a href="#how-it-works" className="hover:text-white transition">Workflow</a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-full border border-line px-4 py-2 text-xs font-semibold text-ink hover:border-accent hover:text-white transition"
            >
              Sign In
            </Link>
            <Link
              href="/space"
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[#7c5cff] to-[#3ee6c4] px-5 py-2 text-xs font-bold text-[#061018] shadow-[0_0_25px_rgba(124,92,255,0.6)] transition hover:scale-[1.03] hover:shadow-[0_0_35px_rgba(62,230,196,0.8)]"
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-white" />
              </span>
              Enter Space
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative px-6 pt-20 pb-28 md:pt-28 md:pb-36 text-center">
        <div className="mx-auto max-w-4xl">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-accent-2 backdrop-blur-md">
            <span>✨</span>
            <span>VOICE-FIRST MEMORY CONSTELLATION · POWERED BY BOLNA</span>
          </div>

          {/* Heading */}
          <h1 className="mt-8 font-display text-4xl font-extrabold tracking-tight md:text-7xl leading-[1.1]">
            Ask your past. <br />
            <span className="text-gradient">It answers with proof.</span>
          </h1>

          {/* Subtitle */}
          <p className="mx-auto mt-6 max-w-2xl text-base md:text-lg text-muted leading-relaxed">
            Every decision, promise, and commitment from your conversations, mapped into an interconnected spatial universe. 
            Talk to Recall naturally — watch it illuminate the exact moment in the stars with zero hallucinations.
          </p>

          {/* Action buttons */}
          <div className="mt-10 flex flex-wrap justify-center items-center gap-4">
            <Link
              href="/space"
              className="group inline-flex items-center gap-2.5 rounded-full bg-gradient-to-r from-[#7c5cff] to-[#3ee6c4] px-8 py-3.5 font-bold text-sm text-[#061018] shadow-[0_0_40px_rgba(124,92,255,0.7)] transition hover:scale-105 hover:shadow-[0_0_50px_rgba(62,230,196,0.9)]"
            >
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white" />
              </span>
              Enter Memory Space
            </Link>

            <Link
              href="/login"
              className="rounded-full border border-line bg-surface/60 px-7 py-3.5 text-sm font-semibold text-ink backdrop-blur hover:bg-white/10 hover:border-accent transition"
            >
              Sign In to Library
            </Link>
          </div>

          {/* Metric highlights */}
          <div className="mt-12 flex flex-wrap justify-center gap-8 text-xs font-medium text-muted">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>0% Hallucinations (Strict Ground Truth)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
              <span>Sub-second Voice Latency</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-purple-400" />
              <span>Interactive Celestial Map</span>
            </div>
          </div>
        </div>

        {/* Hero Interactive Spatial Teaser Visual */}
        <div className="mx-auto mt-16 max-w-5xl rounded-3xl border border-line bg-surface/40 p-4 md:p-8 backdrop-blur-2xl shadow-2xl relative overflow-hidden">
          <div className="relative h-[380px] md:h-[480px] w-full rounded-2xl bg-[#040714] overflow-hidden flex items-center justify-center border border-white/5">
            {/* Stars background simulation */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-accent/15 via-[#050814]/80 to-[#040714]" />

            {/* Orbit concentric rings */}
            <div className="absolute h-48 w-48 rounded-full border border-accent/20 animate-spin" style={{ animationDuration: "50s" }} />
            <div className="absolute h-80 w-80 rounded-full border border-accent/10 border-dashed animate-spin" style={{ animationDuration: "80s" }} />
            <div className="absolute h-[420px] w-[420px] rounded-full border border-accent/5" />

            {/* Glowing memory nodes in space */}
            <div className="absolute top-[22%] left-[24%] flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-[#3ee6c4] shadow-[0_0_14px_#3ee6c4]" />
              <span className="text-[11px] font-semibold text-white/90 bg-black/60 px-2 py-0.5 rounded-full border border-line">
                Decision: Picked PostgreSQL
              </span>
            </div>

            <div className="absolute top-[30%] right-[22%] flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-[#b69cff] shadow-[0_0_14px_#b69cff]" />
              <span className="text-[11px] font-semibold text-white/90 bg-black/60 px-2 py-0.5 rounded-full border border-line">
                Promise: Arjun follows up Friday
              </span>
            </div>

            <div className="absolute bottom-[24%] left-[28%] flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-[#5cd6ff] shadow-[0_0_12px_#5cd6ff]" />
              <span className="text-[11px] font-semibold text-white/90 bg-black/60 px-2 py-0.5 rounded-full border border-line">
                Fact: WebSocket latency &lt; 20ms
              </span>
            </div>

            <div className="absolute bottom-[28%] right-[26%] flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-[#ff8fd1] shadow-[0_0_14px_#ff8fd1]" />
              <span className="text-[11px] font-semibold text-white/90 bg-black/60 px-2 py-0.5 rounded-full border border-line">
                Person: Priya (Lead Architect)
              </span>
            </div>

            {/* Simulated beam connecting center to decision */}
            <svg className="absolute inset-0 h-full w-full pointer-events-none">
              <line x1="50%" y1="50%" x2="30%" y2="24%" stroke="rgba(62, 230, 196, 0.6)" strokeWidth="2" strokeDasharray="4 4" />
              <line x1="50%" y1="50%" x2="72%" y2="32%" stroke="rgba(182, 156, 255, 0.4)" strokeWidth="1.5" />
            </svg>

            {/* Central Glowing Orb */}
            <Link
              href="/space"
              className="group relative z-10 grid h-32 w-32 md:h-40 md:w-40 place-items-center rounded-full transition-transform hover:scale-105"
            >
              <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-[#7c5cff] via-[#8b7bff] to-[#3ee6c4] blur-xl opacity-80 group-hover:opacity-100 transition duration-500 animate-pulse" />
              <div className="relative grid h-28 w-28 md:h-32 md:w-32 place-items-center rounded-full bg-gradient-to-br from-[#121b38] to-[#090e22] border-2 border-accent-2/60 shadow-[0_0_30px_rgba(62,230,196,0.6)]">
                <span className="text-xs font-bold uppercase tracking-wider text-white drop-shadow">
                  Launch Space
                </span>
                <span className="text-[10px] text-accent-2 mt-0.5">Click to Speak</span>
              </div>
            </Link>

            {/* Floating prompt overlay */}
            <div className="absolute bottom-4 inset-x-4 md:bottom-6 md:inset-x-auto mx-auto flex items-center gap-3 rounded-full border border-line bg-surface/90 px-5 py-2.5 text-xs text-muted backdrop-blur-md shadow-lg">
              <span className="h-2 w-2 rounded-full bg-accent animate-ping" />
              <span className="text-white font-medium">&ldquo;What did Priya decide regarding WebSockets?&rdquo;</span>
              <span className="text-accent-2 font-semibold">→ Citing Transcript Segment #4</span>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pillars */}
      <section id="constellation" className="relative px-6 py-24 border-t border-line/60 bg-paper/40">
        <div className="mx-auto max-w-6xl">
          <div className="text-center max-w-2xl mx-auto">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-accent-2">Core Architecture</p>
            <h2 className="mt-3 font-display text-3xl md:text-5xl font-bold tracking-tight text-white">
              A Memory Canvas, Not a Boring Table.
            </h2>
            <p className="mt-3 text-muted text-sm md:text-base">
              Traditional dashboards flatten your conversations into dry rows and columns. Recall maps them into living, clustered constellations.
            </p>
          </div>

          <div className="mt-16 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-line bg-surface/60 p-6 backdrop-blur-lg hover:border-accent/60 transition">
              <div className="grid h-12 w-12 place-items-center rounded-xl bg-accent/20 text-xl text-accent">
                🌌
              </div>
              <h3 className="mt-4 font-display text-lg font-semibold text-white">Spatial Constellations</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Decisions, commitments, and facts plotted as celestial star clusters. Pan, zoom, and explore connections like a universe.
              </p>
            </div>

            <div id="voice" className="rounded-2xl border border-line bg-surface/60 p-6 backdrop-blur-lg hover:border-accent/60 transition">
              <div className="grid h-12 w-12 place-items-center rounded-xl bg-accent-2/20 text-xl text-accent-2">
                🎙️
              </div>
              <h3 className="mt-4 font-display text-lg font-semibold text-white">Bolna Voice Engine</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Click the central orb and ask questions with natural voice. The orb pulses to real audio volume with sub-second retrieval.
              </p>
            </div>

            <div id="proof" className="rounded-2xl border border-line bg-surface/60 p-6 backdrop-blur-lg hover:border-accent/60 transition">
              <div className="grid h-12 w-12 place-items-center rounded-xl bg-emerald-400/20 text-xl text-emerald-400">
                🛡️
              </div>
              <h3 className="mt-4 font-display text-lg font-semibold text-white">Verifiable Ground Truth</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Zero hallucinations. Every response provides clickable citations to the exact speaker and transcript line. If not found, it says so.
              </p>
            </div>

            <div className="rounded-2xl border border-line bg-surface/60 p-6 backdrop-blur-lg hover:border-accent/60 transition">
              <div className="grid h-12 w-12 place-items-center rounded-xl bg-purple-400/20 text-xl text-purple-400">
                🛸
              </div>
              <h3 className="mt-4 font-display text-lg font-semibold text-white">Slide-out Mission Control</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Conversations, transcripts, and voice logs live under a neat hamburger menu that slides out as a side box without leaving space.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How it Works Walkthrough */}
      <section id="how-it-works" className="relative px-6 py-24 border-t border-line/60">
        <div className="mx-auto max-w-5xl">
          <div className="text-center max-w-xl mx-auto">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-accent">Workflow</p>
            <h2 className="mt-3 font-display text-3xl md:text-4xl font-bold tracking-tight text-white">
              From Raw Transcripts to Cosmic Memory
            </h2>
          </div>

          <div className="mt-14 grid gap-8 md:grid-cols-3">
            <div className="relative rounded-2xl border border-line bg-surface/40 p-6">
              <div className="text-3xl font-display font-extrabold text-accent/40">01</div>
              <h3 className="mt-2 text-base font-semibold text-white">Import Transcripts</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Upload or paste meeting transcripts (.txt, .md, .vtt) in seconds. Recall identifies participants and tracks who promised what.
              </p>
            </div>

            <div className="relative rounded-2xl border border-line bg-surface/40 p-6">
              <div className="text-3xl font-display font-extrabold text-accent-2/40">02</div>
              <h3 className="mt-2 text-base font-semibold text-white">Semantic Star Graph</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Recall extracts decisions, facts, and action items, clustering related topics into starry orbital systems and linking superseded ideas.
              </p>
            </div>

            <div className="relative rounded-2xl border border-line bg-surface/40 p-6">
              <div className="text-3xl font-display font-extrabold text-purple-400/40">03</div>
              <h3 className="mt-2 text-base font-semibold text-white">Ask in Real-time</h3>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Speak directly to the Voice Orb. Watch starlight beams illuminate exact evidence in space, with transcript proof displayed instantly.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="relative px-6 py-20 border-t border-line/60 bg-gradient-to-b from-paper to-[#03050d]">
        <div className="mx-auto max-w-4xl text-center rounded-3xl border border-line/80 bg-surface/60 p-10 md:p-16 backdrop-blur-xl shadow-2xl relative overflow-hidden">
          <div className="absolute -top-24 -left-24 h-64 w-64 rounded-full bg-accent/20 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -right-24 h-64 w-64 rounded-full bg-accent-2/20 blur-3xl pointer-events-none" />

          <h2 className="font-display text-3xl md:text-5xl font-bold tracking-tight text-white">
            Step into your memory space.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm md:text-base text-muted">
            Free yourself from taking endless notes and searching through recording archives. Your conversations are waiting in the stars.
          </p>

          <div className="mt-8 flex justify-center gap-4">
            <Link
              href="/space"
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[#7c5cff] to-[#3ee6c4] px-8 py-3.5 font-bold text-sm text-[#061018] shadow-[0_0_35px_rgba(124,92,255,0.7)] transition hover:scale-105"
            >
              Enter Recall Space →
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-line px-6 py-8 text-xs text-muted">
        <div className="mx-auto max-w-6xl flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center rounded-md bg-gradient-to-br from-[#7c5cff] to-[#3ee6c4] text-[10px] font-bold text-[#061018]">
              R
            </span>
            <span className="font-medium text-white">Recall</span>
            <span>· Built for the Bolna Symphony Buildathon</span>
          </div>

          <div className="flex items-center gap-6">
            <Link href="/space" className="hover:text-white transition">Space Canvas</Link>
            <Link href="/login" className="hover:text-white transition">Sign In</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
