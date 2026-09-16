"""/svg — independent SVG generation workflow (spec §11-§13)."""
from __future__ import annotations

import io
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.ai.client import AIServiceError
from app.billing.credits import calculate_svg_cost, format_cost
from app.bot.handlers.common import ensure_user, require_activated, services, state_is_processing
from app.bot.keyboards import svg_result_kb
from app.bot.messages import (
    AI_DOWN,
    BUSY,
    GENERIC_DOWN,
    NO_CREDIT,
    SVG_BAD_PROMPT,
    SVG_DONE,
    SVG_DOWN,
    SVG_PROCESSING,
    SVG_PROMPT,
    SVG_RESULT_NOTE,
)
from app.database.users import (
    STATE_IDLE,
    STATE_SVG_PROCESSING,
    STATE_SVG_WAITING_PROMPT,
)
from app.svg.generator import SceneError, generate_scene
from app.svg.renderer import render_scene_svg
from app.svg.sanitizer import SVGSanitizeError, sanitize_svg

logger = logging.getLogger(__name__)


async def svg_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
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
    if not svc.limiter.allow(uid, "svg"):
        return
    await svc.users.set_fields(uid, state=STATE_SVG_WAITING_PROMPT, pending_text="")
    await update.effective_message.reply_text(SVG_PROMPT)


async def handle_svg_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user: dict) -> None:
    svc = services(ctx)
    uid = update.effective_user.id
    limits = svc.cfg.limits
    prompt = (update.message.text or "").strip()
    if len(prompt) > limits.max_svg_prompt_chars:
        await update.effective_message.reply_text(
            SVG_BAD_PROMPT.format(chars=len(prompt), max=limits.max_svg_prompt_chars)
        )
        return
    if len(prompt) < 3:
        await update.effective_message.reply_text("Hãy mô tả chi tiết hơn một chút nhé.")
        return

    cost = calculate_svg_cost()
    balance = float(user.get("credit") or 0.0)
    if balance < cost.amount:
        await update.effective_message.reply_text(
            NO_CREDIT.format(balance=f"${balance:,.2f}", cost=format_cost(cost.amount))
        )
        return

    await svc.users.set_state(uid, STATE_SVG_PROCESSING)
    await update.effective_message.reply_text(SVG_PROCESSING)

    submitted = await svc.jobs.submit(
        uid,
        "svg",
        lambda: _run_svg_job(svc, prompt),
        on_success=lambda result: _on_svg_success(ctx, uid, cost.amount, result),
        on_error=lambda exc: _on_svg_error(ctx, uid, exc),
        timeout=svc.cfg.limits.ai_timeout_seconds + svc.cfg.limits.svg_preview_timeout_seconds + 10,
    )
    if not submitted:  # race
        await svc.users.set_state(uid, STATE_IDLE)
        await update.effective_message.reply_text(BUSY)


async def _run_svg_job(svc, prompt: str) -> dict:
    scene = await generate_scene(svc.ai, prompt, svc.cfg.limits)
    svg = render_scene_svg(scene)
    safe_svg = sanitize_svg(svg, max_bytes=svc.cfg.limits.max_svg_bytes)
    return {
        "svg": safe_svg,
        "width": scene.width,
        "height": scene.height,
        "elements": len(scene.elements),
        "prompt": prompt,
    }


async def _on_svg_success(ctx, uid: int, cost_amount: float, result: dict) -> None:
    svc = services(ctx)
    try:
        user = await svc.users.get(uid)
        conv_id = (user or {}).get("active_conversation") or ""
        if conv_id and not await svc.conversations.owns(conv_id, uid):
            conv_id = ""
        if not conv_id:
            conv = await svc.conversations.create(uid, workflow="svg")
            conv_id = conv["conversation_id"]
            await svc.users.set_fields(uid, active_conversation=conv_id)

        gen_id = await svc.svg_gens.add(
            uid=uid,
            conversation_id=conv_id,
            prompt=result["prompt"],
            svg_source=result["svg"],
            width=result["width"],
            height=result["height"],
            element_count=result["elements"],
            cost=cost_amount,
        )
        ok, _balance = await svc.users.try_charge(uid, cost_amount)
        if not ok:
            logger.warning("svg charge failed for uid=%s (insufficient at completion)", uid)
        await svc.usage.log(uid, conv_id, "svg", cost_amount, detail=f"{result['width']}x{result['height']}")
        await svc.conversations.touch(conv_id, workflow="svg", add_cost=cost_amount)
        await svc.messages.add(conv_id, uid, "user", "svg_prompt", result["prompt"])
        await svc.messages.add(conv_id, uid, "assistant", "svg_result", f"{result['width']}x{result['height']} elements={result['elements']}")
        await svc.users.set_fields(uid, state=STATE_IDLE, pending_text="")
    except Exception:  # noqa: BLE001
        logger.exception("svg post-processing failed")
        await svc.users.set_fields(uid, state=STATE_IDLE, pending_text="")
        await ctx.bot.send_message(uid, GENERIC_DOWN)
        return

    await ctx.bot.send_message(
        uid,
        SVG_DONE.format(
            width=result["width"], height=result["height"],
            elements=result["elements"], cost=format_cost(cost_amount),
        ) + "\n\n" + SVG_RESULT_NOTE,
        reply_markup=svg_result_kb(gen_id),
    )


async def _on_svg_error(ctx, uid: int, exc: BaseException) -> None:
    svc = services(ctx)
    try:
        await svc.users.set_fields(uid, state=STATE_IDLE, pending_text="")
    except Exception:  # noqa: BLE001
        logger.exception("reset state after svg error failed")
    if isinstance(exc, (SceneError, SVGSanitizeError)):
        logger.warning("SVG scene rejected: %s", exc)
        await ctx.bot.send_message(uid, SVG_DOWN)
    elif isinstance(exc, AIServiceError):
        await ctx.bot.send_message(uid, AI_DOWN)
    else:
        logger.error("svg job unexpected error", exc_info=exc)
        await ctx.bot.send_message(uid, GENERIC_DOWN)


async def handle_svg_action_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data or ""
    await handle_svg_action(update, ctx, data.split(":", 1)[-1])


async def handle_svg_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE, payload: str) -> None:
    """Inline buttons: svgaction:<preview|code|download>:<gen_id>."""
    try:
        kind, gen_id = payload.split(":", 1)
    except ValueError:
        return
    query = update.callback_query
    svc = services(ctx)
    uid = update.effective_user.id
    await query.answer()

    record = await svc.svg_gens.get(gen_id)
    if not record or record.get("uid") != str(uid):
        await query.message.reply_text("Không tìm thấy kết quả này (hoặc không thuộc tài khoản của bạn).")
        return
    svg_source = str(record.get("svg_source") or "")
    if not svg_source:
        await query.message.reply_text(SVG_DOWN)
        return

    if kind == "preview":
        if record.get("preview_file_id"):
            await ctx.bot.send_photo(uid, photo=record["preview_file_id"],
                                     caption=f"🖼 {record.get('width')}x{record.get('height')}")
            return
        try:
            from app.svg.renderer import render_png
            png = await render_png(
                svg_source, max_width=min(1280, max(512, int(record.get("width") or 1024))),
                timeout=svc.cfg.limits.svg_preview_timeout_seconds,
            )
        except Exception:  # noqa: BLE001
            logger.exception("preview render failed")
            await query.message.reply_text(SVG_NO_PREVIEW)
            return
        sent = await ctx.bot.send_photo(
            uid, photo=io.BytesIO(png), caption=f"🖼 {record.get('width')}x{record.get('height')}"
        )
        try:
            file_id = sent.photo[-1].file_id if sent.photo else ""
            if file_id:
                await svc.svg_gens.update(gen_id, preview_file_id=file_id)
        except Exception:  # noqa: BLE001
            logger.debug("cache preview file_id failed", exc_info=True)
        return

    if kind in ("code", "download"):
        if record.get("code_file_id"):
            await ctx.bot.send_document(uid, document=record["code_file_id"])
            return
        filename = f"wioos-svg-{gen_id[:8]}.svg"
        sent = await ctx.bot.send_document(
            uid, document=io.BytesIO(svg_source.encode("utf-8")), filename=filename,
            caption=f"</> {filename} — source SVG",
        )
        try:
            if sent.document and sent.document.file_id:
                await svc.svg_gens.update(gen_id, code_file_id=sent.document.file_id)
        except Exception:  # noqa: BLE001
            logger.debug("cache code file_id failed", exc_info=True)
        return


