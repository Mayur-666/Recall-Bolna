"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type CSSProperties } from "react";

import { EvidencePanel } from "@/components/evidence-panel";
import { Logo } from "@/components/logo";
import { CountUp, Reveal } from "@/components/motion";
import { SpaceCanvas } from "@/components/space-canvas";
import { DecisionStateChip } from "@/components/ui";
import type { OrbState } from "@/components/voice-orb";
import { DEMO_GRAPH, DEMO_SCENARIOS } from "@/lib/demo-data";

type Phase = "listening" | "searching" | "answered";

// How long an answered question stays up before autoplay moves on.
const AUTO_MS = 7500;

const FAQ = [
  {
    q: "Where do the answers come from?",
    a: "Only from transcripts you add. Recall splits each one into speaker turns, extracts decisions, commitments, dates and facts with a quote that must match the transcript exactly, and searches those with a mix of keyword and vector search. The voice agent can only answer from what that search returns.",
  },
  {
    q: "What happens when it can't find something?",
    a: "If nothing clears the similarity threshold, search returns “no reliable memory” and the agent says so. It may mention the closest match, but it tells you it might not answer the question.",
  },
  {
    q: "How do I talk to it?",
    a: "Tap the orb in the app to start a browser call (Bolna Web Call — it needs microphone access), or enter your number and Recall calls your phone. The agent calls Recall's search while you're on the line, and the matching memories light up on screen as it answers.",
  },
  {
    q: "Can I just tell it things to remember?",
    a: "Yes. On a call, say “remember that we moved the demo to Friday” or “note that I'll send Priya the deck by Thursday”. Recall saves it as a voice note in your library, pulls out the decision, promise or date in a few seconds, and answers from it next time — including “what did I promise?”, because it knows the note is yours.",
  },
  {
    q: "What can I upload?",
    a: "Plain text, Markdown, WebVTT or SubRip transcripts — exports from Zoom, Meet, Teams or Otter work. Label lines as “Name: …” so Recall knows who said what; unlabeled lines are never attributed to anyone.",
  },
];

const delay = (ms: number) => ({ "--delay": `${ms}ms`, animationDelay: `${ms}ms` }) as CSSProperties;

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <Header />
      <Hero />
      <Demo />
      <HowItWorks />
      <Changes />
      <Honest />
      <Faq />
      <Footer />
    </div>
  );
}

const navLink =
  "relative py-1 transition hover:text-ink after:absolute after:inset-x-0 after:-bottom-0.5 after:h-px after:origin-left after:scale-x-0 after:bg-accent after:transition-transform after:duration-300 hover:after:scale-x-100";

function Header() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-50 border-b bg-paper transition-[border-color,box-shadow] duration-300 ${
        scrolled ? "border-line shadow-[0_10px_30px_-18px_rgba(0,0,0,0.9)]" : "border-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
        <Link href="/" aria-label="Recall home" className="group">
          <span className="inline-block transition-transform duration-300 group-hover:-rotate-3">
            <Logo size={22} />
          </span>
        </Link>
        <nav className="hidden items-center gap-7 text-sm text-muted md:flex">
          <a href="#demo" className={navLink}>Demo</a>
          <a href="#how" className={navLink}>How it works</a>
          <a href="#faq" className={navLink}>FAQ</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className="btn rounded-lg px-3 py-1.5 text-sm text-ink-sub transition hover:bg-white/5 hover:text-ink">
            Sign in
          </Link>
          <Link
            href="/space"
            className="btn group rounded-lg bg-accent px-3.5 py-1.5 text-sm font-semibold text-on-accent transition hover:brightness-105"
          >
            Try Recall <span className="nudge-x">→</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-5 pb-12 pt-16 md:pt-24">
      <p className="enter font-mono text-xs uppercase tracking-[0.18em] text-muted" style={delay(0)}>
        Voice memory for your meetings
      </p>
      <h1 className="mt-5 max-w-4xl font-display text-[40px] font-semibold leading-[1.05] tracking-[-0.03em] sm:text-6xl">
        <span className="enter block" style={delay(90)}>Ask what was decided.</span>
        <span className="enter block" style={delay(200)}>
          Hear the answer, <mark className="hero sweep" style={delay(750)}>see the line</mark>.
        </span>
      </h1>
      <p className="enter mt-6 max-w-xl text-base leading-relaxed text-ink-sub sm:text-lg" style={delay(320)}>
        Recall reads your meeting transcripts and answers out loud — who said it, in which meeting, and the exact
        quote. When a decision changed, it tells you. When nobody said it, it tells you that too.
      </p>
      <div className="enter mt-8 flex flex-wrap items-center gap-3" style={delay(430)}>
        <Link
          href="/login"
          className="btn group rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent shadow-[0_8px_24px_-10px_rgba(242,201,76,0.6)] transition hover:brightness-105 hover:shadow-[0_10px_30px_-8px_rgba(242,201,76,0.7)]"
        >
          Try Recall <span className="nudge-x">→</span>
        </Link>
        <a
          href="#demo"
          className="btn group rounded-lg border border-line px-5 py-2.5 text-sm font-medium text-ink-sub transition hover:border-white/20 hover:bg-white/[0.03] hover:text-ink"
        >
          Watch it answer <span className="nudge-y">↓</span>
        </a>
      </div>
    </section>
  );
}

/** The real /space components (memory field, orb, evidence panel) driven by the seeded sample account. */
function Demo() {
  const [idx, setIdx] = useState(0);
  const [run, setRun] = useState(0);
  const [phase, setPhase] = useState<Phase>("listening");
  const [typed, setTyped] = useState("");
  const [auto, setAuto] = useState(true);
  const [visible, setVisible] = useState(false);
  const [zoom, setZoom] = useState<number | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const scenario = DEMO_SCENARIOS[idx];

  useEffect(() => {
    setZoom(Math.max(0.36, Math.min(0.64, window.innerWidth / 1300)));
    const el = frameRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.35 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Play one question: the user speaks (typed out), Recall searches, then answers.
  useEffect(() => {
    if (!visible) return;
    const q = scenario.question;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let i = 0;
    setPhase("listening");
    setTyped("");
    const tick = setInterval(() => {
      i += 1;
      setTyped(q.slice(0, i));
      if (i >= q.length) {
        clearInterval(tick);
        timers.push(
          setTimeout(() => {
            setPhase("searching");
            timers.push(setTimeout(() => setPhase("answered"), 1100));
          }, 400),
        );
      }
    }, 32);
    return () => {
      clearInterval(tick);
      timers.forEach(clearTimeout);
    };
  }, [idx, run, visible, scenario.question]);

  // Autoplay through the questions until the visitor picks one.
  useEffect(() => {
    if (!auto || !visible || phase !== "answered") return;
    const t = setTimeout(() => setIdx((i) => (i + 1) % DEMO_SCENARIOS.length), AUTO_MS);
    return () => clearTimeout(t);
  }, [auto, visible, phase]);

  const answered = phase === "answered";
  const none = scenario.result.status === "no_reliable_memory";
  const orbState: OrbState = phase === "listening" ? "listening" : phase === "searching" ? "searching" : none ? "no-memory" : "found";
  const lit = answered && !none ? scenario.result.results.map((r) => r.ref) : [];

  function pick(i: number) {
    setAuto(false);
    setIdx(i);
    setRun((r) => r + 1);
  }

  return (
    <section id="demo" className="mx-auto max-w-6xl scroll-mt-20 px-5 pb-20">
      <Reveal>
        <div
          ref={frameRef}
          className="overflow-hidden rounded-2xl border border-line bg-surface-solid shadow-[0_40px_80px_-40px_rgba(0,0,0,0.9)]"
        >
          {/* the app's own header row */}
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <div className="flex items-center gap-3">
              <Logo size={18} className="text-sm" />
              <span className="hidden font-mono text-[11px] text-muted sm:inline">
                {DEMO_GRAPH.nodes.length} memories · {DEMO_GRAPH.clusters.length} topics · 9 sample conversations
              </span>
            </div>
            <span className="flex items-center gap-2 rounded-md border border-line px-2.5 py-1 text-[11px] text-ink-sub">
              {phase === "listening" ? (
                <span className="eq flex h-2.5 items-end gap-[2px]" aria-hidden>
                  <span className="h-full w-[3px] rounded-sm bg-[#86c79a]" />
                  <span className="h-full w-[3px] rounded-sm bg-[#86c79a]" />
                  <span className="h-full w-[3px] rounded-sm bg-[#86c79a]" />
                </span>
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-[#86c79a]" />
              )}
              {phase === "listening" ? "Hearing you" : phase === "searching" ? "Searching" : "On a call"}
            </span>
          </div>

          <div className="relative h-[400px] sm:h-[480px] lg:h-[560px]">
            {zoom !== null && (
              <SpaceCanvas
                graph={DEMO_GRAPH}
                highlightRefs={lit}
                pulseKey={idx * 1000 + run}
                orbState={orbState}
                audioLevel={phase === "listening" ? 0.25 + 0.2 * Math.sin(typed.length) : answered ? 0.3 : 0}
                onOrbClick={() => pick(idx)}
                orbLabel="Replay"
                interactive={false}
                initialZoom={zoom}
              />
            )}

            {answered && (
              <EvidencePanel
                key={`${idx}-${run}`}
                question={scenario.question}
                result={scenario.result}
                className="rise-in absolute left-4 top-4 z-30 hidden max-h-[calc(100%-2rem)] w-80 lg:flex"
              />
            )}

            {/* spoken exchange (overlaid on wide screens, below the field on narrow ones) */}
            <div className="pointer-events-none absolute bottom-4 right-4 z-30 hidden w-[380px] space-y-2 lg:block">
              <Exchange phase={phase} typed={typed} answer={scenario.answer} />
            </div>
          </div>

          <div className="space-y-2 border-t border-line p-3 lg:hidden">
            <Exchange phase={phase} typed={typed} answer={scenario.answer} />
          </div>

          {answered && (
            <div className="border-t border-line p-3 lg:hidden">
              <EvidencePanel key={`m-${idx}-${run}`} question={scenario.question} result={scenario.result} className="rise-in" />
            </div>
          )}
        </div>
      </Reveal>

      {/* question picker */}
      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {DEMO_SCENARIOS.map((s, i) => {
          const active = i === idx;
          return (
            <Reveal key={s.key} delay={120 + i * 70}>
              <button
                onClick={() => pick(i)}
                className={`lift relative h-full w-full overflow-hidden rounded-xl border p-3.5 text-left ${
                  active ? "border-accent/50 bg-accent-soft" : "border-line hover:border-white/20 hover:bg-white/[0.02]"
                }`}
              >
                <span className="block text-sm font-medium text-ink">&ldquo;{s.question}&rdquo;</span>
                <span className="mt-1.5 block text-xs leading-relaxed text-muted">{s.note}</span>
                {active && auto && answered && (
                  <span
                    key={`${idx}-${run}`}
                    className="countdown absolute inset-x-0 bottom-0 h-0.5 bg-accent/70"
                    style={{ animationDuration: `${AUTO_MS}ms` }}
                  />
                )}
              </button>
            </Reveal>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[11px] text-muted">
          Real components from the app, running on the seeded sample account. Quotes are verbatim from its transcripts.
        </p>
        <button
          onClick={() => setAuto((a) => !a)}
          className="rounded-md border border-line px-2.5 py-1 font-mono text-[11px] text-muted transition hover:border-white/20 hover:text-ink"
        >
          {auto ? "❚❚ Pause tour" : "▶ Play tour"}
        </button>
      </div>
    </section>
  );
}

function Exchange({ phase, typed, answer }: { phase: Phase; typed: string; answer: string }) {
  return (
    <>
      <Line who="You" text={typed} typing={phase === "listening"} />
      {phase === "searching" && <Line who="Recall" text="Searching your conversations…" dim searching />}
      {phase === "answered" && <Line who="Recall" text={answer} accent />}
    </>
  );
}

function Line({
  who,
  text,
  typing,
  dim,
  accent,
  searching,
}: {
  who: string;
  text: string;
  typing?: boolean;
  dim?: boolean;
  accent?: boolean;
  searching?: boolean;
}) {
  return (
    <div
      className={`rise-in rounded-lg border px-3 py-2 text-[13px] leading-relaxed shadow-lg ${
        accent ? "border-accent/30 bg-surface-solid" : "border-line bg-surface-solid/95"
      }`}
    >
      <span className={`mr-2 font-mono text-[10px] uppercase tracking-wider ${accent ? "text-accent" : "text-muted"}`}>{who}</span>
      <span className={`${dim ? "text-muted" : "text-ink"} ${typing ? "caret" : ""}`}>{text}</span>
      {searching && (
        <span className="ml-1.5 inline-flex gap-0.5 align-middle" aria-hidden>
          {[0, 150, 300].map((d) => (
            <span key={d} className="h-1 w-1 animate-bounce rounded-full bg-accent" style={{ animationDelay: `${d}ms` }} />
          ))}
        </span>
      )}
    </div>
  );
}

function SectionHead({ kicker, title, children }: { kicker: string; title: string; children?: React.ReactNode }) {
  return (
    <Reveal className="max-w-2xl">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted">{kicker}</p>
      <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.02em] sm:text-4xl">{title}</h2>
      {children && <p className="mt-4 text-base leading-relaxed text-ink-sub">{children}</p>}
    </Reveal>
  );
}

function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-20 border-t border-line">
      <div className="mx-auto max-w-6xl px-5 py-20">
        <SectionHead kicker="How it works" title="From transcript to spoken answer" />
        <div className="mt-12 grid gap-4 lg:grid-cols-3">
          <Step i={0} n="01" title="Add a transcript" body="Paste it or upload .txt, .md, .vtt or .srt. Recall keeps each speaker's turns and their exact position in the text.">
            <div className="space-y-1.5 font-mono text-[11.5px] leading-relaxed text-ink-sub">
              <p><span className="text-muted">Neha:</span> I had it running in an afternoon as a test…</p>
              <p>
                <span className="text-muted">Mayur:</span>{" "}
                <mark className="hl sweep-on-reveal" style={{ "--sweep-delay": "550ms" } as CSSProperties}>
                  Then we&apos;re dropping ECS and moving the beta deployment to Render.
                </mark>
              </p>
              <p><span className="text-muted">Neha:</span> Agreed. I&apos;ll migrate the staging environment…</p>
            </div>
          </Step>
          <Step i={1} n="02" title="Recall pulls out what matters" body="Decisions, commitments, dates and facts — each one must quote the transcript word for word, or it's thrown away.">
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="pop-on-reveal rounded border border-line px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted" style={delay(500)}>
                  Decision
                </span>
                <span className="pop-on-reveal inline-block" style={delay(620)}>
                  <DecisionStateChip state="decided" />
                </span>
              </div>
              <p className="pop-on-reveal font-medium text-ink" style={delay(740)}>Move the beta deployment to Render</p>
              <p className="pop-on-reveal font-mono text-[11px] text-muted" style={delay(860)}>Mayur · Deployment follow-up · chars 238–303</p>
            </div>
          </Step>
          <Step i={2} n="03" title="Ask out loud" body="Tap the orb or have Recall call your phone. Ask anything — or say “remember that…” and it saves a new memory on the spot.">
            <div className="space-y-2 text-[12.5px] leading-relaxed">
              <p className="pop-on-reveal" style={delay(600)}>
                <span className="mr-2 font-mono text-[10px] uppercase text-muted">You</span>Where are we deploying the beta?
              </p>
              <p className="pop-on-reveal" style={delay(1200)}>
                <span className="mr-2 font-mono text-[10px] uppercase text-accent">Recall</span>On Render — you moved it off ECS five days ago.
              </p>
            </div>
          </Step>
        </div>
      </div>
    </section>
  );
}

function Step({ i, n, title, body, children }: { i: number; n: string; title: string; body: string; children: React.ReactNode }) {
  return (
    <Reveal delay={i * 110} className="h-full">
      <div className="lift group flex h-full flex-col rounded-2xl border border-line bg-surface-solid hover:border-white/15">
        <div className="min-h-[148px] border-b border-line p-5">{children}</div>
        <div className="p-5">
          <p className="font-mono text-xs text-accent">{n}</p>
          <h3 className="mt-2 text-lg font-semibold">{title}</h3>
          <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
        </div>
      </div>
    </Reveal>
  );
}

function Changes() {
  return (
    <section className="border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 lg:grid-cols-2 lg:items-center">
        <SectionHead kicker="Decisions change" title="It knows which answer is current">
          Notes keep the first thing anyone wrote down. Recall links a later decision to the one it replaced, so you
          get today&apos;s answer and can still see what it used to be. If two meetings genuinely contradict each other,
          it asks you which one applies instead of picking.
        </SectionHead>

        <Reveal as="ol" className="relative space-y-4 pl-6">
          <span className="draw-down absolute bottom-2 left-0 top-2 w-px bg-line" aria-hidden />
          <li className="relative">
            <span className="pop-on-reveal absolute -left-[29px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-paper bg-[#e07a6e]" style={delay(200)} />
            <p className="font-mono text-[11px] text-muted">Deployment planning · 12 days ago</p>
            <div className="mt-2 rounded-xl border border-line bg-surface-solid p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm text-muted">
                  <span className="strike" style={{ "--strike-delay": "1100ms" } as CSSProperties}>Use AWS ECS for the beta deployment</span>
                </p>
                <span className="pop-on-reveal" style={delay(1500)}>
                  <DecisionStateChip state="superseded" />
                </span>
              </div>
              <p className="mt-2 text-xs text-ink-sub">
                <span className="text-muted">Mayur:</span> Let&apos;s go with AWS ECS for the beta deployment. We have the credits and it scales.
              </p>
            </div>
          </li>
          <li className="pop-on-reveal relative" style={delay(800)}>
            <span className="absolute -left-[29px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-paper bg-[#86c79a]" />
            <p className="font-mono text-[11px] text-muted">Deployment follow-up · 5 days ago</p>
            <div className="mt-2 rounded-xl border border-accent/30 bg-surface-solid p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-ink">Move the beta deployment to Render</p>
                <DecisionStateChip state="decided" />
              </div>
              <p className="mt-2 text-xs text-ink-sub">
                <span className="text-muted">Mayur:</span>{" "}
                <mark className="hl sweep-on-reveal" style={{ "--sweep-delay": "1700ms" } as CSSProperties}>
                  Then we&apos;re dropping ECS and moving the beta deployment to Render.
                </mark>
              </p>
            </div>
          </li>
        </Reveal>
      </div>
    </section>
  );
}

function Honest() {
  const stats = [
    { v: <><CountUp to={18} /> / 18</>, l: "retrieval eval cases pass, including 6 held-out questions it should refuse or paraphrase" },
    { v: <><CountUp to={27} /> ms</>, l: "p95 search latency over 100 warm queries (keyword + vector, fused)" },
    { v: <CountUp to={0.97} decimals={2} />, l: "share of extracted quotes that match the transcript exactly, with qwen2.5 7B running locally" },
  ];
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-6xl px-5 py-20">
        <SectionHead kicker="When it doesn't know" title="“I don't have a reliable memory of that.”">
          Recall would rather say nothing than make something up. A question nobody discussed — like who your
          accountant is — gets a plain no, and the memory field stays dark.
        </SectionHead>
        <Reveal delay={100}>
          <dl className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-3">
            {stats.map((s, i) => (
              <div key={i} className="group bg-paper p-6 transition-colors duration-300 hover:bg-surface-solid">
                <dt className="font-display text-3xl font-semibold tracking-tight transition-colors duration-300 group-hover:text-accent">{s.v}</dt>
                <dd className="mt-2 text-sm leading-relaxed text-muted">{s.l}</dd>
              </div>
            ))}
          </dl>
        </Reveal>
        <p className="mt-3 font-mono text-[11px] text-muted">Measured on the seeded sample account — see docs/eval-results.md and docs/model-benchmark.md.</p>
      </div>
    </section>
  );
}

function Faq() {
  return (
    <section id="faq" className="scroll-mt-20 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 lg:grid-cols-[1fr_1.4fr]">
        <SectionHead kicker="FAQ" title="Questions people ask first" />
        <Reveal delay={100} className="divide-y divide-line border-y border-line">
          {FAQ.map((f, i) => (
            <details key={f.q} className="group py-4" open={i === 0}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-medium text-ink transition-colors hover:text-accent">
                {f.q}
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-line font-mono text-muted transition duration-300 group-open:rotate-45 group-open:border-accent/40 group-open:text-accent">
                  +
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-ink-sub">{f.a}</p>
            </details>
          ))}
        </Reveal>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-6xl px-5 py-16">
        <Reveal>
          <div className="flex flex-col items-start justify-between gap-6 rounded-2xl border border-line bg-surface-solid p-8 transition-colors duration-300 hover:border-accent/30 sm:flex-row sm:items-center">
            <div>
              <h2 className="font-display text-2xl font-semibold tracking-tight">Try it on the sample meetings</h2>
              <p className="mt-1.5 text-sm text-muted">Nine seeded conversations. Sign in with the demo account and ask anything.</p>
            </div>
            <Link
              href="/login"
              className="btn group shrink-0 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent transition hover:brightness-105"
            >
              Open the demo <span className="nudge-x">→</span>
            </Link>
          </div>
        </Reveal>
        <div className="mt-10 flex flex-col justify-between gap-3 text-xs text-muted sm:flex-row">
          <Logo size={18} className="text-sm" />
          <span>Built for the Bolna Symphony Buildathon · voice by Bolna</span>
        </div>
      </div>
    </footer>
  );
}
