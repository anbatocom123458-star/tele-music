"""Server-side SVG renderer.

Builds SVG text purely from a validated Scene — numeric attributes are
formatted by us, text content is XML-escaped, so no injection survives.
Also renders PNG previews via cairosvg (lazy import, run in a thread).
"""
from __future__ import annotations

import asyncio
from xml.sax.saxutils import escape

from app.svg.generator import Scene


def _fmt(v: float) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _paint(el: dict, key: str) -> str:
    val = el.get(key)
    if val in (None, "", "none"):
        return ""
    return f' {key}="{escape(str(val))}"'


def render_scene_svg(scene: Scene) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" '
        f'height="{scene.height}" viewBox="0 0 {scene.width} {scene.height}">',
        f'<rect x="0" y="0" width="{scene.width}" height="{scene.height}" '
        f'fill="{escape(scene.background)}"/>',
    ]
    for el in scene.elements:
        etype = el["type"]
        common = _paint(el, "fill") + _paint(el, "stroke")
        if el.get("stroke_width") is not None:
            common += f' stroke-width="{_fmt(el["stroke_width"])}"'
        if el.get("opacity") is not None:
            common += f' opacity="{_fmt(el["opacity"])}"'

        if etype == "rect":
            body = (
                f'<rect x="{_fmt(el.get("x", 0))}" y="{_fmt(el.get("y", 0))}" '
                f'width="{_fmt(el.get("width", 100))}" height="{_fmt(el.get("height", 100))}"'
                f"{common}/>"
            )
        elif etype == "circle":
            body = (
                f'<circle cx="{_fmt(el.get("cx", 0))}" cy="{_fmt(el.get("cy", 0))}" '
                f'r="{_fmt(el.get("r", 50))}"{common}/>'
            )
        elif etype == "ellipse":
            body = (
                f'<ellipse cx="{_fmt(el.get("cx", 0))}" cy="{_fmt(el.get("cy", 0))}" '
                f'rx="{_fmt(el.get("rx", 50))}" ry="{_fmt(el.get("ry", 30))}"{common}/>'
            )
        elif etype == "line":
            body = (
                f'<line x1="{_fmt(el.get("x1", 0))}" y1="{_fmt(el.get("y1", 0))}" '
                f'x2="{_fmt(el.get("x2", 100))}" y2="{_fmt(el.get("y2", 100))}"'
                f'{common or " stroke=\"#333333\" stroke-width=\"2\""} />'
            )
        elif etype in ("polyline", "polygon"):
            pts = " ".join(f"{_fmt(px)},{_fmt(py)}" for px, py in el.get("points", []))
            tag = "polyline" if etype == "polyline" else "polygon"
            if etype == "polyline" and not el.get("fill"):
                common += ' fill="none"'
            body = f'<{tag} points="{pts}"{common}/>'
        elif etype == "path":
            body = f'<path d="{escape(el.get("d", ""))}"{common or " fill=\"none\" stroke=\"#333333\""}/>'
        elif etype == "text":
            font = _fmt(el.get("font_size", 24))
            body = (
                f'<text x="{_fmt(el.get("x", 0))}" y="{_fmt(el.get("y", 0))}" '
                f'font-family="sans-serif" font-size="{font}"{common or " fill=\"#222222\""}>'
                f'{escape(str(el.get("text", "")))}</text>'
            )
        else:  # unreachable — validated upstream
            continue

        rotate = el.get("rotate")
        if rotate:
            cx = _fmt(el.get("x", el.get("cx", 0)))
            cy = _fmt(el.get("y", el.get("cy", 0)))
            body = f'<g transform="rotate({_fmt(rotate)} {cx} {cy})">{body}</g>'
        parts.append(body)

    parts.append("</svg>")
    return "".join(parts)


async def render_png(svg_source: str, max_width: int = 1024, timeout: int = 30) -> bytes:
    """Rasterize SVG to PNG (cairosvg) in a worker thread with a timeout."""
    def _render() -> bytes:
        import cairosvg  # lazy: requires libcairo2 in the container

        return cairosvg.svg2png(bytestring=svg_source.encode("utf-8"), output_width=max_width)

    try:
        return await asyncio.wait_for(asyncio.to_thread(_render), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"SVG preview render vượt quá {timeout}s.") from exc
