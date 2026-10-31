"use client";

import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from "react";

/** Arms the scroll-reveal CSS once React is running; mounted once in the root layout. */
export function MotionReady() {
  useEffect(() => {
    document.documentElement.classList.add("motion-ready");
  }, []);
  return null;
}

/** True once the element has scrolled into view (stays true). */
export function useInView<T extends Element>(threshold = 0.2) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);
  // Already on screen at mount: show it straight away rather than hiding it for a frame.
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && el.getBoundingClientRect().top < window.innerHeight * 0.92) setInView(true);
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el || inView) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold, inView]);
  return { ref, inView };
}

/**
 * Fades/slides its children in the first time they scroll into view, and flips on `.in` so
 * descendants can run their own reveal effects (.sweep-on-reveal, .strike, .pop-on-reveal, .draw-down).
 */
export function Reveal({
  children,
  delay = 0,
  as: Tag = "div",
  className = "",
  style,
}: {
  children: ReactNode;
  delay?: number;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
}) {
  const { ref, inView } = useInView<HTMLElement>();
  return (
    <Tag
      ref={ref}
      className={`reveal ${inView ? "in" : ""} ${className}`}
      style={{ "--delay": `${delay}ms`, ...style } as CSSProperties}
    >
      {children}
    </Tag>
  );
}

/** Counts from 0 to `to` once visible. */
export function CountUp({ to, decimals = 0, duration = 1100 }: { to: number; decimals?: number; duration?: number }) {
  const { ref, inView } = useInView<HTMLSpanElement>(0.6);
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!inView) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setValue(to);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / duration);
      setValue(to * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, duration]);
  return (
    <span ref={ref} className="tabular-nums">
      {value.toFixed(decimals)}
    </span>
  );
}
