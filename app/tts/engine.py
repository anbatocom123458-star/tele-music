"""Piper TTS engine.

- Models are DOWNLOADED at container start (ensure_models_downloaded) and
  cached in MODEL_DIR (persist this dir on a Railway volume).
- ONNX sessions are loaded lazily and kept in an LRU cache (max 2 models in
  RAM) to stay memory-friendly; inference is serialized with a semaphore so
  two jobs never oversubscribe the CPU.
- All blocking work runs in threads; asyncio timeouts wrap every stage.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import urllib.request
import wave
from collections import OrderedDict
from pathlib import Path

from app.config import Config
from app.tts.processor import normalize_for_tts
from app.tts.voices import ALL_MODELS, VoiceOption

logger = logging.getLogger(__name__)

CHUNK = 1 << 20


class TTSError(RuntimeError):
    pass


class TTSTimeout(TTSError):
    pass


class TTSEngine:
    MAX_LOADED_MODELS = 2

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.model_dir = Path(cfg.model_dir)
        self._voices: OrderedDict[str, object] = OrderedDict()
        self._load_lock = asyncio.Lock()
        self._infer_semaphore = asyncio.Semaphore(1)
        self._ready = False

    # -- model management ------------------------------------------------
    def model_paths(self, model: str) -> tuple[Path, Path] | None:
        onnx = self.model_dir / f"{model}.onnx"
        conf = self.model_dir / f"{model}.onnx.json"
        if onnx.is_file() and conf.is_file():
            return onnx, conf
        return None

    def _download_file(self, url: str, dest: Path, min_size: int = 1024) -> None:
        if dest.is_file() and dest.stat().st_size >= min_size:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        logger.info("Downloading %s -> %s", url, dest)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as fh:
                    while True:
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        fh.write(chunk)
                if tmp.stat().st_size < min_size:
                    raise TTSError(f"File tải về quá nhỏ: {dest.name}")
                os.replace(tmp, dest)
                return
            except Exception as exc:  # noqa: BLE001 - retry with backoff
                last_error = exc
                logger.warning("Download attempt %d failed for %s: %s", attempt + 1, url, exc)
                time.sleep(2 * (attempt + 1))
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise TTSError(f"Không thể tải model {dest.name}: {last_error}")

    def ensure_models_downloaded_sync(self) -> None:
        """Blocking. Runs once at container start. Skips already-cached files."""
        from app.tts.voices import HF_BASE

        self.model_dir.mkdir(parents=True, exist_ok=True)
        for model in ALL_MODELS:
            if self.model_paths(model):
                logger.info("TTS model cached: %s", model)
                continue
            stem = model[len("vi_VN-"):]
            dataset, quality = stem.rsplit("-", 1)
            base = f"{HF_BASE}/{dataset}/{quality}/{model}"
            self._download_file(f"{base}.onnx", self.model_dir / f"{model}.onnx", min_size=1_000_000)
            self._download_file(f"{base}.onnx.json", self.model_dir / f"{model}.onnx.json")
        self._ready = True
        logger.info("All TTS models ready in %s", self.model_dir)

    async def ensure_models_downloaded(self) -> None:
        await asyncio.to_thread(self.ensure_models_downloaded_sync)

    def status(self) -> bool:
        if not self._ready:
            return all(self.model_paths(m) is not None for m in ALL_MODELS)
        return True

    # -- inference --------------------------------------------------------
    def _load_model_sync(self, model: str):
        try:
            from piper import PiperVoice  # heavy import, only when needed
        except ImportError as exc:
            raise TTSError("piper-tts chưa được cài trong container.") from exc
        paths = self.model_paths(model)
        if not paths:
            raise TTSError(f"Model {model} chưa được tải về.")
        onnx, _conf = paths
        logger.info("Loading Piper model: %s", model)
        return PiperVoice.load(str(onnx))

    async def _get_voice(self, model: str):
        cached = self._voices.get(model)
        if cached is not None:
            self._voices.move_to_end(model)
            return cached
        async with self._load_lock:
            cached = self._voices.get(model)
            if cached is None:
                cached = await asyncio.to_thread(self._load_model_sync, model)
                self._voices[model] = cached
                while len(self._voices) > self.MAX_LOADED_MODELS:
                    evicted_model, evicted = self._voices.popitem(last=False)
                    logger.info("Evicting loaded model from RAM: %s", evicted_model)
                    del evicted
            return cached

    def _synthesize_sync(self, voice_obj, text: str, out_path: Path) -> float:
        """Blocking Piper synthesis -> WAV. Returns duration in seconds."""
        started = time.monotonic()
        with wave.open(str(out_path), "wb") as wav_file:
            voice_obj.synthesize_wav(text, wav_file)
        logger.info("TTS synth done in %.2fs", time.monotonic() - started)
        return _wav_duration(out_path)

    async def synthesize(self, text: str, voice: VoiceOption) -> tuple[Path, float, int]:
        """Returns (wav_path, duration_seconds, sample_rate). Caller deletes path."""
        clean = normalize_for_tts(text)
        if not clean:
            raise TTSError("Văn bản rỗng sau khi làm sạch.")
        try:
            voice_obj = await self._get_voice(voice.model)
        except TTSError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TTSError(f"Lỗi nạp model TTS: {exc}") from exc

        out_path = Path(self.cfg.tmp_voice_dir) / f"tts_{int(time.time() * 1000)}_{voice.key}.wav"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with self._infer_semaphore:
                await asyncio.wait_for(
                    asyncio.to_thread(self._synthesize_sync, voice_obj, clean, out_path),
                    timeout=self.cfg.limits.tts_timeout_seconds,
                )
        except asyncio.TimeoutError as exc:
            out_path.unlink(missing_ok=True)
            raise TTSTimeout(f"TTS vượt quá {self.cfg.limits.tts_timeout_seconds}s.") from exc
        except Exception as exc:  # noqa: BLE001
            out_path.unlink(missing_ok=True)
            raise TTSError(f"Lỗi tổng hợp giọng nói: {exc}") from exc
        return out_path, round(max(0.0, _wav_duration(out_path)), 2), voice.sample_rate


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / float(wav_file.getframerate() or 1)


# -- ffmpeg ---------------------------------------------------------------


class FFmpegError(TTSError):
    pass


async def wav_to_ogg_opus(wav_path: Path, ogg_path: Path, timeout: int = 30) -> Path:
    """Convert WAV -> OGG/Opus for Telegram voice notes. Deletes the WAV."""
    ogg_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav_path),
        "-map_metadata", "-1",
        "-c:a", "libopus", "-b:a", "48k", "-vbr", "on",
        "-compression_level", "8",
        str(ogg_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        proc.kill()
        wav_path.unlink(missing_ok=True)
        raise FFmpegError(f"FFmpeg vượt quá {timeout}s.") from exc
    wav_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise FFmpegError(f"FFmpeg lỗi: {stderr.decode(errors='replace')[:300]}")
    if not ogg_path.is_file() or ogg_path.stat().st_size == 0:
        raise FFmpegError("FFmpeg không tạo được file âm thanh.")
    return ogg_path


def cleanup_dir(path: Path, max_age_seconds: int = 3600) -> None:
    """Best-effort cleanup of stale temp files (crash leftovers)."""
    now = time.time()
    try:
        for file in Path(path).glob("*"):
            try:
                if file.is_file() and now - file.stat().st_mtime > max_age_seconds:
                    file.unlink()
            except OSError:
                continue
    except OSError:
        pass

