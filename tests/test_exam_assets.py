from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


BANK_ROOT = Path(__file__).resolve().parents[1] / "Knowledge" / "Exam" / "高考真题" / "diagnose"
ASSET_URL = re.compile(r'src=\\?"[^"\\]*?/exam-diagnostics/assets/([^"\\]+)')
UNITLESS_FONT_SIZE = re.compile(
    r"font-size\s*:\s*-?(?:\d+(?:\.\d*)?|\.\d+)(?=\s*;)",
    flags=re.I,
)
LEGACY_TIMES_FAMILY = re.compile(r"font-family\s*:\s*Times(?=\s*;)", flags=re.I)


def test_every_published_exam_asset_exists_and_is_browser_renderable() -> None:
    references: set[str] = set()
    invalid_svg: list[str] = []
    private_glyphs: list[str] = []
    invalid_font_metrics: list[str] = []
    # Scan both student paper files and the isolated answer banks: grading and
    # post-submission explanations may render formulas from either side.
    for payload_path in BANK_ROOT.rglob("*.json"):
        references.update(ASSET_URL.findall(payload_path.read_text(encoding="utf-8")))

    assert references, "诊断卷没有提取到任何图片资源引用"
    for relative in references:
        asset = BANK_ROOT / "assets" / relative
        assert asset.is_file(), f"诊断卷引用的资源不存在：{relative}"
        assert asset.stat().st_size > 0, f"诊断卷引用了空资源：{relative}"
        assert asset.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"}, (
            f"浏览器不应直接加载旧版 Office 图片格式：{relative}"
        )
        if asset.suffix.lower() == ".svg":
            raw = asset.read_bytes()
            assert b"<svg" in raw[:2048], f"SVG 资源内容无效：{relative}"
            text = raw.decode("utf-8")
            assert "\ufffd" not in text, f"SVG 含 Unicode 替换字符：{relative}"
            if any(0xE000 <= ord(character) <= 0xF8FF for character in text):
                private_glyphs.append(relative)
            if UNITLESS_FONT_SIZE.search(text) or LEGACY_TIMES_FAMILY.search(text):
                invalid_font_metrics.append(relative)
            try:
                ET.parse(asset)
            except ET.ParseError as exc:
                invalid_svg.append(f"{relative}: {exc}")
    assert not invalid_svg, "浏览器无法解析以下 SVG：\n" + "\n".join(invalid_svg)
    assert not private_glyphs, "SVG 含浏览器无法显示的 MathType 私有字符：\n" + "\n".join(private_glyphs)
    assert not invalid_font_metrics, (
        "SVG 仍含会造成公式重叠或错位的旧字体声明：\n"
        + "\n".join(invalid_font_metrics)
    )


def test_mathtype_greek_charset_is_preserved_in_trigonometric_formula() -> None:
    formula = (
        BANK_ROOT
        / "assets"
        / "mathematics"
        / "79a7b6ef0e1fac6a7580.svg"
    ).read_text(encoding="utf-8")
    assert ">π<" in formula
    assert ">α<" in formula
    assert ">ð<" not in formula
    assert "font-family:Liberation Serif,Times New Roman,serif" in formula
    assert not UNITLESS_FONT_SIZE.search(formula)
    # The original WMF uses MathType's six-part scalable round parentheses.
    # Keeping every piece is what makes the tall pair continuous in browsers.
    for delimiter_piece in "⎛⎜⎝⎞⎟⎠":
        assert f">{delimiter_piece}<" in formula
