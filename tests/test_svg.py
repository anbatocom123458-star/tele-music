"""SVG scene validation, rendering, sanitizing (spec §12)."""
from __future__ import annotations

import pytest

from app.config import Limits
from app.svg.generator import SceneError, validate_scene
from app.svg.renderer import render_scene_svg
from app.svg.sanitizer import SVGSanitizeError, sanitize_svg

LIMITS = Limits()


def test_valid_scene_renders_svg():
    scene = validate_scene(
        {
            "width": 1024,
            "height": 1024,
            "background": "#f5f1e8",
            "elements": [
                {"type": "rect", "x": 0, "y": 0, "width": 1024, "height": 1024, "fill": "#f5f1e8"},
                {"type": "circle", "cx": 512, "cy": 512, "r": 200, "fill": "#3366cc"},
                {"type": "text", "x": 100, "y": 900, "text": "Nhà <nhỏ> & đầm", "font_size": 40},
            ],
        },
        LIMITS,
    )
    svg = render_scene_svg(scene)
    assert svg.startswith("<svg")
    assert "</svg>" in svg
    # `<`/`>` are stripped server-side, `&` becomes "và"; nothing injectable survives
    assert "Nhà nhỏ và đầm" in svg
    assert "<script" not in svg


def test_unknown_element_types_dropped():
    scene = validate_scene(
        {
            "width": 512,
            "height": 512,
            "background": "white",
            "elements": [
                {"type": "iframe", "src": "https://evil.example"},
                {"type": "rect", "x": 0, "y": 0, "width": 10, "height": 10},
            ],
        },
        LIMITS,
    )
    assert len(scene.elements) == 1
    assert scene.elements[0]["type"] == "rect"


def test_bad_colors_fall_back():
    scene = validate_scene(
        {
            "width": 512,
            "height": 512,
            "background": "javascript:alert(1)",
            "elements": [{"type": "circle", "cx": 5, "cy": 5, "r": 5, "fill": "url(evil)"}],
        },
        LIMITS,
    )
    assert scene.background == "#f5f1e8"
    assert scene.elements[0]["fill"] == "none"


def test_too_many_elements_rejected():
    elements = [{"type": "rect", "x": 0, "y": 0, "width": 1, "height": 1}] * 500
    with pytest.raises(SceneError):
        validate_scene({"width": 512, "height": 512, "background": "white", "elements": elements}, LIMITS)


def test_path_charset_enforced():
    scene = validate_scene(
        {
            "width": 512,
            "height": 512,
            "background": "white",
            "elements": [
                {"type": "path", "d": "M 0 0 L 10 10 Z", "stroke": "black"},
                {"type": "path", "d": "M 0 0 L 10 10; <script>alert(1)</script>"},
            ],
        },
        LIMITS,
    )
    assert len(scene.elements) == 1


def test_sanitizer_strips_script_and_handlers():
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
        "<script>alert('x')</script>"
        '<circle cx="5" cy="5" r="5" onclick="alert(2)" fill="red"/>'
        '<a href="javascript:alert(3)"><rect width="4" height="4"/></a>'
        '<image href="https://evil.example/x.png"/>'
        '<rect style="fill:url(https://evil.example)" width="2" height="2"/>'
        "</svg>"
    )
    clean = sanitize_svg(dirty, max_bytes=100_000)
    assert "<script" not in clean
    assert "onload" not in clean and "onclick" not in clean
    assert "javascript:" not in clean
    assert "<image" not in clean
    assert "url(" not in clean


def test_sanitizer_rejects_oversize_and_garbage():
    with pytest.raises(SVGSanitizeError):
        sanitize_svg("x" * (LIMITS.max_svg_bytes + 10), max_bytes=LIMITS.max_svg_bytes)
    with pytest.raises(SVGSanitizeError):
        sanitize_svg("<svg><unclosed>", max_bytes=1000)
