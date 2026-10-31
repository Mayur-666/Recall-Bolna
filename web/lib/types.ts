// Mirrors the FastAPI response schemas (backend/app/schemas).

export type ConversationStatus = "queued" | "processing" | "ready" | "failed";
export type DecisionState = "proposed" | "decided" | "superseded" | "rejected" | "unresolved";
export type MemoryKind = "decision" | "commitment" | "action_item" | "fact" | "date" | "person";

export interface User {
  id: string;
  email: string;
  display_name: string;
}

export interface Conversation {
  id: string;
  title: string;
  conversation_date: string;
  participants: string[];
  self_speaker: string | null;
  source_type: "paste" | "upload" | "voice";
  original_filename: string | null;
  status: ConversationStatus;
  error_message: string | null;
  attempts: number;
  is_sample: boolean;
  created_at: string;
}

export interface Segment {
  seq: number;
  speaker: string | null;
  text: string;
  char_start: number;
  char_end: number;
}

export interface MemoryItem {
  id: string;
  conversation_id: string;
  kind: MemoryKind;
  topic: string;
  statement: string;
  speaker: string | null;
  owner: string | null;
  owner_is_user: boolean;
  due_date: string | null;
  decision_state: DecisionState | null;
  superseded_by_id: string | null;
  evidence_quote: string;
  char_start: number;
  char_end: number;
}

export interface ConversationDetail extends Conversation {
  transcript_text: string;
  segments: Segment[];
  memory_items: MemoryItem[];
}

export interface MemoryRow {
  id: string;
  conversation_id: string;
  conversation_title: string;
  conversation_date: string;
  kind: MemoryKind;
  topic: string;
  statement: string;
  speaker: string | null;
  owner: string | null;
  owner_is_user: boolean;
  due_date: string | null;
  decision_state: DecisionState | null;
  superseded_by_id: string | null;
  conflict_with_id: string | null;
  evidence_quote: string;
}

export interface Overview {
  conversation_count: number;
  memory_count: number;
  recent_decisions: MemoryRow[];
  open_action_items: MemoryRow[];
  needs_attention: { id: string; title: string; status: ConversationStatus; error: string | null }[];
}

export interface Evidence {
  ref: string;
  kind: string;
  conversation_id: string;
  conversation_title: string;
  conversation_date: string;
  relative_date: string;
  speaker: string | null;
  statement: string | null;
  excerpt: string;
  decision_state: DecisionState | null;
  superseded_by_ref: string | null;
  conflict: boolean;
  owner: string | null;
  owner_is_user: boolean;
  due_date: string | null;
  score: number;
  vector_similarity: number | null;
  related_to_ref: string | null;
  weak: boolean;
}

export interface SearchResult {
  status: "found" | "no_reliable_memory" | "ambiguous" | "error";
  results: Evidence[];
  memory_count: number;
  conversation_count: number;
  pending_conversations: string[];
  failed_conversations: string[];
  guidance: string;
  timings_ms: Record<string, number>;
  degraded: boolean;
}

export interface CallSession {
  id: string;
  channel: "web" | "phone";
  status: string;
  bolna_execution_id: string | null;
  created_at: string;
  ended_at: string | null;
  transcript: string | null;
  transcript_note: string | null;
}

export type CallEvent =
  | { type: "call_session_created"; channel: string }
  | {
      type: "tool_call_started";
      tool_call_id: string;
      tool: string;
      question?: string | null;
      standalone_query?: string | null;
      note?: string | null;
    }
  | {
      type: "tool_call_completed";
      tool_call_id: string;
      tool: string;
      status?: string;
      degraded?: boolean;
      timings_ms?: Record<string, number>;
      results?: Evidence[];
      context?: { conversation: string; date: string; when: string; lines: { speaker: string | null; text: string }[] };
      note?: string;
      conversation_id?: string | null;
    }
  | { type: "tool_call_failed"; tool_call_id: string; tool: string }
  | { type: "call_ended"; status: string }
  | { type: "transcript_available" };

export interface MemoryNode {
  id: string;
  kind: MemoryKind;
  statement: string;
  topic: string;
  decision_state: DecisionState | null;
  owner_is_user: boolean;
  speaker: string | null;
  conversation_id: string;
  conversation_title: string;
  conversation_date: string;
  chunk_ref: string | null;
  cluster: number | null;
  /** Client-only: a just-saved voice note still being processed into real memories. */
  pending?: boolean;
}

export interface MemoryGraph {
  nodes: MemoryNode[];
  clusters: { id: number; label: string; size: number }[];
  edges: { a: string; b: string; type: "similar" | "supersedes" | "conflicts"; weight: number }[];
}

export type MemoryEvent =
  | { type: "conversation_processing"; conversation_id: string; title: string }
  | {
      type: "conversation_ready";
      conversation_id: string;
      title: string;
      source_type: Conversation["source_type"];
      memories: { id: string; kind: MemoryKind; statement: string; decision_state: DecisionState | null }[];
    }
  | { type: "conversation_failed"; conversation_id: string; title: string; error: string };
