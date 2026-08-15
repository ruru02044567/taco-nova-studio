# -*- coding: utf-8 -*-
"""用光流量一支片的「動作幅度」與「流暢度」。

為什麼不能只用 momentum.py：
    momentum 量的是「相鄰畫面的像素差」，它分不出兩件完全不同的事 ——
    (A) 狗真的甩了一下身體（畫面差很大，但是好的）
    (B) 狗的臉在原地融解、閃爍、抖動（畫面差也很大，但是壞的）
    D6/D7 六支候選片的動量數字都在同一個區間，賢賢卻說「不會動、不流暢」。
    這支工具就是為了把 (A) 和 (B) 分開。

四個指標（都用同一套演算法，可以互相比較）：

    motion   動作幅度：每一格畫面裡的東西平均移動了幾 % 的畫面寬度。
             越大＝動作越大。「站著不動」大約 0.05 以下。
    peak     動作峰值（95 分位）：最大的那一下有多大。
    jerk     速度抖動：相鄰兩格之間「速度變化量」的平均，除以平均速度。
             越小越順。真實運動是連續加速減速，jerk 低；
             一格衝一下、下一格停住的跳格感，jerk 高。
    flow_ok  光流解釋率：把前一格照光流「搬」到後一格的位置之後，還剩多少誤差。
             ⭐ 這是最關鍵的一個。1.0 = 畫面的變化 100% 是「東西移動」造成的；
             數字低 = 畫面在變，但不是因為移動 —— 就是融解、閃爍、材質重畫。
             賢賢說的「不流暢」，技術上多半是這一項低。

用法：
    python flow.py <影片> [<影片2> ...]        逐支列印明細＋摘要
    python flow.py --json <影片> [...]         只輸出一行 JSON（給批次腳本收集用）
"""
import json
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

W = 240  # 分析寬度。太大只是慢，光流看的是構圖層級的位移


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(num) / float(den)


def frames(path, w, h):
    """用 ffmpeg 解碼成灰階原始畫格。

    刻意不用 cv2.VideoCapture：這台機器的路徑有中文又有空格，
    OpenCV 讀中文路徑會靜默失敗（回傳空的，不報錯），ffmpeg 沒這個問題。
    """
    hh = round(h * W / w / 2) * 2
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", f"scale={W}:{hh}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True).stdout
    n = len(p) // (W * hh)
    return np.frombuffer(p, np.uint8)[:n * W * hh].reshape(n, hh, W), hh


def analyse(path):
    w, h, fps = probe(path)
    arr, hh = frames(path, w, h)
    if len(arr) < 3:
        return None

    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32),
                         np.arange(hh, dtype=np.float32))

    mags, oks, prev_flow = [], [], None
    cohs = []
    for i in range(1, len(arr)):
        a, b = arr[i - 1], arr[i]
        flow = cv2.calcOpticalFlowFarneback(a, b, None,
                                            0.5, 3, 15, 3, 5, 1.2, 0)
        mag = float(np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2).mean())
        mags.append(mag / W * 100)  # 換算成畫面寬度的百分比

        # 光流解釋率：把 b 依照光流搬回 a 的位置，看還剩多少對不上。
        # ⚠️ 方向很容易搞反：Farneback 的 flow(x) 是「a 的第 x 格像素跑到 b 的哪裡」，
        # 所以要 remap(b, x+flow) 才會還原成 a。反過來寫會算出負的解釋率（第一版就是這樣）。
        warped = cv2.remap(b, gx + flow[..., 0], gy + flow[..., 1],
                           cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        raw = float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())
        res = float(np.abs(warped.astype(np.int16) - a.astype(np.int16)).mean())
        oks.append(1.0 - res / raw if raw > 0.5 else 1.0)

        # 方向一致性：這一格的光流跟上一格像不像（用強度加權，不然靜止區的雜訊會主導）
        if prev_flow is not None:
            d = (flow[..., 0] * prev_flow[..., 0] + flow[..., 1] * prev_flow[..., 1])
            n1 = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            n2 = np.sqrt(prev_flow[..., 0] ** 2 + prev_flow[..., 1] ** 2)
            wgt = n1 * n2
            if wgt.sum() > 1e-6:
                cohs.append(float((d / (n1 * n2 + 1e-6) * wgt).sum() / wgt.sum()))
        prev_flow = flow

    m = np.array(mags)
    jerk = float(np.abs(np.diff(m)).mean() / max(m.mean(), 1e-6))
    return {
        "file": str(path).split("\\")[-1],
        "sec": round(len(arr) / fps, 2),
        "frames": len(arr),
        "motion": round(float(m.mean()), 4),
        "peak": round(float(np.percentile(m, 95)), 4),
        "peak_at": round(float((int(m.argmax()) + 1) / fps), 2),
        "jerk": round(jerk, 3),
        "coherence": round(float(np.mean(cohs)) if cohs else 0.0, 3),
        "flow_ok": round(float(np.mean(oks)), 3),
        "_curve": [round(float(x), 3) for x in m],
        "_fps": fps,
    }


def show(r):
    print(f"\n=== {r['file']}  {r['sec']}秒 / {r['frames']}格 ===")
    fps = r["_fps"]
    step = max(1, int(round(fps / 4)))  # 每 0.25 秒印一列，跟 momentum.py 對齊
    c = r["_curve"]
    print(" 時間   動作幅度")
    for i in range(0, len(c), step):
        v = float(np.mean(c[i:i + step]))
        print(f"{(i + 1) / fps:5.2f}s  {v:6.3f}  {'#' * int(v * 20)}")
    print(f"\n  動作幅度 motion   {r['motion']:.4f}  （站著不動 ≈ 0.05 以下）")
    print(f"  動作峰值 peak     {r['peak']:.4f}  @ {r['peak_at']}s")
    print(f"  速度抖動 jerk     {r['jerk']:.3f}  （越小越順）")
    print(f"  方向一致 coherence{r['coherence']:.3f}  （越接近 1 越像真實運動）")
    print(f"  光流解釋 flow_ok  {r['flow_ok']:.3f}  ⭐（低＝畫面在變但不是在動＝融解閃爍）")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)
    out = []
    for p in args:
        r = analyse(p)
        if r is None:
            print(f"FAILED: 抽不到足夠的影格 {p}")
            continue
        out.append(r)
        if not as_json:
            show(r)
    if as_json:
        for r in out:
            r.pop("_curve", None)
            r.pop("_fps", None)
        print(json.dumps(out, ensure_ascii=False))
