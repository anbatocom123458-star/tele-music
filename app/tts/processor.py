"""Text normalization before TTS (spec §9).

Goals:
- Multiple spaces / tabs / NBSP collapse to ONE space; leading/trailing
  whitespace removed -> Piper never "reads" stray whitespace.
- Punctuation (! ? . , …) is preserved so prosody stays natural.
- Newlines collapse to a single space (Piper/espeak has no paragraph prosody).
- Control characters and zero-width characters are stripped.
"""
from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE = re.compile(r"[^\S\n]+")
_NEWLINES = re.compile(r"\s*\n+\s*")
_SPACES = re.compile(r" {2,}")


class VoiceTextError(ValueError):
    """User text cannot be used for TTS (empty / too long / no letters)."""


def normalize_for_tts(text: str) -> str:
    if not text:
        return ""
    # Normalize unicode, kill soft hyphens / zero-width chars.
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00ad", "").replace("\r\n", "\n").replace("\r", "\n")
    text = _ZERO_WIDTH.sub("", text)
    text = _CONTROL.sub("", text)
    # Non-breaking & other odd spaces -> normal space.
    text = text.replace("\u00a0", " ").replace("\u2007", " ").replace("\u202f", " ")
    # Collapse horizontal whitespace runs to one space (keeps newlines first).
    text = _MULTI_SPACE.sub(" ", text)
    # Newlines become single spaces — no phantom pauses, no read-out blanks.
    text = _NEWLINES.sub(" ", text)
    # Collapse any remaining duplicate spaces and trim.
    text = _SPACES.sub(" ").strip() if False else _SPACES.sub(" ", text).strip()
    return text


def validate_voice_text(text: str, max_chars: int, min_chars: int = 2) -> str:
    normalized = normalize_for_tts(text)
    if len(normalized) < min_chars:
        raise VoiceTextError("Văn bản quá ngắn. Hãy gửi đoạn văn dài hơn.")
    if len(normalized) > max_chars:
        raise VoiceTextError(
            f"Văn bản quá dài ({len(normalized)} ký tự). "
            f"Tối đa {max_chars} ký tự mỗi lần tạo."
        )
    if not any(unicodedata.category(ch).startswith("L") for ch in normalized):
        raise VoiceTextError("Văn bản phải chứa chữ hoặc từ, không chỉ dấu cách/ký tự đặc biệt.")
    return normalized
