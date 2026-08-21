# -*- coding: utf-8 -*-
r"""measure.py — 實驗用客觀量測（2026-08-21 建立）

## 為什麼要有這支

現有的 `score_video.py` 量的是「成片規格」（片長、音量、鏡頭數），
量不到「接龍到底有沒有比較穩」這種段落層級的東西。
而 8/20 和 8/21 兩次接龍實測的結論全部是**用眼睛看四張幀圖**下的 ——
看得出「崩沒崩」，看不出「哪一組比較不崩」。5 組 anchor 掃描要排名次，
沒有數字就只能靠印象，那跟沒做實驗一樣。

所以這支把「量得出來的」全部變成數字，**量不出來的老實承認量不出來**
（第三條腿、增生第二隻狗、黑點眉在不在 —— 那些交給 auto\frame_gate.py 的人眼硬閘門）。

## 只用現成套件

系統 Python 3.13 已經有 numpy / PIL / cv2 / scipy / skimage，一個都不用裝。
影格一律走 `ffmpeg -f rawvideo` 管進 numpy，不落地暫存檔。

## 中文路徑坑

ffmpeg 碰中文路徑會**靜默失敗**（回空 stdout、returncode 0），所以所有讀檔
一律先 copy 到英文暫存目錄再處理。這是這台機器已知的坑，不是防禦性編程。
"""
import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FPS = 24


# ────────────────────────── 基礎讀檔 ──────────────────────────

@contextmanager
def ascii_copy(path):
    """把可能含中文的路徑複製到純英文暫存路徑再交給 ffmpeg。"""
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix="meas_") as td:
        dst = Path(td) / ("v" + path.suffix)
        shutil.copy2(path, dst)
        yield dst


def probe(path):
    """回 dict：width / height / nb_frames / duration。"""
    with ascii_copy(path) as v:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=width,height,nb_read_frames",
             "-show_entries", "format=duration", "-of", "json", str(v)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        d = json.loads(p.stdout or "{}")
    st = (d.get("streams") or [{}])[0]
    return {
        "width": int(st.get("width", 0)),
        "height": int(st.get("height", 0)),
        "frames": int(st.get("nb_read_frames", 0) or 0),
        "duration": float((d.get("format") or {}).get("duration", 0) or 0),
    }


def read_frames(path, start=0, n=None, scale=None, gray=False):
    """讀影格成 (N, H, W, 3) uint8（gray=True 時 (N, H, W)）。

    scale 給 (w, h) 會先縮小 —— 光流與直方圖不需要全解析度，縮到 176x320
    可以快 16 倍，而且對這幾個指標的結論沒有影響（都是統計量不是細節）。
    """
    with ascii_copy(path) as v:
        vf = []
        if start or n:
            end = f":end_frame={start + n}" if n else ""
            vf.append(f"trim=start_frame={start}{end},setpts=N/{FPS}/TB")
        if scale:
            vf.append(f"scale={scale[0]}:{scale[1]}")
        cmd = ["ffmpeg", "-v", "error", "-i", str(v)]
        if vf:
            cmd += ["-vf", ",".join(vf)]
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    if not raw:
        raise RuntimeError(f"讀不到影格（ffmpeg 回空）：{path}")
    if scale:
        w, h = scale
    else:
        info = probe(path)
        w, h = info["width"], info["height"]
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w, 3)
    if gray:
        # BT.601 灰階；比 arr.mean(3) 準，因為人眼對綠色最敏感
        arr = (arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114).astype(np.uint8)
    return arr


# ────────────────────────── 指標 ──────────────────────────

def frame_deltas(gray):
    """相鄰幀的逐像素平均絕對差，回長度 N-1 的陣列。

    這是所有「接縫看不看得出來」判斷的基準單位：接縫處的差值要跟
    段內正常相鄰幀的差值比，比出來的倍數才有意義。
    8/20 量到的參考值：段內正常跳動 1.58、✅ 接法 2.68、❌ 接法 8.58、硬接 24.56。
    """
    a = gray[:-1].astype(np.float32)
    b = gray[1:].astype(np.float32)
    return np.abs(b - a).mean(axis=(1, 2))


def seam_ratio(video, cut_frames):
    """接縫幀差 ÷ 段內正常幀差。1.0 = 跟正常跳動一樣，肉眼絕對看不出來。

    cut_frames：接縫落在第幾格（新段的第一格 index）。
    回 dict：每個接縫的差值、基準線、倍數。
    """
    g = read_frames(video, scale=(176, 320), gray=True)
    d = frame_deltas(g)
    cuts = [c for c in cut_frames if 1 <= c <= len(d)]
    mask = np.ones(len(d), bool)
    for c in cuts:
        # 接縫前後各一格排除在基準線外，免得接縫自己把基準線拉高
        mask[max(0, c - 2):c + 1] = False
    base = float(np.median(d[mask])) if mask.any() else float(np.median(d))
    out = {"baseline": round(base, 3), "seams": []}
    for c in cuts:
        v = float(d[c - 1])
        out["seams"].append({"frame": c, "delta": round(v, 3),
                             "ratio": round(v / base, 2) if base > 0 else None})
    return out


def anchor_fidelity(fed_video, gen_video, anchor):
    """接龍專用：生成結果的前 anchor 格 vs 餵進去那 anchor 格。

    Wan22ImageToVideoLatent 會把餵進去的格子在 latent 上 mask 成 0（不去噪），
    所以這兩段在數學上應該是同一段畫面，只差一次 VAE 來回。
    差值大 = 接線接錯了（沒真的鎖住），不是「品質差」。
    """
    a = read_frames(fed_video, 0, anchor, scale=(176, 320)).astype(np.float32)
    b = read_frames(gen_video, 0, anchor, scale=(176, 320)).astype(np.float32)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    dmean = (b.mean((0, 1, 2)) - a.mean((0, 1, 2)))
    return {
        "frames_compared": int(n),
        "rgb_shift": [round(float(x), 2) for x in dmean],
        "mean_abs_diff": round(float(np.abs(b - a).mean()), 3),
    }


def luma_drift(video, start=0, k=9):
    """段內亮度漂移：頭 k 格 vs 尾 k 格的平均亮度差。

    WanVideoWrapper issue #1541 那個色偏 bug 會讓亮度單調上升。
    量到才知道「段間要不要統一調色」——這是 P4 統一調色的決策依據，
    不是憑感覺加一層 curves。
    """
    g = read_frames(video, scale=(176, 320), gray=True).astype(np.float32)
    g = g[start:]
    head, tail = float(g[:k].mean()), float(g[-k:].mean())
    return {"head": round(head, 2), "tail": round(tail, 2), "drift": round(tail - head, 2)}


def rgb_mean(video, start=0, n=None):
    a = read_frames(video, start, n, scale=(176, 320)).astype(np.float32)
    return [round(float(x), 2) for x in a.mean((0, 1, 2))]


def motion_energy(video, start=0):
    """整段的平均幀間差 —— 「這片到底有沒有在動」。

    對照組意義：Wan 的死穴之一是生出 live wallpaper（幾乎不動）。
    這個數字低到接近段內雜訊水平，就是 prompt 的動作指令根本沒被執行。
    """
    g = read_frames(video, scale=(176, 320), gray=True)[start:]
    d = frame_deltas(g)
    return {"mean": round(float(d.mean()), 3), "max": round(float(d.max()), 3),
            "std": round(float(d.std()), 3)}


def flow_stats(video, start=0, step=2):
    """Farneback 光流：動作幅度與速度抖動。

    速度抖動（相鄰幀光流大小的變化率）是 8/14 那輪實驗量到的硬天花板 0.47，
    四種變數都突破不了。這裡沿用同一個指標，好讓新實驗跟舊基線可比。
    step=2 是抽樣（每 2 格算一次），121 格算 60 次，約 3 秒。
    """
    import cv2
    g = read_frames(video, scale=(176, 320), gray=True)[start:]
    mags = []
    for i in range(0, len(g) - step, step):
        f = cv2.calcOpticalFlowFarneback(g[i], g[i + step], None,
                                         0.5, 3, 15, 3, 5, 1.2, 0)
        mags.append(float(np.linalg.norm(f, axis=2).mean()))
    mags = np.array(mags) if mags else np.array([0.0])
    jitter = (float(np.abs(np.diff(mags)).mean() / mags.mean())
              if len(mags) > 1 and mags.mean() > 1e-6 else 0.0)
    return {"flow_mean": round(float(mags.mean()), 3),
            "flow_max": round(float(mags.max()), 3),
            "jitter": round(jitter, 3)}


def sharpness(video, start=0, step=6):
    """Laplacian 變異數 —— 畫質／銳利度代理。

    段間如果有一段明顯糊掉（VAE 來回誤差累積），這個數字會掉下去。
    抽樣算，不需要每格。
    """
    import cv2
    g = read_frames(video, scale=(352, 640), gray=True)[start::step]
    vals = [float(cv2.Laplacian(f, cv2.CV_64F).var()) for f in g]
    return {"mean": round(float(np.mean(vals)), 1), "min": round(float(np.min(vals)), 1)}


def hist_drift(video, start=0, bins=32):
    """每一格的色彩直方圖 vs 第一格的卡方距離，取最大值。

    角色漂移（換毛色／換品種）與場景漂移會讓色彩分佈整體偏移。
    ⚠️ 這是**代理指標**不是判定：狗轉個身、光影變化也會讓它上升。
    拿來排名次（哪一組漂得比較多）可以，拿來說「這組崩了」不行。
    """
    import cv2
    a = read_frames(video, scale=(176, 320))[start:]
    ref = cv2.calcHist([a[0]], [0, 1, 2], None, [bins] * 3, [0, 256] * 3)
    cv2.normalize(ref, ref)
    ds = []
    for f in a[1::3]:
        h = cv2.calcHist([f], [0, 1, 2], None, [bins] * 3, [0, 256] * 3)
        cv2.normalize(h, h)
        ds.append(float(cv2.compareHist(ref, h, cv2.HISTCMP_CHISQR_ALT)))
    return {"max": round(max(ds), 2), "mean": round(float(np.mean(ds)), 2)}


def subject_area(video, start=0, thr=18):
    """前景面積代理：每格跟「時間中位數背景」差多少的像素比例。

    用途是抓 **增生**：畫面上突然多一隻狗 → 會動的面積階躍上升。
    ⚠️ 一樣是代理指標。狗走近鏡頭、道具翻倒也會讓它上升。
    回變異係數（std/mean）與最大值 —— 變異係數大＝面積不穩＝值得人眼去看。
    """
    a = read_frames(video, scale=(176, 320), gray=True)[start:].astype(np.float32)
    bg = np.median(a, axis=0)
    area = ((np.abs(a - bg) > thr).mean(axis=(1, 2)))
    m = float(area.mean())
    return {"mean": round(m, 4), "max": round(float(area.max()), 4),
            "cv": round(float(area.std() / m), 3) if m > 1e-6 else 0.0}


# ────────────────────────── 打包 ──────────────────────────

def full_report(video, skip_frames=0, seams=None, fed=None, anchor=None):
    """一支片跑完所有指標。skip_frames：接龍段要跳過前 anchor 格再量段內指標。"""
    info = probe(video)
    r = {
        "file": Path(video).name,
        "spec": f"{info['width']}x{info['height']}",
        "frames": info["frames"],
        "duration": round(info["duration"], 2),
        "motion": motion_energy(video, skip_frames),
        "flow": flow_stats(video, skip_frames),
        "sharpness": sharpness(video, skip_frames),
        "luma_drift": luma_drift(video, skip_frames),
        "rgb_mean": rgb_mean(video, skip_frames),
        "hist_drift": hist_drift(video, skip_frames),
        "subject_area": subject_area(video, skip_frames),
    }
    if seams:
        r["seam"] = seam_ratio(video, seams)
    if fed and anchor:
        r["anchor_fidelity"] = anchor_fidelity(fed, video, anchor)
    return r


def contact_sheet(video, out_png, n=6, cols=6, label=None):
    """抽 n 格橫排成一張對照圖，給人眼看（自動指標看不到第三條腿）。"""
    info = probe(video)
    total = info["frames"]
    idx = np.linspace(0, max(0, total - 1), n).astype(int)
    frames = []
    for i in idx:
        frames.append(read_frames(video, int(i), 1, scale=(352, 640))[0])
    from PIL import Image, ImageDraw
    rows = (n + cols - 1) // cols
    W, H = 352 * min(n, cols), 640 * rows + (26 if label else 0)
    sheet = Image.new("RGB", (W, H), (20, 20, 20))
    for j, f in enumerate(frames):
        sheet.paste(Image.fromarray(f), (352 * (j % cols), 640 * (j // cols) + (26 if label else 0)))
    d = ImageDraw.Draw(sheet)
    if label:
        d.text((8, 6), label, fill=(255, 255, 0))
    for j, i in enumerate(idx):
        d.text((352 * (j % cols) + 8, 640 * (j // cols) + (26 if label else 0) + 8),
               f"f{i}", fill=(255, 255, 0))
    sheet.save(out_png)
    return out_png


if __name__ == "__main__":
    print(json.dumps(full_report(sys.argv[1]), ensure_ascii=False, indent=2))
