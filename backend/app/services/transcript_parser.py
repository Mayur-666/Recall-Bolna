"""Split a transcript into speaker segments with exact character offsets.

Speakers are recorded only when the source labels them ("Name: ..." lines, VTT
voice tags). Nothing is inferred from conversational context. Every segment's
text is exactly original[char_start:char_end].
"""

import re
from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class Segment:
    seq: int
    speaker: str | None
    text: str
    char_start: int
    char_end: int


_LABEL = re.compile(r"^([A-Za-z][\w.'-]*(?: [A-Za-z][\w.'-]*){0,2}):[ \t]+(?=\S)")
_CAPITALIZED_LABEL = re.compile(r"^[A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,2}$")
_STOP_WORDS = {
    "note", "notes", "todo", "action", "actions", "decision", "decisions", "summary", "agenda",
    "q", "a", "http", "https", "re", "fyi", "update", "next", "question", "answer", "subject",
    "date", "time", "location", "attendees", "participants", "transcript", "meeting", "topic",
}  # fmt: skip
_TIMESTAMP = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}\s+-->\s+\d{1,2}:\d{2}")
_CUE_NUMBER = re.compile(r"^\s*\d+\s*$")
_VTT_VOICE = re.compile(r"^<v(?:\.[\w.-]+)?\s+([^>]+)>")
_VTT_CLOSE = re.compile(r"</v>\s*$")


def _resolve_label(label: str, participants: list[str] | None) -> str | None:
    if participants:
        for p in participants:
            if p.lower() == label.lower():
                return p
        return None
    if not _CAPITALIZED_LABEL.match(label):
        return None
    if label.split(" ")[0].lower() in _STOP_WORDS:
        return None
    return label


def _lines_with_offsets(text: str) -> list[tuple[str, int]]:
    """Each line without its line terminator, with the line's start offset."""
    out: list[tuple[str, int]] = []
    pos = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        out.append((line, pos))
        pos += len(raw)
    return out


def _strip(line: str, start: int) -> tuple[str, int, int]:
    """Trim whitespace, returning text and its absolute offsets."""
    lead = len(line) - len(line.lstrip())
    stripped = line.strip()
    return stripped, start + lead, start + lead + len(stripped)


def parse_transcript(text: str, filename: str | None, participants: list[str] | None = None) -> list[Segment]:
    ext = PurePath(filename).suffix.lower() if filename else ""
    is_caption = ext in {".vtt", ".srt"} or text.lstrip().startswith("WEBVTT")

    segments: list[Segment] = []
    current_speaker: str | None = None

    for line, line_start in _lines_with_offsets(text):
        content, start, end = _strip(line, line_start)
        if not content:
            current_speaker = None  # a blank line ends a speaker's turn
            continue
        if is_caption and (
            content.startswith("WEBVTT")
            or content.startswith("NOTE")
            or _TIMESTAMP.match(content)
            or _CUE_NUMBER.match(content)
        ):
            continue

        speaker: str | None = None
        if is_caption:
            voice = _VTT_VOICE.match(content)
            if voice:
                speaker = _resolve_label(voice.group(1).strip(), participants) or voice.group(1).strip()
                start += voice.end()
                content = content[voice.end() :]
            close = _VTT_CLOSE.search(content)
            if close:
                content = content[: close.start()]
            content, start, end = _strip(content, start)
            if not content:
                continue

        if speaker is None:
            label = _LABEL.match(content)
            resolved = _resolve_label(label.group(1), participants) if label else None
            if label and resolved:
                speaker = resolved
                start += label.end()
                content = content[label.end() :]
            elif not is_caption and not label:
                # Continuation of a labeled turn in the same block. A line that looks
                # like "Something: ..." but isn't a known speaker never inherits one.
                speaker = current_speaker

        current_speaker = speaker if not is_caption else None
        segments.append(Segment(len(segments), speaker, content, start, end))

    return segments
