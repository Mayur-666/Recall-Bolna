"use client";

import type { CSSProperties } from "react";

import { DecisionStateChip } from "@/components/ui";
import type { Evidence, SearchResult } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  chunk: "Transcript",
  decision: "Decision",
  commitment: "Commitment",
  action_item: "Action item",
  fact: "Fact",
  date: "Date",
  person: "Person",
};

// An excerpt that already starts with its own "Name:" label (multi-speaker chunks) needs no prefix.
const LABELED = /^[A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,2}:\s/;

// Chunks keep their "Name:" label; the speaker is shown separately, so drop the duplicate.
function stripSpeaker(excerpt: string, speaker: string | null): string {
  const prefix = speaker ? `${speaker}:` : null;
  return prefix && excerpt.startsWith(prefix) ? excerpt.slice(prefix.length).trimStart() : excerpt;
}

/**
 * The "Retrieved info" panel beside the memory field. Shared by /space and the landing-page demo,
 * so the demo is the real component, not a mock-up of it.
 */
export function EvidencePanel({
  question,
  result,
  onClose,
  onOpen,
  className = "",
  answer,
  answering = false,
  speaking = false,
  speakOn = false,
  onToggleSpeak,
  onReplay,
}: {
  question: string;
  result: Pick<SearchResult, "status" | "results">;
  onClose?: () => void;
  onOpen?: (e: Evidence) => void;
  className?: string;
  /** Spoken-style answer for a typed question (written from these results). */
  answer?: string | null;
  answering?: boolean;
  speaking?: boolean;
  speakOn?: boolean;
  onToggleSpeak?: () => void;
  onReplay?: () => void;
}) {
  const none = result.status === "no_reliable_memory";
  return (
    <aside
      aria-label="Retrieved Evidence"
      className={`flex flex-col overflow-hidden rounded-xl border border-line bg-surface-solid shadow-[0_24px_60px_-20px_rgba(0,0,0,0.7)] ${className}`}
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
          {none ? "Search result" : `Retrieved info · ${result.results.length}`}
        </span>
        <span className="flex items-center gap-1">
        {onToggleSpeak && (
          <button
            onClick={onToggleSpeak}
            aria-pressed={speakOn}
            title={speakOn ? "Answers are read aloud — click to mute" : "Read answers aloud"}
            className={`grid h-6 w-6 place-items-center rounded-md transition hover:bg-white/5 ${speakOn ? "text-accent" : "text-muted hover:text-ink"}`}
          >
            <SpeakerIcon on={speakOn} />
          </button>
        )}
        {onClose && (
          <button
            onClick={onClose}
            className="grid h-6 w-6 place-items-center rounded-md text-muted transition hover:bg-white/5 hover:text-ink"
            title="Close retrieved info"
          >
            ✕
          </button>
        )}
        </span>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {question && (
          <p className="px-1 text-xs text-muted">
            You asked <span className="text-ink">&ldquo;{question}&rdquo;</span>
          </p>
        )}

        {(answering || answer) && (
          <div className="rise-in rounded-lg border border-accent/30 bg-accent-soft px-3 py-2.5 text-[12.5px] leading-relaxed text-ink">
            <div className="mb-1 flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-accent">
                Recall
                {speaking && (
                  <span className="eq flex h-2.5 items-end gap-[2px]" aria-label="speaking">
                    <span className="h-full w-[2px] rounded-sm bg-accent" />
                    <span className="h-full w-[2px] rounded-sm bg-accent" />
                    <span className="h-full w-[2px] rounded-sm bg-accent" />
                  </span>
                )}
              </span>
              {answer && onReplay && !speaking && speakOn && (
                <button onClick={onReplay} className="font-mono text-[10px] text-muted transition hover:text-ink">
                  ▶ Replay
                </button>
              )}
            </div>
            {answer ? (
              <p>{answer}</p>
            ) : (
              <p className="flex items-center gap-1.5 text-muted">
                Thinking
                {[0, 150, 300].map((d) => (
                  <span key={d} className="h-1 w-1 animate-bounce rounded-full bg-accent" style={{ animationDelay: `${d}ms` }} />
                ))}
              </p>
            )}
          </div>
        )}

        {none ? (
          <div className="rise-in rounded-lg border border-[#93a7c4]/30 bg-[#93a7c4]/10 p-3 text-xs leading-relaxed text-[#c3cfe0]" style={{ animationDelay: "120ms" }}>
            No reliable memory of that in your conversations. Recall says so instead of guessing.
          </div>
        ) : (
          result.results.map((e, i) => (
            <article
              key={e.ref}
              onClick={onOpen ? () => onOpen(e) : undefined}
              style={{ animationDelay: `${120 + i * 90}ms` }}
              className={`rise-in group rounded-lg border border-line bg-raised/60 p-3 text-xs transition ${
                onOpen ? "cursor-pointer [transition-property:translate,border-color,background-color] hover:[translate:0_-1px] hover:border-accent/50 hover:bg-raised" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2 text-[11px] text-muted">
                <span className="truncate font-medium text-ink-sub">{e.conversation_title}</span>
                <span className="shrink-0 font-mono">{e.relative_date}</span>
              </div>

              {e.statement && (
                <p
                  className={`mt-1.5 font-medium leading-snug ${
                    e.decision_state === "superseded" ? "text-muted line-through decoration-[#e07a6e]/60" : "text-ink"
                  }`}
                >
                  {e.statement}
                </p>
              )}

              <blockquote className="mt-2 text-[11.5px] leading-relaxed text-ink-sub">
                {e.speaker && !LABELED.test(stripSpeaker(e.excerpt, e.speaker)) && (
                  <span className="font-medium text-muted">{e.speaker}: </span>
                )}
                <mark className="hl sweep" style={{ "--delay": `${380 + i * 90}ms` } as CSSProperties}>
                  {stripSpeaker(e.excerpt, e.speaker)}
                </mark>
              </blockquote>

              <div className="mt-2.5 flex items-center justify-between gap-2 text-[11px]">
                <span className="flex items-center gap-1.5">
                  <span className="rounded border border-line px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted">
                    {KIND_LABEL[e.kind] ?? e.kind}
                  </span>
                  <DecisionStateChip state={e.decision_state} />
                </span>
                {onOpen && (
                  <span className="text-accent opacity-80 transition-opacity group-hover:opacity-100">
                    Open transcript <span className="nudge-x">→</span>
                  </span>
                )}
              </div>
            </article>
          ))
        )}
      </div>
    </aside>
  );
}

function SpeakerIcon({ on }: { on: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M11 5 6 9H3v6h3l5 4z" />
      {on ? (
        <>
          <path d="M15.5 8.5a5 5 0 0 1 0 7" />
          <path d="M18.5 5.5a9 9 0 0 1 0 13" />
        </>
      ) : (
        <path d="m16 9 5 6m0-6-5 6" />
      )}
    </svg>
  );
}
