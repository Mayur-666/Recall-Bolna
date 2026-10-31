"use client";

// Reads typed-question answers aloud with the browser's own speech synthesis (no audio leaves the machine).

const PREFERRED = [/natural/i, /aria/i, /jenny/i, /guy/i, /google uk english female/i, /google us english/i, /samantha/i];

function pickVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("en"));
  for (const re of PREFERRED) {
    const v = voices.find((x) => re.test(x.name));
    if (v) return v;
  }
  return voices.find((v) => v.default) ?? voices[0] ?? null;
}

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel();
}

/** Speak `text`, replacing anything already being spoken. `onLevel` gets a rough 0..1 level per word. */
export function speak(text: string, handlers: { onStart?: () => void; onEnd?: () => void; onLevel?: (l: number) => void } = {}) {
  if (!canSpeak() || !text.trim()) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  if (voice) u.voice = voice;
  u.lang = voice?.lang ?? "en-US";
  u.rate = 1.02;
  u.onstart = () => handlers.onStart?.();
  u.onboundary = () => handlers.onLevel?.(0.35 + Math.random() * 0.4);
  u.onend = u.onerror = () => {
    handlers.onLevel?.(0);
    handlers.onEnd?.();
  };
  // Some browsers load voices lazily; speaking before they arrive uses the default voice, which is fine.
  synth.speak(u);
}
