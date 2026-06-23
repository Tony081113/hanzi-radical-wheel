"""以 KAGE + GlyphWiki dump 離線產生本專案實際使用的偏旁 SVG。

範例：
  git clone https://github.com/HowardZorn/kage-engine C:\tools\kage-engine
  python tools/generate_radical_svgs.py --kage-dir C:\tools\kage-engine --glyphwiki-dump C:\downloads\dump_newest_only.txt
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from radical_forms import ASSET_ROOT, SVG_GLYPHS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="用 KAGE 產生 IDS 偏旁 SVG 資產")
    parser.add_argument("--kage-dir", type=Path, required=True, help="HowardZorn/kage-engine 的本機 clone")
    parser.add_argument("--glyphwiki-dump", type=Path, required=True, help="GlyphWiki 的 dump_newest_only.txt")
    args = parser.parse_args()
    sys.path.insert(0, str(args.kage_dir))
    try:
        from kage import Kage
        from kage.font.sans import Sans
    except ImportError as error:
        raise SystemExit("找不到 KAGE。請確認 --kage-dir 指向 kage-engine clone。") from error

    engine = Kage(ignore_component_version=True)
    engine.font = Sans()
    with args.glyphwiki_dump.open(encoding="utf-8") as source:
        for row in csv.reader(source, delimiter="|"):
            if len(row) >= 3:
                engine.components.push(row[0].strip(), row[2].strip())

    output = ROOT / ASSET_ROOT
    output.mkdir(parents=True, exist_ok=True)
    glyphs = sorted(SVG_GLYPHS)
    for glyph in glyphs:
        engine.make_glyph(name=f"u{ord(glyph):x}").saveas(output / f"u{ord(glyph):x}.svg")
    print(f"已產生 {len(glyphs)} 個 KAGE SVG：{output}")


if __name__ == "__main__":
    main()
