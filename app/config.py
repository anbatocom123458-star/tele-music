"""Central configuration loaded strictly from environment variables.

Rules:
- No secret is ever hard-coded or defaulted.
- Missing required ENV fails fast at startup with a clear message.
- Values are never logged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse


class ConfigError(RuntimeError):
    """Raised when required environment variables are missing/invalid."""


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ConfigError(f"Thiếu biến môi trường bắt buộc: {name}.")
    return value


def _optional(name: str, default: str = "") -> str:
    return (os.getenv(name) or "").strip() or default


def _optional_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Biến {name} phải là số nguyên (nhận được: {raw!r}).") from exc


def _optional_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"Biến {name} phải là số thực (nhận được: {raw!r}).") from exc


@dataclass(frozen=True)
class ChromaConfig:
    host: str
    port: int
    ssl: bool
    database: str
    tenant: str
    apikey: str
    secret: str

    @property
    def has_auth(self) -> bool:
        return bool(self.apikey or self.secret)


@dataclass(frozen=True)
class Limits:
    max_voice_chars: int = 1200
    min_voice_chars: int = 2
    max_svg_prompt_chars: int = 800
    max_tts_seconds: int = 120
    tts_timeout_seconds: int = 90
    ffmpeg_timeout_seconds: int = 30
    ai_timeout_seconds: int = 90
    ai_max_tokens: int = 2500
    svg_preview_timeout_seconds: int = 30
    max_global_jobs: int = 2
    max_jobs_per_user: int = 1
    command_cooldown_seconds: float = 2.0
    max_svg_elements: int = 120
    max_svg_bytes: int = 512_000
    max_message_bytes: int = 8_000


@dataclass
class Config:
    telegram_bot_token: str
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    chroma: ChromaConfig
    admin_telegram_id: int | None
    redeem_codes: dict[str, str] = field(default_factory=dict)  # label -> plaintext
    model_dir: str = "/data/models"
    tmp_voice_dir: str = "/tmp/voice"
    tmp_svg_dir: str = "/tmp/svg"
    port: int = 8080
    initial_credit: float = 100.0
    limits: Limits = field(default_factory=Limits)

    def consume_redeem_codes(self) -> dict[str, str]:
        """Return redeem codes once so plaintext does not linger in memory."""
        codes = dict(self.redeem_codes)
        self.redeem_codes = {}
        return codes


def load_config() -> Config:
    """Build Config from ENV. Raises ConfigError listing every missing variable."""
    missing = [
        name
        for name in (
            "TELEGRAM_BOT_TOKEN", "AI_API_KEY", "AI_BASE_URL",
            "AI_MODEL", "CHROMA_URL",
        )
        if not (os.getenv(name) or "").strip()
    ]
    if missing:
        raise ConfigError(
            "Thiếu biến môi trường bắt buộc: " + ", ".join(missing)
        )

    chroma_url = (os.getenv("CHROMA_URL") or "").strip()
    parsed = urlparse(chroma_url if "://" in chroma_url else f"http://{chroma_url}")
    if not parsed.hostname:
        raise ConfigError("CHROMA_URL không hợp lệ (không đọc được host).")
    ssl = parsed.scheme == "https"
    port = parsed.port or (443 if ssl else 80)
    path_db = parsed.path.strip("/").split("/")[0] if parsed.path.strip("/") else ""

    admin_raw = (os.getenv("ADMIN_TELEGRAM_ID") or "").strip()
    admin_id: int | None = None
    if admin_raw:
        try:
            admin_id = int(admin_raw)
        except ValueError as exc:
            raise ConfigError("ADMIN_TELEGRAM_ID phải là Telegram UID (số).") from exc

    redeem_codes: dict[str, str] = {}
    for i in range(1, 9):
        code = (os.getenv(f"REDEEM_CODE_{i}") or "").strip()
        if code:
            redeem_codes[f"RC{i}"] = code
    for i, code in enumerate((os.getenv("REDEEM_CODES") or "").split(","), start=1):
        code = code.strip()
        if code:
            redeem_codes[f"RCL{i}"] = code
    if not redeem_codes:
        raise ConfigError(
            "Chưa có mã redeem nào. Khai báo REDEEM_CODE_1..REDEEM_CODE_8 trong ENV."
        )

    return Config(
        telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
        ai_api_key=_required("AI_API_KEY"),
        ai_base_url=_required("AI_BASE_URL").rstrip("/"),
        ai_model=_required("AI_MODEL"),
        chroma=ChromaConfig(
            host=parsed.hostname,
            port=port,
            ssl=ssl,
            database=_optional("CHROMA_DATABASE", path_db or "default_database"),
            tenant=_optional("CHROMA_TENANT", "default_tenant"),
            apikey=(os.getenv("CHROMA_APIKEY") or "").strip(),
            secret=(os.getenv("CHROMA_SECRET") or "").strip(),
        ),
        admin_telegram_id=admin_id,
        redeem_codes=redeem_codes,
        model_dir=_optional("MODEL_DIR", "/data/models"),
        tmp_voice_dir=_optional("TMP_VOICE_DIR", "/tmp/voice"),
        tmp_svg_dir=_optional("TMP_SVG_DIR", "/tmp/svg"),
        port=_optional_int("PORT", 8080),
        initial_credit=_optional_float("INITIAL_CREDIT", 100.0),
        limits=Limits(
            max_voice_chars=_optional_int("MAX_VOICE_CHARS", 1200),
            max_svg_prompt_chars=_optional_int("MAX_SVG_PROMPT_CHARS", 800),
            max_global_jobs=_optional_int("MAX_GLOBAL_JOBS", 2),
            max_jobs_per_user=_optional_int("MAX_JOBS_PER_USER", 1),
            ai_timeout_seconds=_optional_int("AI_TIMEOUT_SECONDS", 90),
            tts_timeout_seconds=_optional_int("TTS_TIMEOUT_SECONDS", 90),
            ai_max_tokens=_optional_int("AI_MAX_TOKENS", 2500),
        ),
    )

