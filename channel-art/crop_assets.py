# -*- coding: utf-8 -*-
"""從角色定裝照裁出頻道美術要用的素材（頭像臉部、banner 用的雙狗）"""
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path

BASE = Path(__file__).resolve().parent
CHAR = BASE.parent / "character"
OUT = BASE / "assets"
OUT.mkdir(exist_ok=True)


def punch(img, sharp=1.25, color=1.08, contrast=1.06):
    img = ImageEnhance.Sharpness(img).enhance(sharp)
    img = ImageEnhance.Color(img).enhance(color)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    return img


def crop(src, box, out, size=None):
    img = Image.open(CHAR / src).convert("RGB").crop(box)
    if size:
        img = img.resize(size, Image.LANCZOS)
    img = punch(img)
    img.save(OUT / out, quality=96)
    print(out, img.size)


# 頭像：Taco 臉部特寫（v5-max 極限機歪臉）
crop("taco-ref-v5-max.jpg", (95, 215, 475, 595), "taco-face.jpg", (1000, 1000))

# banner：Taco 頭＋上半身（含藍項圈辨識物）
crop("taco-ref-v5-max.jpg", (60, 225, 520, 730), "taco-full.jpg", (920, 1010))

# banner：Nova 哈士奇頭＋胸（避開左下角的狗床與 Taco）
crop("duo-scene-dogbed.jpg", (322, 90, 572, 555), "nova-full.jpg", (750, 1395))
