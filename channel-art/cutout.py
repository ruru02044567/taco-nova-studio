# -*- coding: utf-8 -*-
"""把兩隻狗從客廳背景去背，輸出透明 PNG 給 banner 用

處理三件事：
1. 去背（isnet 模型，對毛髮比 u2net 乾淨）
2. alpha 內縮一圈，消掉去背常見的白邊
3. 底部淡出，讓狗自然融進 banner 背景，不會有硬切斷的橫線
"""
from PIL import Image, ImageFilter
from rembg import remove, new_session
from pathlib import Path

OUT = Path(__file__).resolve().parent / "assets"
session = new_session("isnet-general-use")


def clean_alpha(img, fade=0.22, erode=5):
    """去白邊 + 底部淡出

    erode 是關鍵：淺色背景（米色牆）去背後邊緣會留一圈白，
    alpha 往內縮幾 px 才吃得掉，不然放在深色 banner 上像貼紙外框。
    """
    a = img.getchannel("A").filter(ImageFilter.MinFilter(erode))
    a = a.filter(ImageFilter.GaussianBlur(1.0))                # 邊緣柔一點
    w, h = img.size
    start = int(h * (1 - fade))
    px = a.load()
    for y in range(start, h):
        k = 1 - (y - start) / max(1, h - start)
        for x in range(w):
            px[x, y] = int(px[x, y] * k)
    img.putalpha(a)
    return img


def cut(src, dst, flip=False, keep_top=1.0, fade=0.22, erode=5):
    img = Image.open(OUT / src).convert("RGB")
    out = remove(img, session=session, post_process_mask=True)
    if keep_top < 1.0:                       # 砍掉畫面下緣的雜物（狗床、另一隻狗的耳朵）
        w, h = out.size
        out = out.crop((0, 0, w, int(h * keep_top)))
    if flip:
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    out = out.crop(out.getbbox())
    out = clean_alpha(out, fade, erode)
    out.save(OUT / dst)
    print(dst, out.size)


cut("taco-full.jpg", "taco-cut.png", fade=0.20, erode=3)
# Nova：頭要留完整（切到吻部會很怪），身體改用長一點的淡出收掉
cut("nova-full.jpg", "nova-cut.png", flip=True, keep_top=0.88, fade=0.38, erode=7)
