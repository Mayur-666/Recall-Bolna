"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Minimal typing for the Web Speech API (not in TypeScript's DOM lib).
interface RecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface RecognitionEvent {
  resultIndex: number;
  results: ArrayLike<RecognitionResult>;
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

function recognitionCtor(): (new () => Recognition) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Microphone access is blocked for this site. Allow it in the address bar and try again.",
  "service-not-allowed": "Speech recognition isn't allowed in this browser.",
  "no-speech": "Didn't catch anything — tap the mic and try again.",
  "audio-capture": "No microphone was found.",
  network: "Speech recognition needs a network connection.",
};

/**
 * Dictation for the ask box via the browser's speech recognition (Chrome/Edge; it runs on the browser
 * vendor's speech service). Interim words stream into the box; the final phrase is handed to `onFinal`.
 */
export function useDictation({ onInterim, onFinal }: { onInterim: (t: string) => void; onFinal: (t: string) => void }) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const cb = useRef({ onInterim, onFinal });
  cb.current = { onInterim, onFinal };

  useEffect(() => {
    setSupported(recognitionCtor() !== null);
    return () => rec.current?.abort();
  }, []);

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    rec.current?.abort();
    const r = new Ctor();
    r.lang = navigator.language || "en-US";
    r.interimResults = true;
    r.continuous = false;
    let finalText = "";
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText += res[0].transcript;
        else interim += res[0].transcript;
      }
      cb.current.onInterim((finalText + interim).trim());
    };
    r.onerror = (e) => {
      if (e.error !== "aborted") setError(ERRORS[e.error] ?? `Speech recognition failed (${e.error}).`);
    };
    r.onend = () => {
      setListening(false);
      rec.current = null;
      if (finalText.trim()) cb.current.onFinal(finalText.trim());
    };
    setError(null);
    setListening(true);
    rec.current = r;
    try {
      r.start();
    } catch {
      setListening(false);
    }
  }, []);

  const stop = useCallback(() => rec.current?.stop(), []);

  return { supported, listening, error, start, stop };
}
