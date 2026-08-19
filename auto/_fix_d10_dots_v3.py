# -*- coding: utf-8 -*-
"""d10s1 黑點眉補繪 v3 —— 毛髮質感版（2026-08-19 賢賢回饋後重寫）。

賢賢 8/19 驗收：v2 的實心圓點被 Wan 抹成「塗眉毛」感，裁示不准用畫眉方式。
v3 原理改成「長出來的黑毛斑」：
  1. 不蓋色塊——把圓內原本的毛髮紋理「乘暗」（×0.16），毛絲細節全保留，
     像真的長了一撮黑毛，不是畫上去的顏料
  2. 邊緣用噪點擾動半徑（±18%），毛斑邊緣自然參差，不是幾何正圓
  3. 輕羽化 1.0px 融入周圍白毛

座標對指定場景圖手動格線校準後填入 DOTS。
用法：python auto\\_fix_d10_dots_v3.py <場景圖> <x1,y1> <x2,y2> [半徑]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

src = Path(sys.argv[1])
DOTS = [tuple(int(v) for v in a.split(",")) for a in sys.argv[2:4]]
R = int(sys.argv[4]) if len(sys.argv) > 4 else 8

im = Image.open(src).convert("RGB")
arr = np.asarray(im).astype(np.float32)
H, W = arr.shape[:2]

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
mask = np.zeros((H, W), np.float32)
rng = np.random.default_rng(20260819)
for (cx, cy) in DOTS:
    ang = np.arctan2(yy - cy, xx - cx)
    # 8 瓣低頻噪聲擾動半徑：邊緣參差得像毛，不像圓規畫的
    wob = 1.0 + 0.18 * np.sin(ang * 8 + rng.uniform(0, 6.28)) \
              + 0.10 * np.sin(ang * 3 + rng.uniform(0, 6.28))
    dist = np.hypot(xx - cx, yy - cy) / (R * wob)
    mask = np.maximum(mask, np.clip(1.35 - dist * 1.35, 0, 1))

mask_im = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
mask = np.asarray(mask_im).astype(np.float32)[..., None] / 255.0

# 乘暗保留毛絲：黑毛=原紋理×0.16 再加一點暖底，避免死黑
dark = arr * 0.16 + np.array([9, 7, 6], np.float32)
out = arr * (1 - mask) + dark * mask

bak = src.with_name(src.stem + "_無眉備份.jpg")
if not bak.exists():
    im.save(bak, quality=95)
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(src, quality=95)
print(f"✅ v3 毛斑補繪 → {src.name}  DOTS={DOTS} R={R}（備份：{bak.name}）")
