# -*- coding: utf-8 -*-
"""d9s1 場景圖黑點眉補繪（一次性production fix，2026-08-18）。

背景：d9s1_scene.jpg（Gemini 08-10 生成）的黑點眉又小又高又不對稱，
Wan i2v 忠實還原了這個弱點，成片的招牌特徵明顯低於已發布基準
（d8s1 發布版的黑點又大又圓）。重抽影片種子救不了起始圖的問題，
所以直接在場景圖上補繪，再重生影片。

作法：在兩眼正上方畫兩顆同尺寸實心近黑圓點（含輕微羽化邊緣融入毛色），
並把原本高位的弱點用周圍毛色蓋掉。座標是對這張圖手動校準的，不通用。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(__file__).parent / "clips" / "d9s1_scene.jpg"
BAK = SRC.with_name("d9s1_scene_原版弱點眉.jpg")

im = Image.open(SRC).convert("RGB")
W, H = im.size
print("size:", im.size)

# ---- 座標（572×1024 原圖上手動校準，v2：v1 點畫太高跑到頭頂）----
# 眼睛中心約 (324,410) 與 (379,408)；點畫在眉骨正上方（眼上 ~15px）
DOTS = [(321, 394), (376, 391)]   # 兩顆新點的圓心
R = 8                              # 半徑（發布基準的點約佔眼寬 0.8 倍）
OLD = [(326, 377), (366, 380)]     # 原本的弱點位置（要蓋掉）

# 1) 蓋掉原弱點：各自取「正上方毛色」局部填色，小範圍羽化
cover = im.copy()
d = ImageDraw.Draw(cover)
for (x, y) in OLD:
    local = im.getpixel((x, y - 14))
    d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=local)
mask = Image.new("L", im.size, 0)
dm = ImageDraw.Draw(mask)
for (x, y) in OLD:
    dm.ellipse([x - 10, y - 10, x + 10, y + 10], fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(2))
im = Image.composite(cover, im, mask)

# 2) 畫新點：實心近黑圓，邊緣輕羽化
layer = Image.new("RGB", im.size, (0, 0, 0))
lm = Image.new("L", im.size, 0)
ld = ImageDraw.Draw(lm)
for (x, y) in DOTS:
    ld.ellipse([x - R, y - R, x + R, y + R], fill=235)
lm = lm.filter(ImageFilter.GaussianBlur(1.2))
dark = Image.new("RGB", im.size, (24, 22, 22))
im = Image.composite(dark, im, lm)

if not BAK.exists():
    Image.open(SRC).save(BAK, quality=95)
im.save(SRC, quality=95)
print("✅ 補繪完成 →", SRC.name, "（原版備份：", BAK.name, "）")
