# -*- coding: utf-8 -*-
"""量角色（主角的頭）在整支片裡有沒有崩壞 —— 給實驗批次用的輕量代理指標。

為什麼需要這支：
    PUBLISH_GATE 的多代理審片一支要燒六十幾萬 token，
    十支實驗片跑不起。但「角色穩不穩」又必須進決策表，
    所以需要一個便宜、可重複、可互相比較的近似值。

⚠️ 這是**代理指標不是 gate**。它抓得到「臉糊掉／融解／細節掉光」這種退化，
   抓不到「多長一條腿」「黑點變三顆」這種需要語意判讀的問題。
   決策表上的角色穩定分數，一律要再用密集幀目視確認過才算數。

三個指標：
    detail_keep  細節保留率：頭部區域的高頻細節（Laplacian 變異數），
                 最後 10% 的畫格相對於最初 10% 的比值。
                 1.0 = 一樣清楚；明顯低於 1 = 臉在糊掉、融解成光滑團塊。
    detail_min   整支片裡最糟的那一段（同樣是相對於開頭的比值）。
    drift        首末幀在頭部區域的結構相似度距離（1 - NCC）。
                 越大 = 末幀的臉離首幀越遠。⚠️ 角色如果有大動作，
                 這個值本來就會大，要跟 motion 一起看，不能單獨判讀。

ROI 是固定框（畫面的 x 30–75%、y 22–50%），因為同一批實驗共用同一張場景圖，
主角起始位置一樣。換場景圖就要重看一次框對不對（用 --roi-check 輸出一張確認圖）。

用法：
    python charstab.py <影片> [<影片2> ...] [--json]
    python charstab.py <影片> --roi-check <輸出.jpg>
"""
import json
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

ROI = (0.30, 0.22, 0.75, 0.50)  # x0, y0, x1, y1（畫面比例）
W = 480  # 分析寬度。要看細節，所以比 flow.py 的 240 大


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def frames(path):
    w, h = probe(path)
    hh = round(h * W / w / 2) * 2
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={W}:{hh}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True).stdout
    n = len(p) // (W * hh)
    a = np.frombuffer(p, np.uint8)[:n * W * hh].reshape(n, hh, W)
    x0, y0, x1, y1 = ROI
    return a[:, int(hh * y0):int(hh * y1), int(W * x0):int(W * x1)]


def ncc(a, b):
    a = a.astype(np.float64) - a.mean()
    b = b.astype(np.float64) - b.mean()
    d = np.sqrt((a ** 2).sum() * (b ** 2).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def analyse(path):
    roi = frames(path)
    if len(roi) < 10:
        return None
    lap = np.array([cv2.Laplacian(f, cv2.CV_64F).var() for f in roi])
    k = max(1, len(lap) // 10)
    head = float(lap[:k].mean())
    if head <= 0:
        return None
    # 用滑動窗口找最糟的一段，避免被單一格的雜訊決定
    win = np.convolve(lap, np.ones(k) / k, mode="valid")
    return {
        "file": str(path).split("\\")[-1],
        "detail_keep": round(float(lap[-k:].mean()) / head, 3),
        "detail_min": round(float(win.min()) / head, 3),
        "drift": round(1.0 - ncc(roi[0], roi[-1]), 3),
    }


if __name__ == "__main__":
    if "--roi-check" in sys.argv:
        i = sys.argv.index("--roi-check")
        src, dst = sys.argv[1], sys.argv[i + 1]
        x0, y0, x1, y1 = ROI
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf",
                        f"select=eq(n\\,0),drawbox=x=iw*{x0}:y=ih*{y0}:"
                        f"w=iw*{x1 - x0}:h=ih*{y1 - y0}:color=red@0.9:t=6,scale=360:-1",
                        "-frames:v", "1", dst], check=True)
        print("saved", dst)
        sys.exit(0)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    out = [r for r in (analyse(p) for p in args) if r]
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(f"{'檔案':<28}{'細節保留':>9}{'最糟':>8}{'首末漂移':>9}")
        for r in out:
            print(f"{r['file']:<28}{r['detail_keep']:>9}{r['detail_min']:>8}{r['drift']:>9}")
