# -*- coding: utf-8 -*-
r"""postfx.py — 場景圖後製一支搞定（2026-08-19 建立，取代零散的 _fix_*_dots*.py）

兩件事合併：
  A. 黑點眉補繪（v3 乘暗毛斑法，賢賢 8/19 裁示：禁塗眉感、係數 0.08–0.10）
     —— 座標仍要人工格線校準，跟 _fix_d10_dots_v3.py 同款演算法
  B. 相機缺陷後製（BENCHMARK 08-exp-realism 結論：顆粒／色差／JPEG 痕跡
     這類「相機行為」FLUX 畫不出來，只能後製加；同時壓掉 AI 光滑感）

用法：
  只補相機缺陷（最常用，gen_scene_flux 出圖後接著跑）：
    python auto\postfx.py clips\d10s1_scene.png
  連黑點眉一起補：
    python auto\postfx.py clips\d10s1_scene.png --dots 402,371 466,368 --radius 8
  只補眉不加缺陷：
    python auto\postfx.py clips\d10s1_scene.png --dots 402,371 466,368 --no-camera
  調強度：
    --grain 6（顆粒 σ，0=關）  --ca 1.0（色差位移 px，0=關）  --jpeg 80（壓縮質感，0=關）

原圖自動備份成 <名>_原圖備份.png，重跑前會從備份還原，所以本腳本可安全重跑（冪等）。
影片要壓光滑感另走 ffmpeg：-vf "noise=alls=6:allf=t+u"（這支只管靜態圖）。
"""
import argparse
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def draw_dots(arr: np.ndarray, dots, radius: int, seed: int) -> np.ndarray:
    """v3 乘暗毛斑法：不蓋色塊，把圓內毛髮紋理乘暗（×0.09），邊緣噪聲擾動＋輕羽化。"""
    H, W = arr.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    mask = np.zeros((H, W), np.float32)
    rng = np.random.default_rng(seed)
    for (cx, cy) in dots:
        ang = np.arctan2(yy - cy, xx - cx)
        # 8 瓣低頻噪聲擾動半徑：邊緣參差得像毛，不像圓規畫的
        wob = 1.0 + 0.18 * np.sin(ang * 8 + rng.uniform(0, 6.28)) \
                  + 0.10 * np.sin(ang * 3 + rng.uniform(0, 6.28))
        dist = np.hypot(xx - cx, yy - cy) / (radius * wob)
        mask = np.maximum(mask, np.clip(1.35 - dist * 1.35, 0, 1))
    mask_im = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    mask = np.asarray(mask_im).astype(np.float32)[..., None] / 255.0
    # 乘暗保留毛絲：黑毛=原紋理×0.09 再加一點暖底，避免死黑（裁示區間 0.08–0.10）
    dark = arr * 0.09 + np.array([8, 6, 5], np.float32)
    return arr * (1 - mask) + dark * mask


def chromatic_aberration(arr: np.ndarray, px: float) -> np.ndarray:
    """R 往右、B 往左各平移 px 像素——廉價手機鏡頭的橫向色差。"""
    s = max(1, int(round(px)))
    out = arr.copy()
    out[:, s:, 0] = arr[:, :-s, 0]   # R 右移
    out[:, :-s, 2] = arr[:, s:, 2]   # B 左移
    return out


def add_grain(arr: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    """感光元件噪點：亮度越暗噪越明顯（陰影噪點），壓 AI 光滑感的主力。"""
    rng = np.random.default_rng(seed + 1)
    lum = arr.mean(axis=2, keepdims=True) / 255.0
    weight = 0.6 + 0.8 * (1.0 - lum)          # 暗部 1.4 倍、亮部 0.6 倍
    noise = rng.normal(0, sigma, arr.shape).astype(np.float32) * weight
    return arr + noise


def jpeg_roundtrip(im: Image.Image, quality: int) -> Image.Image:
    """壓一輪 JPEG 再解回來，留下 8x8 區塊痕跡。"""
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="場景圖路徑（就地覆寫，原圖自動備份）")
    ap.add_argument("--dots", nargs=2, metavar="x,y",
                    help="黑點眉兩顆座標，例：--dots 402,371 466,368（不給就不補眉）")
    ap.add_argument("--radius", type=int, default=8, help="毛斑半徑 px（預設 8）")
    ap.add_argument("--no-camera", action="store_true", help="不加相機缺陷（只補眉）")
    ap.add_argument("--grain", type=float, default=5.0, help="顆粒強度 σ（預設 5，0=關）")
    ap.add_argument("--ca", type=float, default=1.0, help="色差位移 px（預設 1，0=關）")
    ap.add_argument("--jpeg", type=int, default=82, help="JPEG 痕跡質量（預設 82，0=關）")
    ap.add_argument("--seed", type=int, default=20260819)
    args = ap.parse_args()

    src = Path(args.image)
    if not src.exists():
        print(f"[X] 找不到圖：{src}")
        sys.exit(1)
    if not args.dots and args.no_camera:
        print("[X] 眉也不補、缺陷也不加，沒事可做")
        sys.exit(1)

    # 冪等：有備份就從備份讀（代表之前跑過），沒有就先備份
    bak = src.with_name(src.stem + "_原圖備份.png")
    if bak.exists():
        im = Image.open(bak).convert("RGB")
        print(f"[i] 從備份還原重做：{bak.name}")
    else:
        im = Image.open(src).convert("RGB")
        im.save(bak)
        print(f"[i] 原圖已備份：{bak.name}")

    arr = np.asarray(im).astype(np.float32)
    done = []

    if args.dots:
        dots = [tuple(int(v) for v in d.split(",")) for d in args.dots]
        arr = draw_dots(arr, dots, args.radius, args.seed)
        done.append(f"黑點眉 v3 毛斑 {dots} R={args.radius}")

    if not args.no_camera:
        if args.ca > 0:
            arr = chromatic_aberration(arr, args.ca)
            done.append(f"色差 {args.ca}px")
        if args.grain > 0:
            arr = add_grain(arr, args.grain, args.seed)
            done.append(f"顆粒 σ={args.grain}")

    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if not args.no_camera and args.jpeg > 0:
        out = jpeg_roundtrip(out, args.jpeg)
        done.append(f"JPEG 痕跡 q={args.jpeg}")

    out.save(src)
    print(f"[ok] {src.name} ← " + "＋".join(done))


if __name__ == "__main__":
    main()
