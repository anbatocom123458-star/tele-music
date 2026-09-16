"""Final SVG sanitizer (spec §12).

Even though the renderer only emits safe markup, this pass re-parses the
serialized SVG and strips anything dangerous, so a future code path that
accepts external SVG cannot regress:
- <script>, <iframe>, <foreignObject>, <object>, <embed>, <use>, <image>
- any attribute starting with "on" (event handlers)
- href/xlink:href unless it is a same-document fragment (#id)
- style attributes containing url( / expression( / @import
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

BANNED_TAGS = {
    "script", "iframe", "foreignObject", "object", "embed", "use",
    "image", "audio", "video", "handler", "listener",
}
SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


class SVGSanitizeError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.split("}")[-1].lower()


def _clean_attrs(el: ET.Element) -> None:
    for attr in list(el.attrib.keys()):
        local = _local(attr)
        value = el.attrib[attr]
        if local.startswith("on"):
            del el.attrib[attr]
            continue
        if local in ("href", "src") or attr == XLINK_HREF:
            if not value.strip().startswith("#"):
                del el.attrib[attr]
            continue
        if local == "style":
            lowered = value.lower()
            if "url(" in lowered or "expression(" in lowered or "@import" in lowered:
                del el.attrib[attr]


def sanitize_svg(svg_text: str, max_bytes: int) -> str:
    if not svg_text or not svg_text.strip():
        raise SVGSanitizeError("SVG rỗng.")
    if len(svg_text.encode("utf-8")) > max_bytes:
        raise SVGSanitizeError(f"SVG vượt quá giới hạn {max_bytes} bytes.")
    if "<?entity" in svg_text.lower() or "<!entity" in svg_text.lower():
        raise SVGSanitizeError("SVG chứa entity declaration.")
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise SVGSanitizeError(f"SVG không parse được: {exc}") from exc

    def _walk(el: ET.Element) -> None:
        for child in list(el):
            if _local(child.tag) in BANNED_TAGS:
                el.remove(child)
                continue
            _clean_attrs(child)
            _walk(child)

    _clean_attrs(root)
    _walk(root)

    try:
        ET.register_namespace("", SVG_NS[1:-1])
        return ET.tostring(root, encoding="unicode")
    except Exception as exc:  # noqa: BLE001
        raise SVGSanitizeError(f"Không serialize được SVG: {exc}") from exc
