from app.services.transcript_parser import parse_transcript


def _check_offsets(original, segments):
    for seg in segments:
        assert original[seg.char_start : seg.char_end] == seg.text


def test_labeled_lines_get_speakers():
    text = "Priya: We should use WebSockets.\nMayur: Agreed."
    segs = parse_transcript(text, None)
    assert [s.speaker for s in segs] == ["Priya", "Mayur"]
    assert [s.text for s in segs] == ["We should use WebSockets.", "Agreed."]
    _check_offsets(text, segs)


def test_unlabeled_text_speaker_none():
    text = "We talked about the launch.\nNothing was decided."
    segs = parse_transcript(text, None)
    assert all(s.speaker is None for s in segs)
    _check_offsets(text, segs)


def test_non_speaker_colons_not_speakers():
    text = "Note: deploy Friday\nTODO: write docs\nsee https://a.b for details\nAction Items: none"
    segs = parse_transcript(text, None)
    assert all(s.speaker is None for s in segs)
    assert segs[0].text == "Note: deploy Friday"  # label text kept as content
    _check_offsets(text, segs)


def test_participants_restrict_speakers():
    text = "Priya: hi.\nRandom Thing: not a person."
    segs = parse_transcript(text, None, participants=["Priya", "Mayur"])
    assert segs[0].speaker == "Priya"
    assert segs[1].speaker is None
    assert segs[1].text == "Random Thing: not a person."


def test_participant_match_is_case_insensitive_and_canonical():
    segs = parse_transcript("priya: hello.", None, participants=["Priya"])
    assert segs[0].speaker == "Priya"


def test_continuation_line_keeps_speaker_until_blank_line():
    text = "Priya: First line.\nstill Priya here.\n\nunlabeled after blank."
    segs = parse_transcript(text, None)
    assert [s.speaker for s in segs] == ["Priya", "Priya", None]
    _check_offsets(text, segs)


def test_vtt_voice_tags_and_timestamps_stripped():
    text = (
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\n<v Priya>Use WebSockets.</v>\n\n"
        "00:00:04.000 --> 00:00:05.000\n<v Mayur>Agreed.\n"
    )
    segs = parse_transcript(text, "call.vtt")
    assert [(s.speaker, s.text) for s in segs] == [("Priya", "Use WebSockets."), ("Mayur", "Agreed.")]
    _check_offsets(text, segs)


def test_srt_parsed():
    text = (
        "1\n00:00:01,000 --> 00:00:03,000\nPriya: Use WebSockets.\n\n"
        "2\n00:00:04,000 --> 00:00:05,000\nOK then.\n"
    )
    segs = parse_transcript(text, "call.srt")
    assert [(s.speaker, s.text) for s in segs] == [("Priya", "Use WebSockets."), (None, "OK then.")]
    _check_offsets(text, segs)


def test_crlf_offsets():
    text = "Priya: One.\r\nMayur: Two.\r\n"
    segs = parse_transcript(text, None)
    assert [s.text for s in segs] == ["One.", "Two."]
    _check_offsets(text, segs)
