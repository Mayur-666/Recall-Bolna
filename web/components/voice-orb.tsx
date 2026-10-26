"use client";

export type OrbState =
  | "idle"
  | "connecting"
  | "ringing"
  | "listening"
  | "searching"
  | "found"
  | "no-memory"
  | "ended"
  | "error";

const PALETTE: Record<OrbState, [string, string]> = {
  idle: ["#8b7bff", "#3ee6c4"],
  connecting: ["#8b7bff", "#5cd6ff"],
  ringing: ["#8b7bff", "#5cd6ff"],
  listening: ["#3ee6c4", "#8b7bff"],
  searching: ["#5cd6ff", "#b69cff"],
  found: ["#3ee6a0", "#b7fff0"],
  "no-memory": ["#8fa8ff", "#4b5590"],
  ended: ["#5b6182", "#2d3150"],
  error: ["#ff6b9a", "#7a2944"],
};

const LABEL: Record<OrbState, string> = {
  idle: "Ready",
  connecting: "Connecting…",
  ringing: "Ringing…",
  listening: "Listening",
  searching: "Searching memories…",
  found: "Found it",
  "no-memory": "No reliable memory",
  ended: "Call ended",
  error: "Error",
};

/**
 * The voice orb. Its size and glow follow the agent's real audio level (SDK "volume-level"),
 * and its colour follows backend-observed state: listening, searching, found, or honestly not found.
 */
export function VoiceOrb({
  state,
  level,
  onClick,
  disabled,
  label,
}: {
  state: OrbState;
  level: number;
  onClick: () => void;
  disabled?: boolean;
  label: string;
}) {
  const [a, b] = PALETTE[state];
  const live = state === "listening" || state === "searching" || state === "found" || state === "no-memory";
  const scale = 1 + (live ? Math.min(level, 1) * 0.28 : 0);
  const spinning = state === "connecting" || state === "ringing" || state === "searching";
  return (
    <div className="flex flex-col items-center gap-3">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        className="relative grid h-40 w-40 place-items-center rounded-full outline-none focus-visible:ring-4 focus-visible:ring-accent/50 disabled:cursor-not-allowed"
      >
        <span
          className="absolute inset-0 rounded-full transition-transform duration-100"
          style={{
            transform: `scale(${scale})`,
            background: `radial-gradient(circle at 35% 30%, ${b} 0%, ${a} 45%, transparent 72%)`,
            boxShadow: `0 0 ${50 + level * 90}px ${8 + level * 20}px ${a}66`,
            animation: state === "idle" ? "orb-breathe 4s ease-in-out infinite" : undefined,
          }}
        />
        {spinning && (
          <span
            className="absolute -inset-3 rounded-full"
            style={{
              background: `conic-gradient(from 0deg, transparent 0deg, ${b} 60deg, transparent 140deg)`,
              mask: "radial-gradient(circle, transparent 62%, #000 64%)",
              WebkitMask: "radial-gradient(circle, transparent 62%, #000 64%)",
              animation: "orb-spin 1.2s linear infinite",
            }}
          />
        )}
        <span className="relative font-display text-sm font-semibold text-white drop-shadow">
          {state === "idle" || state === "ended" || state === "error" ? label : ""}
        </span>
      </button>
      <span data-testid="orb-state" className="text-xs font-medium uppercase tracking-[0.25em] text-muted">
        {LABEL[state]}
      </span>
      <style>{`
        @keyframes orb-breathe { 0%,100% { transform: scale(0.96); } 50% { transform: scale(1.04); } }
        @keyframes orb-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
