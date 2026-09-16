"""AI prompt + structured scene validation (spec §12).

The model must return JSON: {width, height, background, elements:[...]}.
We NEVER trust raw SVG from the model — the server renders the validated
scene into SVG itself, then runs a sanitizer pass (defense in depth).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SYSTEM_PROMPT = """You are a vector scene planner. Convert the user's Vietnamese \
description into a JSON scene spec. Return ONLY a JSON object, no markdown.

Schema:
{
  "width": int (256..2048),
  "height": int (256..2048),
  "background": color,
  "elements": [
    {
      "type": "rect"|"circle"|"ellipse"|"line"|"polyline"|"polygon"|"path"|"text",
      "x": num, "y": num, "width": num, "height": num,          // rect
      "cx": num, "cy": num, "r": num, "rx": num, "ry": num,     // circle/ellipse
      "x1": num, "y1": num, "x2": num, "y2": num,               // line
      "points": [[num, num], ...],                              // polyline/polygon
      "d": "M x y L x y C ... Z (numbers only)",                // path
      "text": "short label (max 120 chars, no HTML)",           // text
      "font_size": num,
      "fill": color, "stroke": color, "stroke_width": num, "opacity": 0..1,
      "rotate": num
    }
  ]
}

Rules:
- Colors: "#RGB/#RRGGBB hex" or simple names (white, black, gray, red, green, blue, \
yellow, orange, purple, brown, pink, navy, teal, skyblue, gold, silver, darkgreen).
- Max 60 elements. Compose the scene with layered shapes; prefer simple flat \
cartoon style with subtle contrast.
- Path "d" may only contain M/L/C/Q/Z commands and numbers/spaces/commas.
- Text elements are short labels only (e.g. a title), never paragraphs.
- Everything must fit inside width x height."""


class SceneError(ValueError):
    """Invalid scene spec from AI — handler shows a friendly message."""


_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_NAMED_COLORS = {
    "white", "black", "gray", "grey", "red", "green", "blue", "yellow",
    "orange", "purple", "brown", "pink", "navy", "teal", "skyblue", "gold",
    "silver", "darkgreen", "lightgray", "beige", "ivory", "coral", "khaki",
    "indigo", "violet", "crimson", "lime", "olive", "maroon",
}
_PATH_D = re.compile(r"^[MLCQZmlcqz0-9eE ,.\-]+$")


def _num(value, default: float, lo: float, hi: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _color(value, fallback: str) -> str:
    if isinstance(value, str):
        v = value.strip().lower()
        if _HEX_COLOR.match(v) or v in _NAMED_COLORS:
            return v
    return fallback


@dataclass
class Scene:
    width: int
    height: int
    background: str
    elements: list[dict] = field(default_factory=list)


def _validate_element(el: dict) -> dict | None:
    etype = str(el.get("type", "")).strip().lower()
    allowed = {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text"}
    if etype not in allowed:
        return None
    out: dict = {"type": etype}

    def put_num(key: str):
        if key in el:
            out[key] = _num(el.get(key), 0.0, -10000.0, 10000.0)

    for key in ("x", "y", "width", "height", "cx", "cy", "r", "rx", "ry",
                "x1", "y1", "x2", "y2", "font_size", "rotate", "stroke_width", "opacity"):
        put_num(key)
    if "stroke_width" in out:
        out["stroke_width"] = min(50.0, max(0.0, out["stroke_width"]))
    if "opacity" in out:
        out["opacity"] = min(1.0, max(0.0, out["opacity"]))
    if "fill" in el:
        out["fill"] = _color(el.get("fill"), "none")
    if "stroke" in el:
        out["stroke"] = _color(el.get("stroke"), "none")

    if etype in ("polyline", "polygon"):
        points_raw = el.get("points") or []
        pts: list[list[float]] = []
        if isinstance(points_raw, str):
            tokens = re.findall(r"-?\d+(?:\.\d+)?", points_raw)
            for i in range(0, len(tokens) - 1, 2):
                pts.append([float(tokens[i]), float(tokens[i + 1])])
        elif isinstance(points_raw, list):
            for pair in points_raw[:200]:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    pts.append([
                        _num(pair[0], 0.0, -10000.0, 10000.0),
                        _num(pair[1], 0.0, -10000.0, 10000.0),
                    ])
        if len(pts) < 2:
            return None
        out["points"] = pts[:200]
    elif etype == "path":
        d = str(el.get("d", "")).strip()
        if not d or len(d) > 2000 or not _PATH_D.match(d):
            return None
        out["d"] = d
    elif etype == "text":
        label = str(el.get("text", "")).strip()
        label = label.replace("&", "và").replace("<", "").replace(">", "")[:120]
        if not label:
            return None
        out["text"] = label
    return out


def validate_scene(data: dict, limits) -> Scene:
    if not isinstance(data, dict):
        raise SceneError("Scene JSON phải là object.")
    width = int(_num(data.get("width"), 1024, 256, 2048))
    height = int(_num(data.get("height"), 1024, 256, 2048))
    background = _color(data.get("background"), "#f5f1e8")

    raw_elements = data.get("elements")
    if not isinstance(raw_elements, list):
        raise SceneError("Thiếu danh sách elements.")
    if len(raw_elements) > limits.max_svg_elements * 3:
        raise SceneError(
            f"Quá nhiều elements ({len(raw_elements)})."
        )

    elements: list[dict] = []
    text_count = 0
    for el in raw_elements:
        if not isinstance(el, dict):
            continue
        parsed = _validate_element(el)
        if parsed is None:
            continue
        if parsed["type"] == "text":
            text_count += 1
            if text_count > 30:
                continue
        elements.append(parsed)
        if len(elements) >= limits.max_svg_elements:
            break
    if not elements:
        raise SceneError("Không có element hợp lệ nào trong scene.")
    return Scene(width=width, height=height, background=background, elements=elements)


async def generate_scene(ai, prompt: str, limits) -> Scene:
    """Ask the external AI for a scene spec, validate it strictly."""
    data = await ai.chat_json(
        SYSTEM_PROMPT,
        f"Mô tả: {prompt}\n\nTrả về JSON scene theo schema.",
    )
    return validate_scene(data, limits)


def scene_to_json(scene: Scene) -> str:
    import json

    return json.dumps(
        {
            "width": scene.width,
            "height": scene.height,
            "background": scene.background,
            "elements": scene.elements,
        },
        ensure_ascii=False,
    )

