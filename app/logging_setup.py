"""Logging setup with secret redaction.

Security requirement (spec §23): API keys / bot tokens must never reach logs.
A logging Filter masks any occurrence of the actual secret values and any
token-shaped bearer strings.
"""
from __future__ import annotations

import logging
import re


class SecretRedactFilter(logging.Filter):
    """Redact configured secret values and generic secret patterns from records."""

    TOKEN_PATTERN = re.compile(
        r"(?P<prefix>\b(?:token|key|authorization|bearer|apikey)\b\s*[:=]\s*)(?P<value>\S+)",
        re.IGNORECASE,
    )

    def __init__(self, secrets: list[str]):
        super().__init__()
        # Longest first so overlapping values are fully masked.
        self._secrets = sorted({s for s in secrets if s and len(s) >= 6}, key=len, reverse=True)

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "***REDACTED***")
        text = self.TOKEN_PATTERN.sub(lambda m: f"{m.group('prefix')}***REDACTED***", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = self._redact(str(record.msg))
            if record.args:
                record.args = tuple(
                    self._redact(str(a)) if isinstance(a, str) else a for a in record.args
                )
        except Exception:  # never break logging
            pass
        return True


def setup_logging(secrets: list[str] | None = None) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    if secrets:
        handler.addFilter(SecretRedactFilter(secrets))
    root.handlers.clear()
    root.addHandler(handler)
    # Quiet noisy libraries.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
