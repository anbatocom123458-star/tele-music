"""OpenAI-compatible chat completion client.

Security (spec §14/§23):
- The AI NEVER decides credit, authorization, redeem, or identity. Handlers
  ask the backend; this client only transforms prompts into JSON scenes.
- API key stays in headers; never logged. Response is size- and time-limited.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import Config

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class AIServiceError(RuntimeError):
    """AI request failed (network/timeout/bad payload). Handler shows a friendly message."""


class AIClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._client = httpx.AsyncClient(
            base_url=cfg.ai_base_url,
            headers={
                "Authorization": f"Bearer {cfg.ai_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(cfg.limits.ai_timeout_seconds, connect=10.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def chat_json(self, system: str, user: str) -> dict:
        """POST /chat/completions and parse the reply as JSON."""
        payload = {
            "model": self.cfg.ai_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
            "max_tokens": self.cfg.limits.ai_max_tokens,
            # Best-effort strict mode; providers that ignore it still work
            # because we parse + validate the content ourselves.
            "response_format": {"type": "json_object"},
        }
        try:
            resp = await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("AI timeout: %s", exc)
            raise AIServiceError("AI API timeout") from exc
        except httpx.HTTPError as exc:
            logger.warning("AI request failed: %s", exc)
            raise AIServiceError("AI API unreachable") from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise AIServiceError("AI API auth failed (check AI_API_KEY)")
        if resp.status_code == 429:
            raise AIServiceError("AI API rate limited")
        if resp.status_code >= 400:
            logger.warning("AI API error status=%s body=%s", resp.status_code, resp.text[:300])
            raise AIServiceError(f"AI API error status={resp.status_code}")

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unexpected AI payload: %s", str(data)[:300])
            raise AIServiceError("AI API malformed response") from exc

        return self._parse_json(content)

    @staticmethod
    def _parse_json(content: str) -> dict:
        if not isinstance(content, str) or not content.strip():
            raise AIServiceError("AI returned empty content")
        text = _FENCE.sub("", content.strip())
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # salvage the outermost JSON object
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end <= start:
                raise AIServiceError("AI response is not JSON")
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise AIServiceError("AI response JSON unparseable") from exc
        if not isinstance(data, dict):
            raise AIServiceError("AI JSON root must be an object")
        return data
