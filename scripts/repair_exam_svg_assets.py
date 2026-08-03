#!/usr/bin/env python3
"""Repair legacy wmf2svg output that contains non-UTF-8 font bytes."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

from exam_svg_utils import browser_safe_svg_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT / "Knowledge" / "Exam" / "高考真题" / "diagnose" / "assets"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="replace invalid SVG files in place")
    args = parser.parse_args()
    scanned = repaired_count = 0
    for path in ASSET_ROOT.rglob("*.svg"):
        scanned += 1
        raw = path.read_bytes()
        if not raw.strip():
            continue
        try:
            wmf_path = path.with_suffix(".wmf")
            repaired = browser_safe_svg_bytes(
                raw,
                source_wmf=wmf_path.read_bytes() if wmf_path.is_file() else None,
            )
        except ET.ParseError as exc:
            raise RuntimeError(f"无法自动修复 SVG：{path}: {exc}") from exc
        if repaired == raw:
            continue
        repaired_count += 1
        if args.write:
            path.write_bytes(repaired)
    action = "已修复" if args.write else "待修复"
    print(f"扫描 SVG {scanned} 个，{action} {repaired_count} 个")


if __name__ == "__main__":
    main()
