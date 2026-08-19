# -*- coding: utf-8 -*-
"""d10s1 場景圖黑點眉補繪（一次性 production fix，2026-08-19）。

背景：FLUX seed 101 的場景圖角色數正確、構圖成立，但黑點眉完全沒生出來
（FLUX 生不出黑點眉是已知限制，見 local-video-engine-benchmark-findings）。
比照 _fix_d9_dots.py 的作法：格線放大圖手動校準座標後，在兩眼正上方
畫兩顆同尺寸實心近黑圓點（羽化邊緣融入毛色）。

座標是對 d10s1_scene_c101.jpg（704×1280）手動校準的，不通用。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

CLIPS = Path(__file__).parent / "clips"
SRC = CLIPS / "d10s1_scene.jpg"          # 由 c101 升級而來
BAK = CLIPS / "d10s1_scene_原版無眉.jpg"

# ---- 座標（704×1280 原圖，格線圖校準）----
# 眼睛中心約 (285,508) 與 (335,507)；點畫在眉骨正上方（眼上 ~16px）
DOTS = [(284, 491), (336, 491)]
R = 8   # 發布基準：點徑約眼寬 0.8 倍（眼寬 ~20px）

im = Image.open(SRC).convert("RGB")
print("size:", im.size)

layer_mask = Image.new("L", im.size, 0)
ld = ImageDraw.Draw(layer_mask)
for (x, y) in DOTS:
    ld.ellipse([x - R, y - R, x + R, y + R], fill=235)
layer_mask = layer_mask.filter(ImageFilter.GaussianBlur(1.2))
dark = Image.new("RGB", im.size, (24, 22, 22))
im = Image.composite(dark, im, layer_mask)

if not BAK.exists():
    Image.open(SRC).save(BAK, quality=95)
im.save(SRC, quality=95)
print("✅ 補繪完成 →", SRC.name, "（原版備份：", BAK.name, "）")
