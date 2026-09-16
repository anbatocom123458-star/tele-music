"""/voice — TTS workflow (independent pipeline, spec §7-§10)."""
from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.billing.credits import calculate_voice_cost, format_cost
from app.bot.handlers.common import ensure_user, require_activated, services, state_is_processing
from app.bot.keyboards import voice_selection_kb
from app.bot.messages import (
    BUSY,
    GENERIC_DOWN,
    NO_CREDIT,
    VOICE_DONE,
    VOICE_PROCESSING,
    VOICE_PROMPT,
    VOICE_SELECT,
    VOICE_VOICE_NOTE,
    TTS_DOWN,
)
from app.database.users import (
    STATE_IDLE,
    STATE_VOICE_PROCESSING,
    STATE_VOICE_SELECTING_VOICE,
    STATE_VOICE_WAITING_TEXT,
)
from app.tts.engine import FFmpegError, TTSError, wav_to_ogg_opus
from app.tts.processor import VoiceTextError, validate_voice_text
from app.tts.voices import VOICES

logger = logging.getLogger(__name__)


async def voice_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    uid = update.effective_user.id
    user = await ensure_user(update, svc)
    if not await require_activated(update, user):
        return
    if svc.jobs.busy(uid) or state_is_processing(user):
        await update.effective_message.reply_text(BUSY)
        return
    if not svc.limiter.allow(uid, "voice"):
        return
    await svc.users.set_fields(
        uid, state=STATE_VOICE_WAITING_TEXT, pending_text="", pending_voice=""
    )
    await update.effective_message.reply_text(VOICE_PROMPT)


async def handle_voice_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user: dict) -> None:
    svc = services(ctx)
    uid = update.effective_user.id
    limits = svc.cfg.limits
    try:
        clean = validate_voice_text(update.message.text, limits.max_voice_chars, limits.min_voice_chars)
    except VoiceTextError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    await svc.users.set_fields(uid, pending_text=clean, state=STATE_VOICE_SELECTING_VOICE)
    await update.effective_message.reply_text(
        VOICE_SELECT + VOICE_VOICE_NOTE.format(n=len(VOICES)),
        reply_markup=voice_selection_kb(),
    )


async def handle_voice_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE, voice_key: str) -> None:
    """Inline keyboard selection: voice:<KEY>."""
    query = update.callback_query
    svc = services(ctx)
    uid = update.effective_user.id
    voice = VOICES.get(voice_key)
    if voice is None:
        await query.answer("Giọng không hợp lệ.", show_alert=True)
        return
    user = await svc.users.get(uid)
    if not user or user.get("state") != STATE_VOICE_SELECTING_VOICE:
        await query.answer("Yêu cầu không còn hiệu lực. Gõ /voice để bắt đầu lại.", show_alert=True)
        return

    clean_text = str(user.get("pending_text") or "")
    cost = calculate_voice_cost(clean_text)
    balance = float(user.get("credit") or 0.0)
    if balance < cost.amount:
        await query.answer()
        await query.message.reply_text(
            NO_CREDIT.format(balance=f"${balance:,.2f}", cost=format_cost(cost.amount))
        )
        return

    await query.answer()
    try:
        await query.edit_message_text(VOICE_PROCESSING)
    except Exception:  # noqa: BLE001
        pass

    # Ensure a conversation exists for this request.
    conv_id = user.get("active_conversation") or ""
    if conv_id and not await svc.conversations.owns(conv_id, uid):
        conv_id = ""
    if not conv_id:
        conv = await svc.conversations.create(uid, workflow="voice")
        conv_id = conv["conversation_id"]
        await svc.users.set_fields(uid, active_conversation=conv_id)

    await svc.users.set_state(uid, STATE_VOICE_PROCESSING)
    submitted = await svc.jobs.submit(
        uid,
        "voice",
        lambda: _run_voice_job(svc, clean_text, voice),
        on_success=lambda result: _on_voice_success(ctx, uid, cost.amount, result),
        on_error=lambda exc: _on_voice_error(ctx, uid, exc),
        timeout=svc.cfg.limits.tts_timeout_seconds + svc.cfg.limits.ffmpeg_timeout_seconds + 10,
    )
    if not submitted:  # race: another job snuck in
        await svc.users.set_state(uid, STATE_IDLE)
        await query.message.reply_text(BUSY)


async def _run_voice_job(svc, clean_text: str, voice):
    wav_path, duration, _sr = await svc.tts.synthesize(clean_text, voice)
    ogg_path = wav_path.with_suffix(".ogg")
    try:
        await wav_to_ogg_opus(wav_path, ogg_path, timeout=svc.cfg.limits.ffmpeg_timeout_seconds)
    except BaseException:
        ogg_path.unlink(missing_ok=True)
        raise
    return {"ogg": ogg_path, "duration": duration, "voice": voice}


async def _on_voice_success(ctx, uid: int, cost_amount: float, result: dict) -> None:
    from app.bot.handlers.common import fmt_cost

    svc = services(ctx)
    voice = result["voice"]
    ogg: Path = result["ogg"]
    duration: float = result["duration"]
    caption = VOICE_DONE.format(
        voice=voice.label, duration=f"{duration:.1f}", cost=fmt_cost(cost_amount)
    )
    try:
        await svc.users.set_state(uid, STATE_IDLE)
    except Exception:  # noqa: BLE001
        logger.exception("reset state after voice success failed")

    sent = None
    try:
        with open(ogg, "rb") as fh:
            sent = await ctx.bot.send_voice(chat_id=uid, voice=fh, caption=caption)
    except Exception:  # noqa: BLE001
        logger.warning("send_voice failed, falling back to send_audio")
        try:
            with open(ogg, "rb") as fh:
                sent = await ctx.bot.send_audio(chat_id=uid, audio=fh, caption=caption)
        except Exception:  # noqa: BLE001
            logger.exception("sending voice result failed")
            await ctx.bot.send_message(uid, TTS_DOWN)
    finally:
        ogg.unlink(missing_ok=True)

    file_id = ""
    if sent is not None:
        media = sent.voice or sent.audio
        file_id = media.file_id if media else ""

    # Charge credit ONLY after a successful generation (check happened earlier).
    try:
        ok, _balance = await svc.users.try_charge(uid, cost_amount)
        if not ok:
            logger.warning("voice charge failed for uid=%s (insufficient at completion)", uid)
    except Exception:  # noqa: BLE001
        logger.exception("voice charge failed")

    try:
        user = await svc.users.get(uid)
        conv_id = (user or {}).get("active_conversation") or ""
        await svc.voice_gens.add(
            uid=uid, conversation_id=conv_id, voice_key=voice.key,
            voice_label=voice.label, text=str((user or {}).get("pending_text") or ""),
            chars=len(str((user or {}).get("pending_text") or "")),
            duration_s=duration, cost=cost_amount, file_id=file_id,
        )
        await svc.usage.log(uid, conv_id, "voice", cost_amount, detail=voice.key)
        if conv_id:
            await svc.conversations.touch(conv_id, workflow="voice", add_cost=cost_amount)
            await svc.messages.add(conv_id, uid, "user", "voice_text", str((user or {}).get("pending_text") or ""))
            await svc.messages.add(conv_id, uid, "assistant", "voice_result", f"{voice.label} | {duration:.1f}s")
        await svc.users.set_fields(uid, pending_text="", pending_voice="")
    except Exception:  # noqa: BLE001
        logger.exception("recording voice generation metadata failed")


async def handle_voice_callback_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data or ""
    await handle_voice_callback(update, ctx, data.split(":", 1)[-1])


async def _on_voice_error(ctx, uid: int, exc: BaseException) -> None:
    svc = services(ctx)
    try:
        await svc.users.set_fields(uid, state=STATE_IDLE, pending_text="", pending_voice="")
    except Exception:  # noqa: BLE001
        logger.exception("reset state after voice error failed")
    if isinstance(exc, (TTSError, FFmpegError)):
        await ctx.bot.send_message(uid, TTS_DOWN)
    else:
        logger.error("voice job unexpected error", exc_info=exc)
        await ctx.bot.send_message(uid, GENERIC_DOWN)

