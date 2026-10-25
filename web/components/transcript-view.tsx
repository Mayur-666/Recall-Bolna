import type { MemoryItem } from "@/lib/types";

interface Span {
  id: string;
  start: number;
  end: number;
}

/** Renders the original transcript with evidence quotes highlighted at their exact offsets. */
export function TranscriptView({ text, items, activeId }: { text: string; items: MemoryItem[]; activeId: string | null }) {
  // Non-overlapping spans, earliest first; an overlapping quote is clipped, never dropped silently.
  const spans: Span[] = [];
  for (const it of [...items].sort((a, b) => a.char_start - b.char_start)) {
    const prevEnd = spans.length ? spans[spans.length - 1].end : 0;
    const start = Math.max(it.char_start, prevEnd);
    if (start < it.char_end) spans.push({ id: it.id, start, end: it.char_end });
  }
  const parts: React.ReactNode[] = [];
  let pos = 0;
  for (const s of spans) {
    if (s.start > pos) parts.push(text.slice(pos, s.start));
    parts.push(
      <mark key={s.id} id={`ev-${s.id}`} className={`evidence ${activeId === s.id ? "active" : ""}`}>
        {text.slice(s.start, s.end)}
      </mark>,
    );
    pos = s.end;
  }
  parts.push(text.slice(pos));
  return <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-surface p-4 font-sans text-sm leading-relaxed">{parts}</pre>;
}
