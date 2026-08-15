# -*- coding: utf-8 -*-
"""EXP-07 附件：Nova 眼睛高倍放大（目視仲裁用）

背景：主判讀者目視認為「無 IPA、LoRA 0.15」是雙眼藍，
但 10 位獨立盲評員的像素取樣說是異色瞳（一藍一棕）。
這一格決定 PUBLISH_GATE「明顯藍眼」過不過，所以拉高倍放大並排比對。

**結果：盲評正確，四張無 IPA 全是異色瞳（畫面左眼棕、右眼藍）。**

> ⚠️ 本腳本第一版還輸出過一組 B−R（藍減紅）統計，已移除。
> 那組數字是錯的：眼部框太大，5000+ 個「暗像素」大多是毛髮陰影與鼻子而非虹膜，
> 白點框也沒落在白毛上（白點偏移 -49 明顯異常），
> 導致有 IPA 的棕眼反而算出更高的「偏藍」值。
> 要做客觀量測必須先精準定位虹膜，不能用整塊眼部帶狀區。

用法：python 28_eye_zoom.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "noipa_sweep"

# 眼部帶狀區（相對座標，涵蓋兩眼）
EYE_BOX = (0.62, 0.07, 0.92, 0.19)

CASES = [
    ("無IPA w0.00", OUT / "w0.00.png"),
    ("無IPA w0.15", OUT / "w0.15.png"),
    ("無IPA w0.25", OUT / "w0.25.png"),
    ("無IPA w0.35", OUT / "w0.35.png"),
    ("有IPA w0.15", HERE / "sweep_V2" / "w0.15.png"),
    ("有IPA w0.25", HERE / "sweep_V2" / "w0.25.png"),
]


def crop(im, box):
    W, H = im.size
    return im.crop((int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)))


def main():
    rows = []
    ZH = 260
    for label, path in CASES:
        if not path.exists():
            print(f"缺 {path}")
            continue
        c = crop(Image.open(path).convert("RGB"), EYE_BOX)
        rows.append((label, c.resize((int(c.width * ZH / c.height), ZH), Image.LANCZOS)))

    if not rows:
        return 1

    W = max(c.width for _, c in rows)
    sheet = Image.new("RGB", (W, (ZH + 26) * len(rows)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    y = 0
    for label, c in rows:
        sheet.paste(c, (0, y + 22))
        d.text((4, y + 5), label, fill=(255, 220, 120))
        y += ZH + 26
    p = OUT / "_EYE_ZOOM.jpg"
    sheet.save(p, quality=96)
    print(f"✅ {p}\n（目視判定，本腳本不輸出色彩數值——原因見檔頭）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
