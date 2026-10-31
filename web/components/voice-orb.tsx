"use client";

export type OrbState =
  | "idle"
  | "connecting"
  | "ringing"
  | "listening"
  | "searching"
  | "saving"
  | "saved"
  | "found"
  | "no-memory"
  | "ended"
  | "error";

// [core colour, rim colour, label colour]
const PALETTE: Record<OrbState, [string, string, string]> = {
  idle: ["#f2c94c", "#b48d22", "#17150f"],
  connecting: ["#d8d2c2", "#6f6b60", "#17150f"],
  ringing: ["#d8d2c2", "#6f6b60", "#17150f"],
  listening: ["#86c79a", "#3f6f4d", "#0f1a12"],
  searching: ["#f2c94c", "#b48d22", "#17150f"],
  saving: ["#f2c94c", "#b48d22", "#17150f"],
  saved: ["#a6d8b4", "#4b7f5a", "#0f1a12"],
  found: ["#a6d8b4", "#4b7f5a", "#0f1a12"],
  "no-memory": ["#93a7c4", "#45526a", "#10141b"],
  ended: ["#4a4842", "#2b2a26", "#c9c6bf"],
  error: ["#e07a6e", "#7a3229", "#1d0d0a"],
};

const LABEL: Record<OrbState, string> = {
  idle: "Ready",
  connecting: "Connecting…",
  ringing: "Ringing…",
  listening: "Listening",
  searching: "Searching memories…",
  saving: "Saving to memory…",
  saved: "Saved",
  found: "Found it",
  "no-memory": "No reliable memory",
  ended: "Call ended",
  error: "Error",
};

/**
 * The voice orb. Its size follows the agent's real audio level (SDK "volume-level"),
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
  const [core, rim, text] = PALETTE[state];
  const live = state === "listening" || state === "searching" || state === "saving" || state === "saved" || state === "found" || state === "no-memory";
  const scale = 1 + (live ? Math.min(level, 1) * 0.22 : 0);
  const spinning = state === "connecting" || state === "ringing" || state === "searching" || state === "saving";
  return (
    <div className="flex flex-col items-center gap-3">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        className="group relative grid h-36 w-36 place-items-center rounded-full outline-none focus-visible:ring-4 focus-visible:ring-accent/40 disabled:cursor-not-allowed"
      >
        {/* audio halo */}
        <span
          className="absolute inset-0 rounded-full transition-transform duration-100"
          style={{
            transform: `scale(${scale + 0.12})`,
            background: `radial-gradient(circle, ${core}33 0%, ${core}00 70%)`,
          }}
        />
        <span
          className="absolute inset-3 rounded-full group-hover:[scale:1.05] group-disabled:[scale:1]"
          style={{
            transition: "transform 100ms linear, scale 300ms cubic-bezier(0.2, 0.7, 0.2, 1)",
            transform: `scale(${scale})`,
            background: `radial-gradient(circle at 38% 32%, ${core} 0%, ${core} 38%, ${rim} 100%)`,
            boxShadow: `0 0 0 1px ${rim}, 0 18px 50px -12px ${core}66`,
            animation: state === "idle" ? "orb-breathe 4s ease-in-out infinite" : undefined,
          }}
        />
        {spinning && (
          <span
            className="absolute inset-0 rounded-full"
            style={{
              background: `conic-gradient(from 0deg, transparent 0deg, ${core} 70deg, transparent 150deg)`,
              mask: "radial-gradient(circle, transparent 66%, #000 67.5%, #000 69%, transparent 70.5%)",
              WebkitMask: "radial-gradient(circle, transparent 66%, #000 67.5%, #000 69%, transparent 70.5%)",
              animation: "orb-spin 1.2s linear infinite",
            }}
          />
        )}
        <span className="relative font-display text-[13px] font-semibold" style={{ color: text }}>
          {state === "idle" || state === "ended" || state === "error" ? label : ""}
        </span>
      </button>
      <span
        key={state}
        data-testid="orb-state"
        className="rise-in font-mono text-[11px] uppercase tracking-[0.2em] text-muted"
      >
        {LABEL[state]}
      </span>
      <style>{`
        @keyframes orb-breathe { 0%,100% { transform: scale(0.97); } 50% { transform: scale(1.03); } }
        @keyframes orb-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
