# -*- coding: utf-8 -*-
"""成片逐幀補黑點眉（fallback，2026-08-20）。

背景：場景圖上合成的眉斑撐不過 Wan i2v 前 2 秒（會被「修白」）。
若加粗到 R11/0.06 仍被吃掉，就走這條：直接在生成後的片段上逐幀畫。

原理：
  1. 每幀在頭部搜索窗內找「兩顆最暗的小圓斑」＝眼睛（白毛上的黑眼）
  2. 眉斑位置 = 各眼中心 + 垂直於兩眼連線的偏移（偏移量與點徑都按眼距縮放
     → 頭轉動/遠近時眉斑自然跟隨）
  3. 眼睛偵測結果做 5 幀滑動平均（防抖）；偵測失敗的幀沿用上一幀
  4. 畫法沿用 v3 毛斑（乘暗 0.06 保毛絲 + 噪點邊緣），逐幀 seed 固定不閃爍

用法：python auto\\_paint_dots_video.py <in.mp4> <out.mp4> --search x0,y0,x1,y1
搜索窗給頭部大概範圍（首幀座標），之後逐幀用上一幀眼位擴 60px 當新窗。
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")


def find_eyes(arr, win):
    """在窗內找兩顆暗斑。回 [(x,y),(x,y)]（依 x 排序）或 None。"""
    x0, y0, x1, y1 = win
    g = arr[y0:y1, x0:x1].mean(axis=2)
    th = np.percentile(g, 2.5)          # 最暗 2.5%
    ys, xs = np.where(g <= th)
    if len(xs) < 20:
        return None
    pts = np.stack([xs, ys], axis=1).astype(np.float32)
    # 2-means：以左右極值起始，收斂兩群
    c = np.array([pts[pts[:, 0].argmin()], pts[pts[:, 0].argmax()]], np.float32)
    for _ in range(8):
        d = ((pts[:, None, :] - c[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for k in (0, 1):
            if (lab == k).any():
                c[k] = pts[lab == k].mean(0)
    if abs(c[0][0] - c[1][0]) < 12:      # 兩群黏在一起＝偵測失敗（可能是鼻子）
        return None
    c = c[c[:, 0].argsort()]
    return [(float(c[0][0] + x0), float(c[0][1] + y0)),
            (float(c[1][0] + x0), float(c[1][1] + y0))]


def paint(arr, eyes, rng):
    (lx, ly), (rx, ry) = eyes
    ex, ey = rx - lx, ry - ly
    dist = max(1.0, np.hypot(ex, ey))
    # 垂直向上單位向量（影像 y 向下，眉在眼上方）
    ux, uy = ey / dist, -ex / dist
    if uy > 0:
        ux, uy = -ux, -uy
    off = 0.42 * dist                    # 眼距的 0.42 當眉高（r966 校準比例）
    R = 0.30 * dist                      # 點徑 ~ 眼距 0.30（R11/眼距37 的比例）
    H, W = arr.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    mask = np.zeros((H, W), np.float32)
    for (cx, cy) in [(lx + ux * off, ly + uy * off), (rx + ux * off, ry + uy * off)]:
        ang = np.arctan2(yy - cy, xx - cx)
        wob = 1.0 + 0.08 * np.sin(ang * 8 + 1.7) + 0.05 * np.sin(ang * 3 + 0.9)
        d = np.hypot(xx - cx, yy - cy) / (R * wob)
        mask = np.maximum(mask, np.clip(1.35 - d * 1.35, 0, 1))
    m = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    a = (np.asarray(m, np.float32) / 255.0)[..., None]
    dark = arr * 0.06 + np.array([7, 6, 5], np.float32)
    return arr * (1 - a) + dark * a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--search", required=True, help="首幀頭部窗 x0,y0,x1,y1")
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()
    win0 = tuple(int(v) for v in a.search.split(","))

    td = Path(tempfile.mkdtemp(prefix="dots_"))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.src,
                    str(td / "f_%04d.png")], check=True)
    frames = sorted(td.glob("f_*.png"))
    print(f"{len(frames)} 幀")

    rng = np.random.default_rng(7)
    hist, win, miss = [], win0, 0
    for i, f in enumerate(frames):
        arr = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
        eyes = find_eyes(arr, win)
        if eyes is None:
            miss += 1
            eyes = hist[-1] if hist else None
        if eyes is not None:
            hist.append(eyes)
            sm = np.mean([np.array(e) for e in hist[-5:]], axis=0)  # 5 幀平滑
            eyes_s = [tuple(sm[0]), tuple(sm[1])]
            arr = paint(arr, eyes_s, rng)
            cx = int((eyes_s[0][0] + eyes_s[1][0]) / 2)
            cy = int((eyes_s[0][1] + eyes_s[1][1]) / 2)
            win = (max(0, cx - 90), max(0, cy - 80), cx + 90, cy + 70)
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(f)
        if i % 24 == 0:
            print(f"  {i}/{len(frames)} miss={miss}")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(a.fps),
                    "-i", str(td / "f_%04d.png"),
                    "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
                    a.dst], check=True)
    print(f"✅ 完成 {a.dst}（偵測失敗沿用前幀：{miss} 幀）")


if __name__ == "__main__":
    main()
