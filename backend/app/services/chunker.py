"""Sentence-window chunker with exact offsets.

Carries over the original Recall idea (2-4 sentences, 1 sentence overlap, roughly
"one decision or statement" per chunk) and adds offsets back into the original
transcript plus the labeled speakers in each chunk.
"""

import re
from dataclasses import dataclass

from app.services.transcript_parser import Segment

_SENTENCE = re.compile(r"[^.!?]+(?:[.!?]+|$)")
_WS = re.compile(r"\s+")
MAX_CHUNK_CHARS = 800  # stop growing a window past this; one sentence may still exceed it
MAX_PIECE_CHARS = 1000  # sentences longer than this are split on word boundaries


@dataclass(frozen=True)
class ChunkDraft:
    seq: int
    text: str
    char_start: int
    char_end: int
    speakers: list[str]


@dataclass(frozen=True)
class _Sentence:
    start: int
    end: int
    speaker: str | None
    turn_start: bool = False  # first sentence of a labeled speaker turn


def _split_long(text: str, start: int, speaker: str | None) -> list[_Sentence]:
    pieces: list[_Sentence] = []
    pos = 0
    while pos < len(text):
        end = min(pos + MAX_PIECE_CHARS, len(text))
        if end < len(text):
            space = text.rfind(" ", pos, end)
            if space > pos:
                end = space
        piece = text[pos:end]
        lead = len(piece) - len(piece.lstrip())
        trail = len(piece.rstrip())
        if piece.strip():
            pieces.append(_Sentence(start + pos + lead, start + pos + trail, speaker))
        pos = end
    return pieces


def _sentences(segments: list[Segment]) -> list[_Sentence]:
    out: list[_Sentence] = []
    for seg in segments:
        first = True
        for m in _SENTENCE.finditer(seg.text):
            raw = m.group(0)
            if not raw.strip():
                continue
            lead = len(raw) - len(raw.lstrip())
            body = raw.strip()
            abs_start = seg.char_start + m.start() + lead
            if len(body) > MAX_PIECE_CHARS:
                out.extend(_split_long(body, abs_start, seg.speaker))
            else:
                out.append(
                    _Sentence(abs_start, abs_start + len(body), seg.speaker, first and bool(seg.speaker))
                )
            first = False
    return out


def _label_start(original: str, sentence: _Sentence) -> int:
    """Start offset of the "Name:" label preceding a turn's first sentence, if it's on the same line."""
    if not sentence.turn_start or not sentence.speaker:
        return sentence.start
    line_start = original.rfind("\n", 0, sentence.start) + 1
    prefix = original[line_start : sentence.start]
    if prefix.strip().lower() == f"{sentence.speaker.lower()}:":
        return line_start + len(prefix) - len(prefix.lstrip())
    return sentence.start


def build_chunks(
    segments: list[Segment],
    original: str,
    min_sentences: int = 2,
    max_sentences: int = 4,
    overlap: int = 1,
) -> list[ChunkDraft]:
    """`original` is the full transcript the segments' offsets point into."""
    sentences = _sentences(segments)
    if not sentences:
        return []

    chunks: list[ChunkDraft] = []
    i = 0
    while i < len(sentences):
        window = [sentences[i]]
        j = i + 1
        while j < len(sentences) and len(window) < max_sentences:
            if sentences[j].end - window[0].start > MAX_CHUNK_CHARS and len(window) >= min_sentences:
                break
            if sentences[j].end - window[0].start > MAX_PIECE_CHARS + 200:
                break
            window.append(sentences[j])
            j += 1
        # Keep the speaker label when a chunk starts a turn, so the excerpt says who spoke.
        start, end = _label_start(original, window[0]), window[-1].end
        speakers = list(dict.fromkeys(s.speaker for s in window if s.speaker))
        text = _WS.sub(" ", original[start:end]).strip()
        chunks.append(ChunkDraft(len(chunks), text, start, end, speakers))
        if j >= len(sentences):
            break
        i = max(i + 1, j - overlap)
    return chunks
