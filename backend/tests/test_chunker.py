import re

from app.services.chunker import build_chunks
from app.services.transcript_parser import parse_transcript

TEXT = (
    "Priya: We need live updates. WebSockets are the obvious choice. Polling is wasteful.\n"
    "Mayur: Agreed on WebSockets. Let's go with REST plus WebSockets. I will write the auth spec by Friday.\n"
    "Priya: Great. Ship it."
)


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def test_chunk_offsets_map_to_original():
    chunks = build_chunks(parse_transcript(TEXT, None), TEXT)
    assert chunks
    for c in chunks:
        assert _norm(TEXT[c.char_start : c.char_end]) == c.text


def test_chunk_overlap_one_sentence():
    chunks = build_chunks(parse_transcript(TEXT, None), TEXT)
    assert len(chunks) >= 2
    first_last_sentence = "I will write the auth spec by Friday."
    # 8 sentences, windows of 4 with overlap 1: the 4th sentence starts chunk 2.
    assert chunks[0].text.endswith("Agreed on WebSockets.")
    assert chunks[1].text.startswith("Mayur: Agreed on WebSockets.")
    assert any(first_last_sentence in c.text for c in chunks)


def test_chunk_never_starts_mid_sentence():
    chunks = build_chunks(parse_transcript(TEXT, None), TEXT)
    for c in chunks:
        assert c.text[0].isupper()


def test_chunk_starting_a_turn_keeps_speaker_label():
    chunks = build_chunks(parse_transcript(TEXT, None), TEXT)
    assert chunks[0].text.startswith("Priya: We need live updates.")
    assert TEXT[chunks[0].char_start : chunks[0].char_start + 6] == "Priya:"
    # A chunk starting mid-turn has no label to include.
    assert chunks[1].text.startswith("Mayur: Agreed on WebSockets.")


def test_chunk_speakers_recorded():
    chunks = build_chunks(parse_transcript(TEXT, None), TEXT)
    assert chunks[0].speakers == ["Priya", "Mayur"]
    assert [c.seq for c in chunks] == list(range(len(chunks)))


def test_single_sentence_transcript_one_chunk():
    chunks = build_chunks(parse_transcript("Just one line here.", None), "Just one line here.")
    assert len(chunks) == 1
    assert chunks[0].text == "Just one line here."
    assert chunks[0].speakers == []


def test_very_long_sentence_is_split():
    wall = " ".join(["word"] * 1000)
    chunks = build_chunks(parse_transcript(wall, None), wall)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 1200
        assert _norm(wall[c.char_start : c.char_end]) == c.text
