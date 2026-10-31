/** Recall's mark: three transcript lines on a highlighter block, the middle one picked out. */
export function LogoMark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden className="shrink-0">
      <rect width="24" height="24" rx="6" fill="var(--accent)" />
      <path d="M6.5 7.5h11" stroke="var(--on-accent)" strokeOpacity="0.45" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M6.5 12h7.5" stroke="var(--on-accent)" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M6.5 16.5h9" stroke="var(--on-accent)" strokeOpacity="0.45" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-display font-semibold tracking-tight text-ink ${className}`}>
      <LogoMark size={size} />
      <span>Recall</span>
    </span>
  );
}
