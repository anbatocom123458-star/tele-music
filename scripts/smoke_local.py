"""Local smoke test: real Piper TTS + FFmpeg + SVG render (no Telegram needed).

Run: .venv/bin/python scripts/smoke_local.py
Downloads ONLY the smallest Vietnamese model (vi_VN-vivos-x_low, ~28MB).
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ChromaConfig, Config, Limits  # noqa: E402
from app.svg.generator import validate_scene  # noqa: E402
from app.svg.renderer import render_png, render_scene_svg  # noqa: E402
from app.svg.sanitizer import sanitize_svg  # noqa: E402
from app.tts.engine import TTSEngine, wav_to_ogg_opus  # noqa: E402
from app.tts.processor import normalize_for_tts  # noqa: E402
from app.tts.voices import VOICES  # noqa: E402

MODEL_DIR = Path("/tmp/wioos_smoke/models")
TMP = Path("/tmp/wioos_smoke/tmp")


def make_cfg() -> Config:
    return Config(
        telegram_bot_token="x",
        ai_api_key="x",
        ai_base_url="https://api.example.com/v1",
        ai_model="x",
        chroma=ChromaConfig("h", 8000, False, "db", "t", "", ""),
        admin_telegram_id=None,
        redeem_codes={},
        model_dir=str(MODEL_DIR),
        tmp_voice_dir=str(TMP),
        tmp_svg_dir=str(TMP),
        limits=Limits(),
    )


async def main() -> None:
    cfg = make_cfg()
    engine = TTSEngine(cfg)

    # -- download only the smallest model to keep this test fast -------------
    voice = VOICES["VIVOS_A"]
    engine.model_dir.mkdir(parents=True, exist_ok=True)
    stem = voice.model[len("vi_VN-"):]
    dataset, quality = stem.rsplit("-", 1)
    from app.tts.voices import HF_BASE

    base = f"{HF_BASE}/{dataset}/{quality}/{voice.model}"
    t0 = time.monotonic()
    engine._download_file(f"{base}.onnx", MODEL_DIR / f"{voice.model}.onnx", min_size=1_000_000)
    engine._download_file(f"{base}.onnx.json", MODEL_DIR / f"{voice.model}.onnx.json")
    print(f"model download: {time.monotonic() - t0:.1f}s")
    assert engine.status() is False  # other models not cached yet — honest status

    # -- real TTS -------------------------------------------------------------
    t0 = time.monotonic()
    wav, duration, sr = await engine.synthesize(
        "Xin   chào     bạn!   Hôm nay bạn khỏe không?", voice
    )
    print(f"tts: {time.monotonic() - t0:.1f}s wav={wav.name} duration={duration:.2f}s rate={sr}")
    assert wav.is_file() and wav.stat().st_size > 10_000
    assert duration > 1.0

    # -- ffmpeg ---------------------------------------------------------------
    ogg = wav.with_suffix(".ogg")
    t0 = time.monotonic()
    await wav_to_ogg_opus(wav, ogg, timeout=30)
    print(f"ffmpeg: {time.monotonic() - t0:.1f}s ogg_size={ogg.stat().st_size}")
    assert ogg.is_file() and ogg.stat().st_size > 5_000
    assert not wav.exists()  # wav cleaned up
    ogg.unlink()

    # -- svg pipeline ----------------------------------------------------------
    scene = validate_scene(
        {
            "width": 512,
            "height": 512,
            "background": "#e8f4ff",
            "elements": [
                {"type": "circle", "cx": 256, "cy": 220, "r": 120, "fill": "#ffcc00"},
                {"type": "rect", "x": 96, "y": 380, "width": 320, "height": 60, "fill": "#3366cc"},
                {"type": "text", "x": 110, "y": 420, "text": "Xin chào!", "font_size": 32},
            ],
        },
        cfg.limits,
    )
    svg = render_scene_svg(scene)
    safe = sanitize_svg(svg, max_bytes=cfg.limits.max_svg_bytes)
    png = await render_png(safe, max_width=512, timeout=30)
    print(f"svg: {len(safe)} chars, png: {len(png)} bytes, header={png[:8]!r}")
    assert png.startswith(b"\x89PNG")

    print("SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
