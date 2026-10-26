"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { STATE_COLORS } from "@/components/ui";
import { VoiceOrb, type OrbState } from "@/components/voice-orb";
import type { MemoryGraph, MemoryNode } from "@/lib/types";

const KIND_COLORS: Record<string, string> = {
  commitment: "#b69cff",
  action_item: "#b69cff",
  fact: "#5cd6ff",
  date: "#5cd6ff",
  person: "#ff8fd1",
  decision: "#3ee6c4",
};

export function getNodeColor(n: Pick<MemoryNode, "kind" | "decision_state">): string {
  if (n.kind === "decision" && n.decision_state) return STATE_COLORS[n.decision_state] || "#3ee6c4";
  return KIND_COLORS[n.kind] ?? "#8f97c2";
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}

export interface PlacedNode {
  node: MemoryNode;
  x: number; // world coordinates
  y: number; // world coordinates
  phase: number;
  color: string;
}

interface Beam {
  target: string;
  start: number;
}

const BEAM_MS = 1000;

interface SpaceCanvasProps {
  graph: MemoryGraph;
  highlightRefs: string[];
  pulseKey: number;
  orbState: OrbState;
  audioLevel: number;
  onOrbClick: () => void;
  orbLabel: string;
  onSelectNode?: (node: MemoryNode) => void;
  onInspectTranscript?: (conversationId: string, memoryId?: string) => void;
}

export function SpaceCanvas({
  graph,
  highlightRefs,
  pulseKey,
  orbState,
  audioLevel,
  onOrbClick,
  orbLabel,
  onSelectNode,
  onInspectTranscript,
}: SpaceCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const orbWrapperRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 1200, h: 800 });

  // Continuous ref-based transform for 120fps flicker-free animation
  const zoomRef = useRef(1);
  const panRef = useRef({ x: 0, y: 0 });
  const targetZoomRef = useRef(1);
  const targetPanRef = useRef({ x: 0, y: 0 });

  // Dragging and touch refs
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const panStartRef = useRef({ x: 0, y: 0 });
  const initialPinchDistRef = useRef<number | null>(null);
  const initialPinchZoomRef = useRef<number>(1);

  // Hover and selection state for tooltips
  const [hoveredNode, setHoveredNode] = useState<{ node: MemoryNode; screenX: number; screenY: number } | null>(null);
  const [selectedNode, setSelectedNode] = useState<MemoryNode | null>(null);

  const beamsRef = useRef<Beam[]>([]);

  // Observe container size
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const updateSize = () => {
      setSize({
        w: el.clientWidth || window.innerWidth,
        h: el.clientHeight || window.innerHeight,
      });
    };
    updateSize();
    const ro = new ResizeObserver(updateSize);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Compute celestial layout in world coordinates
  const layout = useMemo(() => {
    const rx = 360;
    const ry = 280;

    const centres = graph.clusters.map((c, k) => {
      const a = (k / Math.max(1, graph.clusters.length)) * Math.PI * 2 - Math.PI / 2 + 0.35;
      return {
        id: c.id,
        label: c.label,
        x: rx * Math.cos(a),
        y: ry * Math.sin(a),
        r: 28 + 9 * Math.sqrt(c.size),
      };
    });

    const counters = new Map<number, number>();
    const placed: PlacedNode[] = graph.nodes.map((n) => {
      const phase = hash(n.id) * Math.PI * 2;
      if (n.cluster !== null && centres[n.cluster]) {
        const i = counters.get(n.cluster) ?? 0;
        counters.set(n.cluster, i + 1);
        const a = i * 2.39996 + phase * 0.1;
        const r = 24 + 11 * Math.sqrt(i);
        return {
          node: n,
          x: centres[n.cluster].x + r * Math.cos(a),
          y: centres[n.cluster].y + r * Math.sin(a),
          phase,
          color: getNodeColor(n),
        };
      }
      const a = hash(`${n.id}a`) * Math.PI * 2;
      const k = 1.3 + 0.3 * hash(`${n.id}r`);
      return {
        node: n,
        x: rx * k * Math.cos(a),
        y: ry * k * Math.sin(a),
        phase,
        color: getNodeColor(n),
      };
    });

    // Deep space stars (fixed in world space)
    const stars = Array.from({ length: 280 }, (_, i) => ({
      x: (hash(`s${i}x`) - 0.5) * 3200,
      y: (hash(`s${i}y`) - 0.5) * 2400,
      r: 0.5 + hash(`s${i}r`) * 1.5,
      a: 0.2 + hash(`s${i}a`) * 0.65,
      flickerSpeed: 0.001 + hash(`s${i}f`) * 0.003,
    }));

    return { placed, centres, stars };
  }, [graph]);

  // Set of matched node IDs based on highlightRefs (can match node id or chunk_ref)
  const matched = useMemo(() => {
    const refs = new Set(highlightRefs);
    return new Set(
      layout.placed
        .filter((p) => refs.has(p.node.id) || (p.node.chunk_ref && refs.has(p.node.chunk_ref)))
        .map((p) => p.node.id)
    );
  }, [highlightRefs, layout.placed]);

  // Launch light beams when pulseKey or matched changes
  useEffect(() => {
    const now = performance.now();
    beamsRef.current = [...matched].map((target, i) => ({
      target,
      start: now + i * 110,
    }));
  }, [pulseKey, matched]);

  // SEPARATE EFFECT: Resize canvas only when container size changes (NEVER on zoom!)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size.w * dpr;
    canvas.height = size.h * dpr;
  }, [size]);

  // Native non-passive Wheel & Trackpad Pinch listener
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onNativeWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (e.ctrlKey) {
        // Trackpad 2-finger pinch zoom
        const factor = Math.exp(-e.deltaY * 0.008);
        const prevZoom = targetZoomRef.current;
        const nextZoom = Math.max(0.35, Math.min(2.8, prevZoom * factor));

        // Keep position under cursor stable
        const worldX = (mouseX - (size.w / 2 + targetPanRef.current.x)) / prevZoom;
        const worldY = (mouseY - (size.h / 2 + targetPanRef.current.y)) / prevZoom;

        targetZoomRef.current = nextZoom;
        targetPanRef.current.x = mouseX - size.w / 2 - worldX * nextZoom;
        targetPanRef.current.y = mouseY - size.h / 2 - worldY * nextZoom;
      } else if (Math.abs(e.deltaX) > 0 || Math.abs(e.deltaY) > 0) {
        // 2-finger trackpad pan or wheel scroll
        targetPanRef.current.x -= e.deltaX * 0.85;
        targetPanRef.current.y -= e.deltaY * 0.85;
      }
    };

    el.addEventListener("wheel", onNativeWheel, { passive: false });
    return () => el.removeEventListener("wheel", onNativeWheel);
  }, [size]);

  // Continuous Canvas Drawing Loop (runs smoothly without re-initializing on zoom/pan)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const byId = new Map(layout.placed.map((p) => [p.node.id, p]));
    const lit = matched.size > 0;
    let raf = 0;

    const pos = (p: PlacedNode, t: number) => [
      p.x + Math.sin(t * 0.0006 + p.phase) * 3.2,
      p.y + Math.cos(t * 0.0005 + p.phase) * 3.2,
    ];

    const draw = (t: number) => {
      const dpr = window.devicePixelRatio || 1;

      // Smooth interpolation for silky 60/120fps motion
      zoomRef.current += (targetZoomRef.current - zoomRef.current) * 0.22;
      panRef.current.x += (targetPanRef.current.x - panRef.current.x) * 0.22;
      panRef.current.y += (targetPanRef.current.y - panRef.current.y) * 0.22;

      const z = zoomRef.current;
      const px = panRef.current.x;
      const py = panRef.current.y;

      // Update Orb position without triggering React re-renders
      if (orbWrapperRef.current) {
        const ox = size.w / 2 + px;
        const oy = size.h / 2 + py;
        const orbScale = Math.max(0.85, Math.min(1.15, z));
        orbWrapperRef.current.style.transform = `translate3d(${ox}px, ${oy}px, 0) translate(-50%, -50%) scale(${orbScale})`;
      }

      ctx.save();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size.w, size.h);

      // Apply Pan and Zoom
      ctx.translate(size.w / 2 + px, size.h / 2 + py);
      ctx.scale(z, z);

      // 1. Draw Starfield
      for (const s of layout.stars) {
        const alpha = s.a * (0.65 + 0.35 * Math.sin(t * s.flickerSpeed + s.x));
        ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
        ctx.fillStyle = "#dce2ff";
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      // 2. Draw Gravitational Orbital Rings
      const rings = [180, 320, 480, 640];
      for (const r of rings) {
        ctx.strokeStyle = "rgba(139, 123, 255, 0.07)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(0, 0, r, 0, Math.PI * 2);
        ctx.stroke();
      }

      // 3. Draw Cluster Atmosphere & Labels
      for (const c of layout.centres) {
        const g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, c.r * 2.2);
        g.addColorStop(0, "rgba(124, 92, 255, 0.12)");
        g.addColorStop(0.6, "rgba(62, 230, 196, 0.04)");
        g.addColorStop(1, "rgba(124, 92, 255, 0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.r * 2.2, 0, Math.PI * 2);
        ctx.fill();

        ctx.font = "600 11px var(--font-display), sans-serif";
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(180, 195, 255, 0.7)";
        ctx.fillText(c.label.toUpperCase(), c.x, c.y - c.r * 1.3 - 6);
      }

      // 4. Draw Edges / Constellation Filaments
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
          ctx.strokeStyle = "rgba(143, 151, 194, 0.15)";
          ctx.lineWidth = 1;
        } else if (e.type === "supersedes") {
          ctx.setLineDash([5, 5]);
          ctx.lineDashOffset = -t * 0.02;
          ctx.strokeStyle = "rgba(255, 107, 154, 0.7)";
          ctx.lineWidth = 1.6;
        } else {
          ctx.setLineDash([3, 4]);
          ctx.strokeStyle = `rgba(255, 90, 90, ${0.4 + 0.3 * Math.sin(t * 0.004)})`;
          ctx.lineWidth = 1.6;
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // 5. Draw Light Beams from Core (0, 0) to Highlighted Nodes
      for (const b of beamsRef.current) {
        const p = byId.get(b.target);
        if (!p) continue;
        const [x, y] = pos(p, t);
        const k = (t - b.start) / BEAM_MS;
        if (k < 0) continue;
        if (k <= 1) {
          const mx = x / 2 + y * 0.15;
          const my = y / 2 - x * 0.15;
          const e = 1 - Math.pow(1 - k, 3);
          const hx = 2 * (1 - e) * e * mx + e * e * x;
          const hy = 2 * (1 - e) * e * my + e * e * y;

          const grad = ctx.createLinearGradient(0, 0, hx, hy);
          grad.addColorStop(0, "rgba(139, 123, 255, 0.1)");
          grad.addColorStop(0.7, "rgba(62, 230, 196, 0.85)");
          grad.addColorStop(1, "rgba(255, 255, 255, 1)");

          ctx.strokeStyle = grad;
          ctx.lineWidth = 2.4;
          ctx.beginPath();
          ctx.moveTo(0, 0);
          ctx.quadraticCurveTo(mx, my, hx, hy);
          ctx.stroke();

          // Spark head
          ctx.fillStyle = "#ffffff";
          ctx.beginPath();
          ctx.arc(hx, hy, 3.5, 0, Math.PI * 2);
          ctx.fill();
        } else if (k < 2.0) {
          // Expanding ignition ripple ring around target
          const pulseProgress = (k - 1) / 1.0;
          const pulseR = 8 + pulseProgress * 36;
          ctx.strokeStyle = `rgba(62, 230, 196, ${1 - pulseProgress})`;
          ctx.lineWidth = 1.8 * (1 - pulseProgress);
          ctx.beginPath();
          ctx.arc(x, y, pulseR, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // 6. Draw Memory Nodes (Stars)
      for (const p of layout.placed) {
        const [x, y] = pos(p, t);
        const on = matched.has(p.node.id);
        const isHovered = hoveredNode?.node.id === p.node.id;
        const isSelected = selectedNode?.id === p.node.id;
        const dim = lit && !on;

        const baseR = on ? 7 : isHovered || isSelected ? 6.5 : 4.5;
        const glowR = baseR * (on ? 5 : isHovered ? 4 : 2.5);

        // Radial glow
        const glow = ctx.createRadialGradient(x, y, 0, x, y, glowR);
        glow.addColorStop(0, `${p.color}${dim ? "22" : on ? "ee" : "77"}`);
        glow.addColorStop(1, `${p.color}00`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(x, y, glowR, 0, Math.PI * 2);
        ctx.fill();

        // Star core
        ctx.globalAlpha = dim ? 0.35 : 1;
        ctx.fillStyle = on || isHovered ? "#ffffff" : p.color;
        ctx.beginPath();
        ctx.arc(x, y, baseR, 0, Math.PI * 2);
        ctx.fill();

        // Inner color ring if hovered/selected
        if (on || isHovered || isSelected) {
          ctx.strokeStyle = p.color;
          ctx.lineWidth = 1.8;
          ctx.beginPath();
          ctx.arc(x, y, baseR + 2, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Ring for user's own promises
        if (p.node.owner_is_user) {
          ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(x, y, baseR + 4, 0, Math.PI * 2);
          ctx.stroke();
        }

        ctx.globalAlpha = 1;
      }

      ctx.restore();
      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [layout, matched, size, hoveredNode, selectedNode, graph.edges]);

  // Convert screen coordinates to world coordinates
  const screenToWorld = (sx: number, sy: number) => {
    const z = zoomRef.current;
    const px = panRef.current.x;
    const py = panRef.current.y;
    return {
      x: (sx - (size.w / 2 + px)) / z,
      y: (sy - (size.h / 2 + py)) / z,
    };
  };

  // Drag pan
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    isDraggingRef.current = true;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    panStartRef.current = { ...targetPanRef.current };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDraggingRef.current) {
      const dx = e.clientX - dragStartRef.current.x;
      const dy = e.clientY - dragStartRef.current.y;
      targetPanRef.current = {
        x: panStartRef.current.x + dx,
        y: panStartRef.current.y + dy,
      };
      return;
    }

    // Hit test for hovered node
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const world = screenToWorld(sx, sy);
    const z = zoomRef.current;

    const hit = layout.placed.find((p) => {
      const d2 = (p.x - world.x) ** 2 + (p.y - world.y) ** 2;
      return d2 < (14 / z) ** 2;
    });

    if (hit) {
      setHoveredNode({ node: hit.node, screenX: sx, screenY: sy });
    } else {
      setHoveredNode(null);
    }
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    const wasDrag =
      Math.abs(e.clientX - dragStartRef.current.x) > 5 ||
      Math.abs(e.clientY - dragStartRef.current.y) > 5;
    isDraggingRef.current = false;

    if (!wasDrag && hoveredNode) {
      setSelectedNode(hoveredNode.node);
      onSelectNode?.(hoveredNode.node);
    } else if (!wasDrag && !hoveredNode) {
      setSelectedNode(null);
    }
  };

  // Touch handlers for mobile / tablet pinch-to-zoom
  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      initialPinchDistRef.current = dist;
      initialPinchZoomRef.current = targetZoomRef.current;
    } else if (e.touches.length === 1) {
      isDraggingRef.current = true;
      dragStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      panStartRef.current = { ...targetPanRef.current };
    }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (e.touches.length === 2 && initialPinchDistRef.current !== null) {
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const scale = dist / initialPinchDistRef.current;
      targetZoomRef.current = Math.max(0.35, Math.min(2.8, initialPinchZoomRef.current * scale));
    } else if (e.touches.length === 1 && isDraggingRef.current) {
      const dx = e.touches[0].clientX - dragStartRef.current.x;
      const dy = e.touches[0].clientY - dragStartRef.current.y;
      targetPanRef.current = {
        x: panStartRef.current.x + dx,
        y: panStartRef.current.y + dy,
      };
    }
  };

  const handleTouchEnd = () => {
    initialPinchDistRef.current = null;
    isDraggingRef.current = false;
  };

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{ touchAction: "none" }}
      className="relative h-full w-full overflow-hidden select-none cursor-grab active:cursor-grabbing bg-[#050814]"
    >
      {/* 2D Space Canvas */}
      <canvas
        ref={canvasRef}
        role="img"
        aria-label="Memory field"
        className="absolute inset-0 block h-full w-full"
      />

      {/* Center Voice Orb anchored to world origin (0, 0) - transformed via ref in RAF */}
      <div
        ref={orbWrapperRef}
        className="pointer-events-none absolute left-0 top-0 z-20 will-change-transform"
        style={{
          transform: `translate3d(${size.w / 2}px, ${size.h / 2}px, 0) translate(-50%, -50%) scale(1)`,
        }}
      >
        <div className="pointer-events-auto">
          <VoiceOrb
            state={orbState}
            level={audioLevel}
            onClick={onOrbClick}
            label={orbLabel}
          />
        </div>
      </div>

      {/* Floating Canvas Navigation Controls (Zoom / Reset) */}
      <div className="absolute bottom-6 right-6 z-30 flex items-center gap-1.5 rounded-full border border-line bg-surface/80 p-1.5 backdrop-blur-md shadow-lg">
        <button
          onClick={() => {
            targetZoomRef.current = Math.min(2.8, targetZoomRef.current * 1.25);
          }}
          aria-label="Zoom in"
          className="grid h-8 w-8 place-items-center rounded-full text-muted hover:bg-white/10 hover:text-white transition"
          title="Zoom In"
        >
          +
        </button>
        <button
          onClick={() => {
            targetZoomRef.current = Math.max(0.35, targetZoomRef.current * 0.8);
          }}
          aria-label="Zoom out"
          className="grid h-8 w-8 place-items-center rounded-full text-muted hover:bg-white/10 hover:text-white transition"
          title="Zoom Out"
        >
          -
        </button>
        <button
          onClick={() => {
            targetZoomRef.current = 1;
            targetPanRef.current = { x: 0, y: 0 };
          }}
          aria-label="Reset space view"
          className="grid h-8 w-8 place-items-center rounded-full text-xs text-muted hover:bg-white/10 hover:text-white transition"
          title="Recenter Orb"
        >
          ⊙
        </button>
      </div>

      {/* Hovered / Selected Node Celestial HUD Popover */}
      {(hoveredNode || selectedNode) && (
        <NodeTooltipCard
          node={(hoveredNode?.node ?? selectedNode)!}
          screenX={hoveredNode?.screenX ?? size.w / 2}
          screenY={hoveredNode?.screenY ?? size.h / 2}
          onInspectTranscript={onInspectTranscript}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}

function NodeTooltipCard({
  node,
  screenX,
  screenY,
  onInspectTranscript,
  onClose,
}: {
  node: MemoryNode;
  screenX: number;
  screenY: number;
  onInspectTranscript?: (convId: string, memId?: string) => void;
  onClose?: () => void;
}) {
  return (
    <div
      className="pointer-events-auto absolute z-30 w-72 -translate-x-1/2 -translate-y-full rounded-xl border border-line bg-surface-solid/95 p-3.5 backdrop-blur-xl shadow-2xl transition animate-in fade-in zoom-in-95"
      style={{
        left: `${Math.max(160, Math.min(window.innerWidth - 160, screenX))}px`,
        top: `${Math.max(120, screenY - 14)}px`,
      }}
    >
      <div className="flex items-center justify-between gap-2 border-b border-line pb-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-accent-2">
          {node.kind}
        </span>
        <div className="flex items-center gap-1.5">
          {node.decision_state && (
            <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] uppercase font-medium text-white">
              {node.decision_state}
            </span>
          )}
          {onClose && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className="text-muted hover:text-white text-xs px-1"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <p className="mt-2 text-xs font-medium text-white leading-relaxed line-clamp-3">
        {node.statement}
      </p>

      {node.topic && (
        <p className="mt-2 text-[11px] text-muted border-l border-accent/40 pl-2">
          Topic: {node.topic}
        </p>
      )}

      <div className="mt-2 flex items-center justify-between text-[10px] text-muted">
        <span>{node.speaker ? `Said by ${node.speaker}` : "System extract"}</span>
        <span>{node.conversation_title}</span>
      </div>

      {onInspectTranscript && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onInspectTranscript(node.conversation_id, node.id);
          }}
          className="mt-2.5 w-full rounded-lg bg-accent/20 hover:bg-accent/30 py-1.5 text-center text-xs font-semibold text-accent transition"
        >
          View in Transcript →
        </button>
      )}
    </div>
  );
}
