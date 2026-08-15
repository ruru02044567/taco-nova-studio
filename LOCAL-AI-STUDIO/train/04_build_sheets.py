# -*- coding: utf-8 -*-
"""把測試圖排成對照表：每個情境一列，橫向是訓練步數。

排成這樣才看得出「多訓練是變好還是變壞」——
單獨看一張圖只知道好不好看，看不出趨勢。

用法：python 04_build_sheets.py --who nova
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True)
    ap.add_argument("--seed", default="424242")
    args = ap.parse_args()

    root = HERE / f"test_{args.who}"
    cols = sorted([d for d in root.iterdir() if d.is_dir()])
    if not cols:
        print("找不到測試圖")
        return 1

    # 收集所有情境名稱
    scenes = sorted({p.name.rsplit("_seed", 1)[0]
                     for d in cols for p in d.glob("*.png")})
    print(f"{len(scenes)} 個情境 × {len(cols)} 個 checkpoint")

    TH, PAD, HDR = 420, 8, 34
    sheets = []
    for sc in scenes:
        tiles = []
        for d in cols:
            hits = sorted(d.glob(f"{sc}_seed{args.seed}.png")) or sorted(d.glob(f"{sc}_seed*.png"))
            if hits:
                im = Image.open(hits[0]).convert("RGB")
                tiles.append((d.name, im.resize((int(im.width * TH / im.height), TH))))
        if not tiles:
            continue
        W = sum(t[1].width for t in tiles) + PAD * (len(tiles) + 1)
        row = Image.new("RGB", (W, TH + HDR + PAD * 2), (24, 24, 24))
        dr = ImageDraw.Draw(row)
        dr.text((PAD, 6), f"{args.who}  /  {sc}", fill=(255, 220, 120))
        x = PAD
        for name, im in tiles:
            row.paste(im, (x, HDR + PAD))
            dr.text((x + 4, HDR - 12), name, fill=(150, 200, 255))
            x += im.width + PAD
        sheets.append(row)
        print(f"   {sc}  ({len(tiles)} 格)")

    W = max(s.width for s in sheets)
    H = sum(s.height for s in sheets)
    big = Image.new("RGB", (W, H), (24, 24, 24))
    y = 0
    for s in sheets:
        big.paste(s, (0, y)); y += s.height
    out = root / f"_COMPARE_{args.who}.jpg"
    big.save(out, quality=86)
    print(f"\n✅ {out}  {big.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
