// Landing-page demo data. Every statement and quote comes verbatim from the seeded sample account
// (backend/seed/conversations/*.txt), and the answers follow the agent prompt's rules
// (backend/app/bolna/agent_prompt.md), so the demo shows what the product actually returns.

import type { DecisionState, Evidence, MemoryGraph, MemoryKind, MemoryNode, SearchResult } from "@/lib/types";

const CONV = {
  planning: { id: "conv-planning", title: "Deployment planning", date: "2026-10-19", when: "12 days ago" },
  followup: { id: "conv-followup", title: "Deployment follow-up", date: "2026-10-26", when: "5 days ago" },
  api: { id: "conv-api", title: "API design sync", date: "2026-10-22", when: "9 days ago" },
  db: { id: "conv-db", title: "Database choice", date: "2026-10-11", when: "20 days ago" },
  analytics: { id: "conv-analytics", title: "Analytics sync", date: "2026-10-28", when: "3 days ago" },
  hiring: { id: "conv-hiring", title: "Hiring sync", date: "2026-10-16", when: "15 days ago" },
  marketing: { id: "conv-marketing", title: "Marketing sync", date: "2026-10-17", when: "14 days ago" },
  pricing: { id: "conv-pricing", title: "Pricing discussion", date: "2026-10-25", when: "6 days ago" },
  design: { id: "conv-design", title: "Design review notes", date: "2026-10-29", when: "2 days ago" },
} as const;

type ConvKey = keyof typeof CONV;

function node(
  id: string,
  conv: ConvKey,
  cluster: number,
  kind: MemoryKind,
  statement: string,
  speaker: string | null,
  extra: { state?: DecisionState; mine?: boolean; topic?: string } = {},
): MemoryNode {
  const c = CONV[conv];
  return {
    id,
    kind,
    statement,
    topic: extra.topic ?? "",
    decision_state: extra.state ?? null,
    owner_is_user: extra.mine ?? false,
    speaker,
    conversation_id: c.id,
    conversation_title: c.title,
    conversation_date: c.date,
    chunk_ref: null,
    cluster,
  };
}

export const DEMO_GRAPH: MemoryGraph = {
  clusters: [
    { id: 0, label: "Beta deployment", size: 7 },
    { id: 1, label: "API & live updates", size: 6 },
    { id: 2, label: "Databases", size: 5 },
    { id: 3, label: "Launch dates & hiring", size: 6 },
    { id: 4, label: "Pricing", size: 3 },
    { id: 5, label: "Design", size: 3 },
  ],
  nodes: [
    node("m:ecs", "planning", 0, "decision", "Use AWS ECS for the beta deployment", "Mayur", { state: "superseded" }),
    node("m:render", "followup", 0, "decision", "Move the beta deployment to Render", "Mayur", { state: "decided" }),
    node("m:keep-ecs", "followup", 0, "decision", "Keep the ECS configuration in the repo for after the beta", "Mayur", { state: "decided" }),
    node("m:neha-ci", "planning", 0, "action_item", "Neha sets up the ECS cluster and the CI pipeline", "Neha"),
    node("m:neha-migrate", "followup", 0, "action_item", "Neha migrates the staging environment to Render tomorrow", "Neha"),
    node("m:rds", "planning", 0, "action_item", "Arjun handles the Postgres instance on RDS", "Arjun"),
    node("m:staging-date", "planning", 0, "date", "Staging live by October 30", "Mayur"),

    node("m:ws", "api", 1, "decision", "REST for the core API plus WebSockets for live updates", "Mayur", { state: "decided" }),
    node("m:v1", "api", 1, "decision", "Prefix every route with v1", "Mayur", { state: "decided" }),
    node("m:auth-spec", "api", 1, "commitment", "Write the auth spec for the WebSocket handshake by Friday, October 23", "Mayur", { mine: true }),
    node("m:gateway", "api", 1, "action_item", "Priya prototypes the WebSocket gateway this week", "Priya"),
    node("m:ratelimit", "api", 1, "decision", "Rate limiting on the socket — revisit next sprint", "Priya", { state: "unresolved" }),
    node("m:sse", "api", 1, "fact", "SSE is one-way; the mobile app needs to send acknowledgements", "Priya"),

    node("m:pg", "db", 2, "decision", "Postgres as the main application database", "Mayur", { state: "decided" }),
    node("m:mysql", "analytics", 2, "decision", "MySQL for the analytics database", "Mayur", { state: "decided" }),
    node("m:alembic", "db", 2, "action_item", "Arjun writes the migration scripts with Alembic", "Arjun"),
    node("m:export", "analytics", 2, "commitment", "Ravi has the first export running by Wednesday", "Ravi"),
    node("m:backups", "db", 2, "action_item", "Turn on daily backups from the start", "Priya"),

    node("m:portal", "hiring", 3, "date", "Careers portal launches November 12", "Kavya"),
    node("m:jds", "hiring", 3, "commitment", "Kavya sends the job descriptions by Monday", "Kavya"),
    node("m:engineers", "hiring", 3, "fact", "Two backend engineers needed before the end of the quarter", "Kavya"),
    node("m:campaign", "marketing", 3, "date", "Beta campaign launches December 1", "Sam"),
    node("m:budget", "marketing", 3, "decision", "Keep the campaign budget at the amount discussed", "Mayur", { state: "decided" }),
    node("m:sponsors", "marketing", 3, "action_item", "Sam books the newsletter sponsorships this week", "Sam"),

    node("m:tiers", "pricing", 4, "decision", "Three tiers: free, pro and team", "Priya", { state: "proposed" }),
    node("m:free-limit", "pricing", 4, "decision", "Free tier with a hard limit on stored conversations", "Mayur", { state: "proposed" }),
    node("m:pricing-open", "pricing", 4, "decision", "Leave pricing open until the beta numbers come in", "Neha", { state: "unresolved" }),

    node("m:inter", "design", 5, "decision", "Switch the primary font to Inter across the web app", null, { state: "decided" }),
    node("m:contrast", "design", 5, "action_item", "Fix the low contrast on dashboard cards before the beta", null),
    node("m:darkmode", "design", 5, "decision", "Dark mode postponed until after launch", null, { state: "decided" }),
  ],
  edges: [
    { a: "m:ecs", b: "m:render", type: "supersedes", weight: 1 },
    { a: "m:render", b: "m:neha-migrate", type: "similar", weight: 0.8 },
    { a: "m:ecs", b: "m:neha-ci", type: "similar", weight: 0.8 },
    { a: "m:ecs", b: "m:keep-ecs", type: "similar", weight: 0.78 },
    { a: "m:ws", b: "m:sse", type: "similar", weight: 0.82 },
    { a: "m:ws", b: "m:gateway", type: "similar", weight: 0.8 },
    { a: "m:auth-spec", b: "m:gateway", type: "similar", weight: 0.77 },
    { a: "m:pg", b: "m:mysql", type: "similar", weight: 0.79 },
    { a: "m:mysql", b: "m:export", type: "similar", weight: 0.76 },
    { a: "m:tiers", b: "m:free-limit", type: "similar", weight: 0.81 },
    { a: "m:free-limit", b: "m:pricing-open", type: "similar", weight: 0.78 },
    { a: "m:portal", b: "m:jds", type: "similar", weight: 0.76 },
  ],
};

function ev(
  ref: string,
  conv: ConvKey,
  kind: string,
  statement: string | null,
  speaker: string | null,
  excerpt: string,
  extra: Partial<Evidence> = {},
): Evidence {
  const c = CONV[conv];
  return {
    ref,
    kind,
    conversation_id: c.id,
    conversation_title: c.title,
    conversation_date: c.date,
    relative_date: c.when,
    speaker,
    statement,
    excerpt,
    decision_state: null,
    superseded_by_ref: null,
    conflict: false,
    owner: null,
    owner_is_user: false,
    due_date: null,
    score: 0,
    vector_similarity: null,
    related_to_ref: null,
    weak: false,
    ...extra,
  };
}

export interface DemoScenario {
  key: string;
  question: string;
  result: Pick<SearchResult, "status" | "results">;
  /** What the voice agent says back. */
  answer: string;
  /** Why this one is worth showing. */
  note: string;
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    key: "changed",
    question: "Which deployment provider did we pick?",
    note: "The decision changed. Recall answers with the current one and says what it replaced.",
    answer:
      "You're on Render. In the deployment follow-up five days ago you said you were dropping ECS and moving the beta to Render — that changed the earlier AWS ECS decision from deployment planning.",
    result: {
      status: "found",
      results: [
        ev("m:render", "followup", "decision", "Move the beta deployment to Render", "Mayur",
          "Mayur: Then we're dropping ECS and moving the beta deployment to Render. It's not worth the time right now.",
          { decision_state: "decided" }),
        ev("m:ecs", "planning", "decision", "Use AWS ECS for the beta deployment", "Mayur",
          "Mayur: Let's go with AWS ECS for the beta deployment. We have the credits and it scales.",
          { decision_state: "superseded", superseded_by_ref: "m:render" }),
      ],
    },
  },
  {
    key: "speaker",
    question: "What did Priya say about WebSockets?",
    note: "Answers name the speaker and the meeting, and link back to the exact line.",
    answer:
      "In the API design sync nine days ago, Priya suggested WebSockets because SSE is one-way and the mobile app needs to send acknowledgements back. You agreed: REST for the core API plus WebSockets for live updates.",
    result: {
      status: "found",
      results: [
        ev("m:sse", "api", "chunk", null, "Priya",
          "Priya: SSE is one-way though, and the mobile app needs to send acknowledgements back. I'd suggest WebSockets for the live updates."),
        ev("m:ws", "api", "decision", "REST for the core API plus WebSockets for live updates", "Mayur",
          "Mayur: Okay, decision then: we go with REST for the core API plus WebSockets for live updates.",
          { decision_state: "decided" }),
        ev("m:gateway", "api", "action_item", "Priya prototypes the WebSocket gateway this week", "Priya",
          "Priya: I can prototype the WebSocket gateway this week.", { owner: "Priya" }),
      ],
    },
  },
  {
    key: "mine",
    question: "What did I promise to do?",
    note: "It knows which speaker is you, so “I” and “my” questions work.",
    answer:
      "In the API design sync nine days ago, you said you'd write the auth spec for the WebSocket handshake and share it by Friday, October 23.",
    result: {
      status: "found",
      results: [
        ev("m:auth-spec", "api", "commitment", "Write the auth spec for the WebSocket handshake by Friday, October 23", "Mayur",
          "Mayur: I will write the auth spec for the WebSocket handshake and share it by Friday, October 23.",
          { owner: "Mayur", owner_is_user: true, due_date: "2026-10-23" }),
      ],
    },
  },
  {
    key: "none",
    question: "Who is our accountant?",
    note: "Nobody ever said. Recall tells you that instead of inventing a name.",
    answer: "I don't have a reliable memory of that in your conversations.",
    result: { status: "no_reliable_memory", results: [] },
  },
];
