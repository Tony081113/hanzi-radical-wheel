"""IDS 部件在不同位置的標準 Unicode 偏旁形式與 SVG 資產鍵。"""
from __future__ import annotations

from pathlib import Path

ASSET_ROOT = Path("assets/radicals")

# Unicode 有正式偏旁字元時才替換；其餘交由 KAGE SVG 保留原始筆畫字形。
VARIANTS = {
    ("水", "left"): "氵", ("心", "left"): "忄", ("手", "left"): "扌",
    ("言", "left"): "訁", ("示", "left"): "礻", ("人", "left"): "亻",
    ("刀", "right"): "刂", ("阜", "right"): "阝", ("邑", "right"): "阝",
    ("艸", "top"): "艹", ("竹", "top"): "⺮", ("人", "top"): "𠆢",
    ("爪", "top"): "爫", ("网", "top"): "罒", ("心", "bottom"): "㣺",
    ("火", "bottom"): "灬", ("犬", "left"): "犭", ("食", "left"): "飠",
    ("衣", "left"): "衤", ("糸", "left"): "糹",
}
SVG_GLYPHS = set(VARIANTS.values()) | {"雨"}


def radical_form(char: str, position: str) -> dict[str, str]:
    """題庫使用的偏旁顯示資料；asset 由離線 KAGE 建置流程產生。"""
    display = VARIANTS.get((char, position), char)
    return {
        "char": char,
        "position": position,
        "display": display,
        "asset": f"assets/radicals/u{ord(display):x}.svg",
        "layout": position,
    }
