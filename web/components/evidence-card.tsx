import Link from "next/link";

import { Chip, DecisionStateChip } from "@/components/ui";
import type { Evidence } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  chunk: "Transcript",
  decision: "Decision",
  commitment: "Commitment",
  action_item: "Action item",
  fact: "Fact",
  date: "Date",
  person: "Person",
};

export function EvidenceCard({ e }: { e: Evidence }) {
  return (
    <article data-testid="evidence-card" className={`rounded-lg border bg-surface p-3 text-sm ${e.weak ? "border-dashed opacity-80" : "border-line"}`}>
      <header className="flex flex-wrap items-center gap-2">
        <Link href={`/conversations/${e.conversation_id}`} className="font-medium hover:underline">
          {e.conversation_title}
        </Link>
        <span className="text-xs text-muted">{e.relative_date}</span>
        <span className="ml-auto flex flex-wrap items-center gap-1">
          <Chip>{KIND_LABEL[e.kind] ?? e.kind}</Chip>
          <DecisionStateChip state={e.decision_state} />
          {e.conflict && <Chip tone="rose">conflicting</Chip>}
          {e.related_to_ref && <Chip>linked decision</Chip>}
          {e.weak && <Chip>weak match</Chip>}
        </span>
      </header>
      {e.statement && <p className="mt-2 font-medium">{e.statement}</p>}
      <blockquote className="mt-2 border-l-2 border-accent/40 pl-3 text-muted">“{e.excerpt}”</blockquote>
      <footer className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
        {e.speaker && <span>Speaker: {e.speaker}</span>}
        {e.owner && <span>Owner: {e.owner_is_user ? "you" : e.owner}</span>}
        {e.due_date && <span>Due {e.due_date}</span>}
        {e.superseded_by_ref && <span>Changed later</span>}
      </footer>
    </article>
  );
}
