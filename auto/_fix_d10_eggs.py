# -*- coding: utf-8 -*-
"""d10s1 場景圖蛋証合成（2026-08-19 第三輪）。

驗證面板抓到：畫面 0 顆蛋，黃液被冷讀成「尿一灘／打翻顏料」，
PUBLISH_GATE 規則 6/10 不成立。修法＝把「蛋」合成回 r966：
  1. r855 的滿蛋開盒紙盤 蓋掉 r966 的空盤（同為白床單暖光，羽化融邊）
  2. c101 的半顆蛋黃殼 ×2 放在蛋黃灘邊（一顆鏡像縮放避免複製感）
亮度用目標區均值校正；每個貼片下加淡橢圓陰影。

用法：python auto\_fix_d10_eggs.py  （就地改 auto\clips\d10s1_scene.jpg）
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")
CLIPS = Path(__file__).parent / "clips"
DST = CLIPS / "d10s1_scene.jpg"


def paste_polygon(base, patch, box, poly, feather=4, match_target=None):
    """緊裁多邊形貼片：poly 是 patch 原始座標系的頂點，貼時同步縮放。"""
    W, H = box[2] - box[0], box[3] - box[1]
    sx, sy = W / patch.width, H / patch.height
    p = patch.resize((W, H), Image.LANCZOS)
    if match_target:
        tt = np.asarray(base.crop(match_target), np.float32)
        s = np.asarray(p, np.float32)
        tm = tt[tt.mean(axis=2) > 170].mean(axis=0) if (tt.mean(axis=2) > 170).any() else tt.mean((0, 1))
        sm = s[s.mean(axis=2) > 170].mean(axis=0) if (s.mean(axis=2) > 170).any() else s.mean((0, 1))
        p = Image.fromarray(np.clip(s * (tm / np.maximum(sm, 1)), 0, 255).astype(np.uint8))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(x * sx, y * sy) for (x, y) in poly], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    base.paste(p, box[:2], mask)


def paste_feathered(base, patch, box, feather=10, match_target=None):
    """patch 貼進 base 的 box，邊緣羽化；match_target=(x0,y0,x1,y1) 取樣做亮度匹配。"""
    W, H = box[2] - box[0], box[3] - box[1]
    p = patch.resize((W, H), Image.LANCZOS)
    if match_target:
        t = np.asarray(base.crop(match_target), np.float32)
        s = np.asarray(p, np.float32)
        # 用高亮區（床單）估增益，避免被蛋殼顏色帶偏
        tm = t[t.mean(axis=2) > 170].mean(axis=0) if (t.mean(axis=2) > 170).any() else t.mean((0, 1))
        sm = s[s.mean(axis=2) > 170].mean(axis=0) if (s.mean(axis=2) > 170).any() else s.mean((0, 1))
        p = Image.fromarray(np.clip(s * (tm / np.maximum(sm, 1)), 0, 255).astype(np.uint8))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([feather, feather, W - feather, H - feather],
                                           radius=feather * 2, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather * 0.8))
    base.paste(p, box[:2], mask)


def drop_shadow(base, cx, cy, rx, ry, alpha=60):
    sh = Image.new("L", base.size, 0)
    ImageDraw.Draw(sh).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    dark = Image.new("RGB", base.size, (60, 50, 40))
    base.paste(dark, (0, 0), sh)


im = Image.open(DST).convert("RGB")

# ── 0) 先用床單布料把舊空盤整塊擦掉（不然羽化邊會透出鬼影）──
sheet = im.crop((150, 850, 410, 1010)).resize((280, 175), Image.LANCZOS)
mask0 = Image.new("L", (280, 175), 0)
ImageDraw.Draw(mask0).rounded_rectangle([8, 8, 272, 167], radius=20, fill=255)
mask0 = mask0.filter(ImageFilter.GaussianBlur(7))
im.paste(sheet, (392, 440), mask0)

# ── 1) 滿蛋紙盒貼上去（r966 空盤原位 (408,455)-(650,597)）──
carton_src = Image.open(CLIPS / "d10s1_scene_r855.jpg").crop((30, 440, 260, 620))
box = (400, 448, 660, 606)
drop_shadow(im, (box[0] + box[2]) // 2, box[3] - 26, 100, 14, alpha=45)
CARTON_POLY = [(22, 74), (136, 10), (200, 48), (210, 120), (160, 172), (38, 136)]
paste_polygon(im, carton_src, box, CARTON_POLY, feather=4, match_target=(395, 430, 668, 620))

# ── 2) 半顆蛋黃殼 ×2（c101 半殼 (500,635)-(560,682)）──
half_src = Image.open(CLIPS / "d10s1_scene_c101.jpg").crop((500, 635, 560, 682))
# 2a. 蛋黃灘左緣（Taco 左前方）
drop_shadow(im, 138, 762, 26, 7, alpha=50)
paste_feathered(im, half_src, (108, 726, 168, 773), feather=6, match_target=(100, 715, 180, 785))
# 2b. 蛋黃灘右下緣，鏡像+縮小 85%
half2 = half_src.transpose(Image.FLIP_LEFT_RIGHT)
drop_shadow(im, 452, 1010, 22, 6, alpha=50)
paste_feathered(im, half2, (426, 978, 478, 1018), feather=5, match_target=(415, 965, 490, 1030))

im.save(DST, quality=95)
print("✅ 蛋証合成完成 →", DST.name)
