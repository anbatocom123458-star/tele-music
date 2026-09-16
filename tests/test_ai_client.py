"""AIClient: OpenAI-compatible request + robust JSON parsing (spec §14)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.ai.client import AIServiceError, AIClient
from app.config import Config, ChromaConfig, Limits


def make_client(handler) -> AIClient:
    cfg = Config(
        telegram_bot_token="x",
        ai_api_key="sk-test",
        ai_base_url="https://api.example.com/v1",
        ai_model="test-model",
        chroma=ChromaConfig("h", 8000, False, "db", "t", "", ""),
        admin_telegram_id=None,
        redeem_codes={},
        limits=Limits(ai_timeout_seconds=5),
    )
    client = AIClient(cfg)
    client._client = httpx.AsyncClient(
        base_url="https://api.example.com/v1",
        headers={"Authorization": f"Bearer {cfg.ai_api_key}"},
        transport=httpx.MockTransport(handler),
        timeout=5,
    )
    return client


async def test_parses_plain_json():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"width": 512}'}}]})

    ai = make_client(handler)
    assert await ai.chat_json("s", "u") == {"width": 512}
    await ai.close()


async def test_parses_fenced_json():
    content = '```json\n{"a": 1}\n```'
    ai = make_client(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}}]}))
    assert await ai.chat_json("s", "u") == {"a": 1}
    await ai.close()


async def test_salvages_embedded_json():
    content = 'Sure! Here is your scene: {"a": 1} hope that helps'
    ai = make_client(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}}]}))
    assert await ai.chat_json("s", "u") == {"a": 1}
    await ai.close()


async def test_http_error_raises():
    ai = make_client(lambda r: httpx.Response(500, text="oops"))
    with pytest.raises(AIServiceError):
        await ai.chat_json("s", "u")
    await ai.close()


async def test_auth_error_raises():
    ai = make_client(lambda r: httpx.Response(401, text="no"))
    with pytest.raises(AIServiceError):
        await ai.chat_json("s", "u")
    await ai.close()


async def test_malformed_payload_raises():
    ai = make_client(lambda r: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(AIServiceError):
        await ai.chat_json("s", "u")
    await ai.close()
