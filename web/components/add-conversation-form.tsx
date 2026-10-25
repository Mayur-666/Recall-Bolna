"use client";

import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";

import { ApiError, apiFetch, useApi } from "@/lib/api";
import type { Conversation, User } from "@/lib/types";

const MAX_BYTES = 1_000_000;
const ACCEPT = ".txt,.md,.vtt,.srt";

export function AddConversationForm({ onCreated, onCancel }: { onCreated: (c: Conversation) => void; onCancel: () => void }) {
  const { data: me } = useApi<User>("/api/v1/auth/me");
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [participants, setParticipants] = useState("");
  const [selfSpeaker, setSelfSpeaker] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [existingId, setExistingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const names = useMemo(
    () => Array.from(new Set(participants.split(",").map((p) => p.trim()).filter(Boolean))),
    [participants],
  );
  // Pre-select only on an exact match with the signed-in user's name; never guess otherwise.
  const autoSelf = me && names.includes(me.display_name) ? me.display_name : "";
  const self = selfSpeaker ?? autoSelf;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setExistingId(null);
    if (!file && !text.trim()) return setError("Paste a transcript or choose a file.");
    if (file && file.size > MAX_BYTES) return setError("That file is larger than 1 MB.");
    const form = new FormData();
    form.set("title", title);
    form.set("conversation_date", date);
    if (names.length) form.set("participants", names.join(", "));
    if (self && names.includes(self)) form.set("self_speaker", self);
    if (file) form.set("file", file);
    else form.set("text", text);
    setBusy(true);
    try {
      onCreated(await apiFetch<Conversation>("/api/v1/conversations", { method: "POST", body: form }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Already added: this transcript is already in your library.");
        setExistingId((err.details?.existing_id as string) ?? null);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Could not save the conversation.");
      }
    } finally {
      setBusy(false);
    }
  }

  const input = "mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft";
  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-surface p-5 shadow-sm">
      <div className="grid gap-4 md:grid-cols-3">
        <label className="block text-sm font-medium md:col-span-2">
          Title
          <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} className={input} />
        </label>
        <label className="block text-sm font-medium">
          Date
          <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className={input} />
        </label>
        <label className="block text-sm font-medium md:col-span-2">
          Participants
          <input placeholder="Priya, Arjun, Mayur" value={participants} onChange={(e) => setParticipants(e.target.value)} className={input} />
        </label>
        <label className="block text-sm font-medium">
          Which participant is you?
          <select value={self} onChange={(e) => setSelfSpeaker(e.target.value)} className={input}>
            <option value="">None / not me</option>
            {names.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="block text-sm font-medium">
        Transcript
        <textarea
          rows={8}
          value={text}
          disabled={Boolean(file)}
          onChange={(e) => setText(e.target.value)}
          placeholder={"Priya: We should use WebSockets for live updates.\nMayur: Agreed, let's go with that."}
          className={`${input} font-mono`}
        />
      </label>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="text-muted">
          Or upload a file ({ACCEPT}, up to 1 MB):{" "}
          <input type="file" accept={ACCEPT} aria-label="Upload file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <span className="text-xs text-muted">Label lines like “Name: …” to record who spoke. Unlabeled text is never attributed.</span>
      </div>
      {error && (
        <div role="alert" className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {error}{" "}
          {existingId && (
            <Link href={`/conversations/${existingId}`} className="font-medium underline">
              Open the existing conversation
            </Link>
          )}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm text-muted hover:text-ink">
          Cancel
        </button>
        <button type="submit" disabled={busy} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-60">
          {busy ? "Saving…" : "Save conversation"}
        </button>
      </div>
    </form>
  );
}
