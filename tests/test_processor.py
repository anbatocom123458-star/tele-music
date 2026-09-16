"""Voice text normalization tests (spec §9)."""
from __future__ import annotations

import pytest

from app.tts.processor import VoiceTextError, normalize_for_tts, validate_voice_text


def test_collapses_multiple_spaces():
    assert normalize_for_tts("Xin   chào     bạn") == "Xin chào bạn"


def test_trims_and_keeps_punctuation():
    out = normalize_for_tts("   Xin chào bạn!  Hôm nay bạn khỏe không?   ")
    assert out == "Xin chào bạn! Hôm nay bạn khỏe không?"
    assert "!" in out and "?" in out


def test_newlines_become_single_spaces():
    out = normalize_for_tts("Dòng một\n\nDòng hai\n   Dòng ba")
    assert out == "Dòng một Dòng hai Dòng ba"
    assert "\n" not in out


def test_zero_width_and_nbsp_removed():
    out = normalize_for_tts("Xin\u00a0 chào\u200b bạn")
    assert out == "Xin chào bạn"


def test_tabs_collapse():
    assert normalize_for_tts("a\t\tb") == "a b"


def test_validate_rejects_empty_and_long():
    with pytest.raises(VoiceTextError):
        validate_voice_text("   ", max_chars=100)
    with pytest.raises(VoiceTextError):
        validate_voice_text("a" * 101, max_chars=100)
    with pytest.raises(VoiceTextError):
        # only punctuation, no letters
        validate_voice_text("!!! ??? ...", max_chars=100)


def test_validate_returns_normalized():
    assert validate_voice_text("  Xin    chào!  ", max_chars=100) == "Xin chào!"
