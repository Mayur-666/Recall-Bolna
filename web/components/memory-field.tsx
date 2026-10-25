"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { STATE_COLORS } from "@/components/ui";
import type { MemoryGraph, MemoryNode } from "@/lib/types";

const KIND_COLORS: Record<string, string> = {
  commitment: "#b69cff",
  action_item: "#b69cff",
  fact: "#5cd6ff",
  date: "#5cd6ff",
  person: "#ff8fd1",
};

export function nodeColor(n: Pick<MemoryNode, "kind" | "decision_state">): string {
  if (n.kind === "decision" && n.decision_state) return STATE_COLORS[n.decision_state];
  return KIND_COLORS[n.kind] ?? "#8f97c2";
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}

interface Placed {
  node: MemoryNode;
  x: number;
  y: number;
  phase: number;
  color: string;
}

interface Beam {
  target: string;
  start: number;
}

const BEAM_MS = 950;
const IGNITE_MS = 1800;

/**
 * A living map of every memory: clustered by topic, linked by "changed into" and
 * "conflicts with", and lit up when a search (or the voice agent) uses them as evidence.
 */
export function MemoryField({
  graph,
  highlight,
  pulseKey,
  onSelect,
  height = 460,
  centerLabel,
}: {
  graph: MemoryGraph;
  highlight: string[];
  pulseKey: number;
  onSelect?: (n: MemoryNode) => void;
  height?: number;
  centerLabel?: string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 800, h: height });
  const [hover, setHover] = useState<{ p: Placed; x: number; y: number } | null>(null);
  const beamsRef = useRef<Beam[]>([]);
  const placedRef = useRef<Placed[]>([]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.max(320, e.contentRect.width), h: height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [height]);

  // Deterministic layout: cluster centres on an ellipse around an empty middle (where the
  // voice orb lives), members in golden-angle spirals, unclustered memories in an outer ring.
  const layout = useMemo(() => {
    const { w, h } = size;
    const cx = w / 2;
    const cy = h / 2;
    const rx = w * 0.34;
    const ry = h * 0.33;
    const centres = graph.clusters.map((c, k) => {
      const a = (k / Math.max(1, graph.clusters.length)) * Math.PI * 2 - Math.PI / 2 + 0.35;
      return { id: c.id, label: c.label, x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a), r: 18 + 7 * Math.sqrt(c.size) };
    });
    const counters = new Map<number, number>();
    const placed: Placed[] = graph.nodes.map((n) => {
      const phase = hash(n.id) * Math.PI * 2;
      if (n.cluster !== null && centres[n.cluster]) {
        const i = counters.get(n.cluster) ?? 0;
        counters.set(n.cluster, i + 1);
        const a = i * 2.39996 + phase * 0.1;
        const r = 7 + 8.5 * Math.sqrt(i);
        return { node: n, x: centres[n.cluster].x + r * Math.cos(a), y: centres[n.cluster].y + r * Math.sin(a), phase, color: nodeColor(n) };
      }
      const a = hash(`${n.id}a`) * Math.PI * 2;
      const k = 1.18 + 0.2 * hash(`${n.id}r`);
      return {
        node: n,
        x: Math.min(w - 16, Math.max(16, cx + rx * k * Math.cos(a))),
        y: Math.min(h - 16, Math.max(16, cy + ry * k * Math.sin(a))),
        phase,
        color: nodeColor(n),
      };
    });
    const stars = Array.from({ length: Math.round((w * h) / 9000) }, (_, i) => ({
      x: hash(`s${i}x`) * w,
      y: hash(`s${i}y`) * h,
      r: 0.4 + hash(`s${i}r`) * 0.9,
      a: 0.15 + hash(`s${i}a`) * 0.35,
    }));
    return { placed, centres, stars, cx, cy };
  }, [graph, size]);
  placedRef.current = layout.placed;

  const matched = useMemo(() => {
    const refs = new Set(highlight);
    return new Set(
      layout.placed.filter((p) => refs.has(p.node.id) || (p.node.chunk_ref && refs.has(p.node.chunk_ref))).map((p) => p.node.id),
    );
  }, [highlight, layout.placed]);

  useEffect(() => {
    const now = performance.now();
    beamsRef.current = [...matched].map((target, i) => ({ target, start: now + i * 110 }));
  }, [pulseKey, matched]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size.w * dpr;
    canvas.height = size.h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const byId = new Map(layout.placed.map((p) => [p.node.id, p]));
    const lit = matched.size > 0;
    let raf = 0;

    const pos = (p: Placed, t: number) =>
      reduced ? [p.x, p.y] : [p.x + Math.sin(t * 0.0005 + p.phase) * 2.6, p.y + Math.cos(t * 0.00043 + p.phase) * 2.6];

    const draw = (t: number) => {
      ctx.clearRect(0, 0, size.w, size.h);
      for (const s of layout.stars) {
        ctx.globalAlpha = s.a * (reduced ? 1 : 0.7 + 0.3 * Math.sin(t * 0.001 + s.x));
        ctx.fillStyle = "#c9cfff";
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      for (const c of layout.centres) {
        const g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, c.r * 1.9);
        g.addColorStop(0, "rgba(139,123,255,0.16)");
        g.addColorStop(1, "rgba(139,123,255,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.r * 1.9, 0, Math.PI * 2);
        ctx.fill();
        ctx.font = "600 11px var(--font-display), sans-serif";
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(200,206,255,0.75)";
        ctx.fillText(c.label.toUpperCase(), c.x, c.y - c.r * 1.25 - 6);
      }

      for (const e of graph.edges) {
        const a = byId.get(e.a);
        const b = byId.get(e.b);
        if (!a || !b) continue;
        const [ax, ay] = pos(a, t);
        const [bx, by] = pos(b, t);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        if (e.type === "similar") {
          ctx.setLineDash([]);
          ctx.strokeStyle = "rgba(143,151,194,0.12)";
          ctx.lineWidth = 1;
        } else if (e.type === "supersedes") {
          ctx.setLineDash([5, 5]);
          ctx.lineDashOffset = reduced ? 0 : -t * 0.02;
          ctx.strokeStyle = "rgba(255,107,154,0.75)";
          ctx.lineWidth = 1.6;
        } else {
          ctx.setLineDash([2, 4]);
          ctx.strokeStyle = `rgba(255,90,90,${0.45 + 0.35 * Math.sin(t * 0.004)})`;
          ctx.lineWidth = 1.6;
        }
        ctx.stroke();
        ctx.setLineDash([]);
        if (e.type === "supersedes") {
          const ang = Math.atan2(by - ay, bx - ax);
          ctx.fillStyle = "rgba(255,107,154,0.9)";
          ctx.beginPath();
          ctx.moveTo(bx - 9 * Math.cos(ang), by - 9 * Math.sin(ang));
          ctx.lineTo(bx - 15 * Math.cos(ang - 0.4), by - 15 * Math.sin(ang - 0.4));
          ctx.lineTo(bx - 15 * Math.cos(ang + 0.4), by - 15 * Math.sin(ang + 0.4));
          ctx.fill();
        }
      }

      for (const p of layout.placed) {
        const [x, y] = pos(p, t);
        const on = matched.has(p.node.id);
        const dim = lit && !on;
        const r = on ? 6.5 : 4;
        const glow = ctx.createRadialGradient(x, y, 0, x, y, r * (on ? 5 : 3));
        glow.addColorStop(0, `${p.color}${dim ? "22" : on ? "cc" : "55"}`);
        glow.addColorStop(1, `${p.color}00`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(x, y, r * (on ? 5 : 3), 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = dim ? 0.35 : 1;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        if (p.node.owner_is_user) {
          ctx.strokeStyle = "rgba(255,255,255,0.85)";
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(x, y, r + 2.5, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }

      // Beams: from the centre (the orb) to each piece of evidence, then an ignition ripple.
      for (const b of beamsRef.current) {
        const p = byId.get(b.target);
        if (!p) continue;
        const [x, y] = pos(p, t);
        const k = (t - b.start) / BEAM_MS;
        if (k < 0) continue;
        if (k <= 1) {
          const mx = (layout.cx + x) / 2 + (y - layout.cy) * 0.18;
          const my = (layout.cy + y) / 2 - (x - layout.cx) * 0.18;
          const e = 1 - Math.pow(1 - k, 3);
          const hx = (1 - e) * (1 - e) * layout.cx + 2 * (1 - e) * e * mx + e * e * x;
          const hy = (1 - e) * (1 - e) * layout.cy + 2 * (1 - e) * e * my + e * e * y;
          const grad = ctx.createLinearGradient(layout.cx, layout.cy, hx, hy);
          grad.addColorStop(0, "rgba(139,123,255,0)");
          grad.addColorStop(1, "rgba(183,255,240,0.9)");
          ctx.strokeStyle = grad;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(layout.cx, layout.cy);
          ctx.quadraticCurveTo(mx, my, hx, hy);
          ctx.stroke();
          ctx.fillStyle = "#eafffa";
          ctx.beginPath();
          ctx.arc(hx, hy, 3, 0, Math.PI * 2);
          ctx.fill();
        } else {
          const r = (t - b.start - BEAM_MS) / IGNITE_MS;
          if (r < 1) {
            ctx.strokeStyle = `rgba(183,255,240,${0.8 * (1 - r)})`;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, 6 + 30 * r, 0, Math.PI * 2);
            ctx.stroke();
          }
        }
      }

      if (centerLabel) {
        ctx.font = "500 12px var(--font-inter), sans-serif";
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(200,206,255,0.55)";
        ctx.fillText(centerLabel, layout.cx, layout.cy + 4);
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [graph.edges, layout, matched, size, centerLabel]);

  function nearest(clientX: number, clientY: number): { p: Placed; x: number; y: number } | null {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    let best: Placed | null = null;
    let bestD = 14 * 14;
    for (const p of placedRef.current) {
      const d = (p.x - x) ** 2 + (p.y - y) ** 2;
      if (d < bestD) {
        best = p;
        bestD = d;
      }
    }
    return best ? { p: best, x, y } : null;
  }

  return (
    <div ref={wrapRef} className="relative w-full" style={{ height }}>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={`Memory field: ${graph.nodes.length} memories in ${graph.clusters.length} topics`}
        style={{ width: size.w, height: size.h, cursor: hover ? "pointer" : "default" }}
        onMouseMove={(e) => setHover(nearest(e.clientX, e.clientY))}
        onMouseLeave={() => setHover(null)}
        onClick={(e) => {
          const n = nearest(e.clientX, e.clientY);
          if (n && onSelect) onSelect(n.p.node);
        }}
      />
      {hover && (
        <div
          className="glass pointer-events-none absolute z-10 max-w-xs rounded-xl px-3 py-2 text-xs shadow-xl"
          style={{ left: Math.min(hover.x + 14, size.w - 260), top: Math.max(hover.y - 10, 0) }}
        >
          <p className="font-medium text-ink">{hover.p.node.statement}</p>
          <p className="mt-1 text-muted">
            {hover.p.node.conversation_title} · {hover.p.node.conversation_date}
            {hover.p.node.speaker && ` · ${hover.p.node.speaker}`}
          </p>
        </div>
      )}
      <ul className="sr-only">
        {graph.nodes.map((n) => (
          <li key={n.id}>
            {n.statement} ({n.conversation_title}, {n.conversation_date})
          </li>
        ))}
      </ul>
    </div>
  );
}

export function FieldLegend() {
  const items: [string, string][] = [
    [STATE_COLORS.decided, "Decided"],
    [STATE_COLORS.proposed, "Suggested"],
    [STATE_COLORS.unresolved, "Left open"],
    [STATE_COLORS.superseded, "Changed later"],
    [KIND_COLORS.commitment, "Commitment"],
    [KIND_COLORS.fact, "Fact / date"],
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      {items.map(([c, l]) => (
        <span key={l} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: c, boxShadow: `0 0 8px ${c}` }} />
          {l}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="h-px w-5 border-t border-dashed border-[#ff6b9a]" /> changed into
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-px w-5 border-t border-dotted border-[#ff5a5a]" /> conflicts
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full ring-1 ring-white" /> yours
      </span>
    </div>
  );
}
