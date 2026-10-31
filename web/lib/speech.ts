"use client";

// Reads typed-question answers aloud. Preferred: the server voice via /api/v1/tts — the local Kokoro
// model (voice af_heart), or the agent's Cartesia voice if configured. Fallback: the browser's speech.

type Handlers = { onStart?: () => void; onEnd?: () => void; onLevel?: (l: number) => void };

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
  return typeof window !== "undefined" && ("speechSynthesis" in window || typeof Audio !== "undefined");
}

let generation = 0;
let audio: HTMLAudioElement | null = null;
let audioCtx: AudioContext | null = null;
let raf = 0;
let agentVoice: Promise<boolean> | null = null;

/** Whether the backend can speak in the agent's voice (asked once per page load). */
export function agentVoiceAvailable(): Promise<boolean> {
  agentVoice ??= fetch("/api/v1/tts/status", { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : { available: false }))
    .then((j: { available?: boolean }) => Boolean(j.available))
    .catch(() => false);
  return agentVoice;
}

function releaseAudio() {
  cancelAnimationFrame(raf);
  if (audio) {
    audio.pause();
    URL.revokeObjectURL(audio.src);
    audio = null;
  }
  void audioCtx?.close().catch(() => undefined);
  audioCtx = null;
}

export function stopSpeaking(): void {
  generation++;
  releaseAudio();
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}

function speakWithBrowser(text: string, h: Handlers) {
  if (!("speechSynthesis" in window)) return h.onEnd?.();
  const u = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  if (voice) u.voice = voice;
  u.lang = voice?.lang ?? "en-US";
  u.rate = 1.02;
  u.onstart = () => h.onStart?.();
  u.onboundary = () => h.onLevel?.(0.35 + Math.random() * 0.4);
  u.onend = u.onerror = () => {
    h.onLevel?.(0);
    h.onEnd?.();
  };
  window.speechSynthesis.speak(u);
}

async function speakWithAgentVoice(text: string, h: Handlers, gen: number): Promise<boolean> {
  const res = await fetch("/api/v1/tts", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  }).catch(() => null);
  if (!res?.ok || gen !== generation) return gen !== generation; // superseded counts as handled
  const url = URL.createObjectURL(await res.blob());
  if (gen !== generation) {
    URL.revokeObjectURL(url);
    return true;
  }
  const el = new Audio(url);
  audio = el;
  // Real output level for the orb.
  try {
    audioCtx = new AudioContext();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    const src = audioCtx.createMediaElementSource(el);
    src.connect(analyser);
    analyser.connect(audioCtx.destination);
    const data = new Uint8Array(analyser.fftSize);
    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += ((data[i] - 128) / 128) ** 2;
      h.onLevel?.(Math.min(1, Math.sqrt(sum / data.length) * 3));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
  } catch {
    // no analyser: still plays, the orb just doesn't pulse
  }
  el.onplay = () => h.onStart?.();
  el.onended = el.onerror = () => {
    releaseAudio();
    h.onLevel?.(0);
    h.onEnd?.();
  };
  try {
    await el.play();
    return true;
  } catch {
    releaseAudio();
    return false; // autoplay blocked etc. -> fall back to the browser voice
  }
}

/** Speak `text` (replacing anything already playing), in the agent's voice when available. */
export async function speak(text: string, handlers: Handlers = {}): Promise<void> {
  if (!canSpeak() || !text.trim()) return;
  stopSpeaking();
  const gen = generation;
  if ((await agentVoiceAvailable()) && gen === generation) {
    if (await speakWithAgentVoice(text, handlers, gen)) return;
  }
  if (gen === generation) speakWithBrowser(text, handlers);
}
