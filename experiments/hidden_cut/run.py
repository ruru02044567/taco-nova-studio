# -*- coding: utf-8 -*-
r"""藏切測試（2026-08-21）—— 八種零下載轉場，哪一種真的看不出接縫？

## 為什麼藏切是 P0 而不是 P4

《對標製作標準》第五節第 3 招「遮擋藏刀」：讓水花撲滿鏡頭的 1–2 幀內藏硬切，
觀感一鏡到底。對我們的意義比對標更大 —— Wan 一次只能生 5 秒，
12–15 秒**一定**是多段組成的。接縫藏不住，觀眾就會看出這是 AI 拼接。
接龍（P1）只能處理「同一鏡延續」，換動作、換機位、換場景照樣要靠藏切。

## 這支不用顯卡、不下載任何東西

全部是 ffmpeg 內建濾鏡（zoompan / eq / tmix / overlay / crop 表達式）。
用現成的已發布素材當輸入，跑完只要幾十秒。所以它排在第一順位跑 ——
GPU 那邊在算圖時，這邊已經可以出結論。

## 兩個情境（因為藏切的難度取決於接縫有多醜）

| 情境 | 接法 | 為什麼選它 |
|---|---|---|
| 甲 同場景殘餘接縫 | `d10s1` ＋ `d10s1_s2` 從第 17 格起 | 這是 8/20 量到「❌ 接法」的那種接縫（幀差 8.58）——接龍做對了不會有，做錯了就是這樣 |
| 乙 換場景硬切 | `d10s1`（蛋液房）＋ `d12s1`（藍漆房） | 最壞情況：換房間、換色調、換姿勢。多鏡敘事一定會遇到 |

## 評分方式（重點：不是「接縫幀差越小越好」）

一個好的藏切**不是**把接縫的畫面變化壓小，而是**讓接縫不再是附近最大的那一跳**。
白光閃一下的那幾格，每一格變化都很大，人眼就分不出哪一格是刀口。所以主指標是：

    cut_prominence ＝ 接縫幀差 ÷ 轉場視窗內的最大幀差

    < 0.5  刀口被完全蓋住（視窗內有比它更大的變化在吸引注意）
    ~ 1.0  刀口就是視窗內最大的一跳 ＝ 藏切沒有作用

輔助指標 `cut_ratio ＝ 接縫幀差 ÷ 段內正常幀差`（8/20 的老指標，越小越好）。
兩個一起看：prominence 說「有沒有被蓋住」，ratio 說「跳得有多大」。

⚠️ 這兩個數字量的是**訊號層面藏得好不好**，量不到「這個轉場放在這支片裡合不合理」
（白光閃在安靜的臥室戲裡很突兀，數字卻很漂亮）。適用情境靠人判斷，見 output 的說明欄。

## 用法

    python experiments\hidden_cut\run.py                # 兩個情境 × 九種方法
    python experiments\hidden_cut\run.py --scenario 乙
    python experiments\hidden_cut\run.py --methods white_flash dip_to_black
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "_lib"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import measure  # noqa: E402

PROJECT = HERE.parents[1]
CLIPS = PROJECT / "auto" / "clips"
OUT = HERE / "out"
OUT.mkdir(parents=True, exist_ok=True)

K = 6            # 轉場長度（每側 6 格 = 0.25 秒；對標的遮擋藏刀是 1–2 幀，白光類 3–6 幀）
FPS = 24
NORM = f"scale=1080:1920:flags=lanczos,setsar=1,fps={FPS},format=yuv420p"

SCENARIOS = {
    "甲": {"a": CLIPS / "d10s1.mp4", "b": CLIPS / "d10s1_s2.mp4", "b_start": 17,
           "desc": "同場景殘餘接縫（接龍段沒切乾淨時的樣子）"},
    "乙": {"a": CLIPS / "d10s1.mp4", "b": CLIPS / "d12s1.mp4", "b_start": 0,
           "desc": "換場景硬切（蛋液房 → 藍漆房，最壞情況）"},
}


FWD = f"(t*{FPS}/{K})"          # A 尾：0 → 1
BWD = f"(1-t*{FPS}/{K})"        # B 頭：1 → 0
SMEAR = "tmix=frames=5:weights='1 1 1 1 1'"

# ── ffmpeg 濾鏡做得到的 ──────────────────────────────────────
FF_FX = {
    "hardcut":        ("null", "null"),
    "whip_pan": (                # 2. 鏡頭快速甩動
        f"scale=1512:2688,crop=1080:1920:x='(iw-ow)/2+(iw-ow)/2*{FWD}':y='(ih-oh)/2',{SMEAR}",
        f"scale=1512:2688,crop=1080:1920:x='(iw-ow)/2-(iw-ow)/2*{BWD}':y='(ih-oh)/2',{SMEAR}"),
    "foreground_wipe": (         # 3. 前景遮擋（用畫面自己放大模糊當前景物）
        f"split[bs][fg];[fg]scale=2376:4224,gblur=sigma=28,crop=1080:1920:400:1200[bl];"
        f"[bs][bl]overlay=x='-W+W*{FWD}':y=0",
        f"split[bs][fg];[fg]scale=2376:4224,gblur=sigma=28,crop=1080:1920:400:1200[bl];"
        f"[bs][bl]overlay=x='W-W*{BWD}':y=0"),
    "white_flash": (             # 4. 白光
        f"eq=brightness='0.95*{FWD}':eval=frame",
        f"eq=brightness='0.95*{BWD}':eval=frame"),
    "dip_to_black": (            # 5. 黑畫面
        f"eq=brightness='-0.95*{FWD}':eval=frame",
        f"eq=brightness='-0.95*{BWD}':eval=frame"),
    "motion_blur":    (SMEAR, SMEAR),   # 7. 純時間塗抹（不動幾何）
}

# ── 逐格縮放：ffmpeg 的 zoompan 做不到 ──────────────────────
# 第一版用 zoompan，6 格被吐成 3000 多格（d／fps 兩個參數在這條鏈上互相打架），
# 接縫索引整個錯位，量出來的數字全是垃圾。改成用 PIL 一格一格算：
# 12 格而已，眨眼跑完，而且輸出幀數是寫死的，不會再有這種驚喜。
# (中心 x 比例, 中心 y 比例, 最大倍率)
PIL_ZOOM = {
    "rush_to_camera": (0.50, 0.45, 2.8),   # 1. 衝向鏡頭：對著角色臉的高度推進
    "whip_zoom":      (0.50, 0.45, 2.5),   # 6. zoom ＋ whip（推完再加時間塗抹）
    "object_fills":   (0.32, 0.66, 4.2),   # 8. 物體填滿：撲向畫面左下的道具區
}
# 推完還要再加一層時間塗抹的
PIL_THEN_SMEAR = {"whip_zoom"}

METHODS = ["hardcut", "rush_to_camera", "whip_pan", "foreground_wipe",
           "white_flash", "dip_to_black", "whip_zoom", "motion_blur", "object_fills",
           "shared_occluder"]

# ── 第一輪跑完之後補的：共用遮擋物 ────────────────────────────
# 第一輪量出來白光／黑畫面壓倒性勝出，其他七種全破功。看原始數字才看懂機制：
#   白光  刀口兩邊都是「幾乎全白」→ 兩格幾乎一樣 → 幀差 0.28
#   甩鏡  刀口兩邊都甩到最大，但甩的是**兩張不同的畫面** → 幀差 43.19（比不做還糟）
# 也就是說藏切能不能成立的關鍵不是「動得夠亂」，是**刀口兩側有沒有收斂到同一個狀態**。
# 我原本的「前景遮擋」讓 A 用 A 的遮擋物、B 用 B 的遮擋物，兩塊不一樣 → 註定失敗。
# 這一版改成：遮擋物只從 A 的最後一格生一次，兩側共用同一塊。
# 這才是《對標製作標準》第 5 節第 3 招「遮擋藏刀」真正在做的事
#   —— 對標是讓一片真的水花掠過鏡頭，那片水花在刀口兩邊是同一片。
OCCLUDE_BLUR = 30
OCCLUDE_ZOOM = 2.2


def pil_zoom(frames, cx, cy, zmax, forward):
    """逐格中心縮放。forward=True 是 A 尾（1→zmax），False 是 B 頭（zmax→1）。"""
    from PIL import Image
    n = len(frames)
    out = []
    for i, f in enumerate(frames):
        p = i / max(1, n - 1)
        z = 1 + (zmax - 1) * (p if forward else (1 - p))
        H, W = f.shape[:2]
        cw, ch = W / z, H / z
        x0 = min(max(cx * W - cw / 2, 0), W - cw)
        y0 = min(max(cy * H - ch / 2, 0), H - ch)
        im = Image.fromarray(f).crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))
        out.append(np.asarray(im.resize((W, H), Image.LANCZOS)))
    return np.stack(out)


NOTES = {
    "hardcut": "對照組，不做任何處理",
    "rush_to_camera": "角色主動衝向鏡頭時最自然；靜態表演鏡用會很怪",
    "whip_pan": "換機位／換場景最泛用；對標鎖死機位，用了要付「不像對標」的代價",
    "foreground_wipe": "最貼近對標第 3 招；畫面裡本來就有東西掠過時無敵，硬加會像特效",
    "white_flash": "災難瞬間、爆炸、閃光合理時最強；安靜家居戲會突兀",
    "dip_to_black": "時間跳躍（過了一會兒）的語法；Shorts 中間放黑畫面會掉完播率，慎用",
    "whip_zoom": "情緒放大＋換鏡；punchline 前推進很好用",
    "motion_blur": "最低調，什麼場景都能用；藏不住大跳變",
    "object_fills": "把道具／身體撲滿畫面藏刀；需要畫面上真的有一塊有質感的區域",
    "shared_occluder": "同一塊遮擋物橫跨刀口（對標第 3 招的正確版本）；最泛用且不改色調",
    "download": "以上九種全部零下載、純 ffmpeg 內建濾鏡，不需要任何模型",
}


def ff(args):
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", *[str(a) for a in args]],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "")[-800:])


def seg(src, start, n, filt, dst):
    """切一段、套濾鏡、正規化。中文路徑坑：呼叫端已經放在英文暫存目錄。"""
    vf = f"trim=start_frame={start}:end_frame={start + n},setpts=PTS-STARTPTS"
    chain = f"[0:v]{vf}[t];[t]" + (filt if filt != "null" else "null") + f"[x];[x]{NORM}[v]"
    ff(["-i", src, "-filter_complex", chain, "-map", "[v]", "-an",
        "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", dst])
    got = measure.probe(dst)["frames"]
    if got != n:
        # 幀數對不上就大聲失敗。第一版 zoompan 靜默把 6 格變成 3000 多格，
        # 接縫索引錯位、數字全錯，卻照樣印出漂亮的結論 —— 這道檢查就是為了那次。
        raise RuntimeError(f"{Path(dst).name} 應該 {n} 格，實際 {got} 格（濾鏡改動了幀數）")


def seg_pil(src, start, n, frames_fn, dst, then_smear=False):
    """逐格用 PIL 處理再寫回 mp4。幀數由 numpy 陣列長度決定，不會被濾鏡改掉。"""
    arr = measure.read_frames(src, start, n)
    arr = frames_fn(arr)
    H, W = arr.shape[1:3]
    tmp = Path(dst).with_name(Path(dst).stem + "_pre.mp4") if then_smear else Path(dst)
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-vf", NORM, "-an", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(tmp)],
        stdin=subprocess.PIPE)
    p.communicate(arr.astype(np.uint8).tobytes())
    if p.returncode != 0:
        raise RuntimeError(f"寫檔失敗：{dst}")
    if then_smear:
        ff(["-i", str(tmp), "-vf", f"{SMEAR},{NORM}", "-an",
            "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(dst)])
        tmp.unlink(missing_ok=True)
    got = measure.probe(dst)["frames"]
    if got != n:
        raise RuntimeError(f"{Path(dst).name} 應該 {n} 格，實際 {got} 格")


def make_occluder(frame):
    """從一張畫格做出遮擋物：放大到看不出是什麼、重模糊。回 (H, W, 3)。"""
    from PIL import Image, ImageFilter
    H, W = frame.shape[:2]
    im = Image.fromarray(frame)
    z = OCCLUDE_ZOOM
    im = im.crop((int(W * 0.1), int(H * 0.45),
                  int(W * 0.1 + W / z), int(H * 0.45 + H / z))).resize((W, H), Image.LANCZOS)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(OCCLUDE_BLUR)))


def slide_occluder(frames, occ, forward):
    """把同一塊遮擋物滑進／滑出。forward=True 由左滑到全覆蓋，False 由全覆蓋滑出右邊。"""
    n = len(frames)
    out = []
    for i, f in enumerate(frames):
        p = i / max(1, n - 1)
        H, W = f.shape[:2]
        x = int(round(-W + W * p)) if forward else int(round(W * p))
        canvas = f.copy()
        # occ 貼在 [x, x+W)，只畫落在畫面內的那一段
        lo, hi = max(0, x), min(W, x + W)
        if hi > lo:
            canvas[:, lo:hi] = occ[:, lo - x:hi - x]
        out.append(canvas)
    return np.stack(out)


def build(a_src, b_src, b_start, method, dst):
    with tempfile.TemporaryDirectory(prefix="hcut_") as td:
        td = Path(td)
        a, b = td / "a.mp4", td / "b.mp4"
        shutil.copy2(a_src, a)
        shutil.copy2(b_src, b)
        na, nb = measure.probe(a)["frames"], measure.probe(b)["frames"]
        # 共用遮擋物只生一次，兩側用同一塊 —— 這正是它跟 foreground_wipe 的唯一差別
        occ = (make_occluder(measure.read_frames(a, na - 1, 1)[0])
               if method == "shared_occluder" else None)
        parts = []
        specs = [("p0", a, 0, na - K, None),
                 ("p1", a, na - K, K, True),
                 ("p2", b, b_start, K, False),
                 ("p3", b, b_start + K, nb - b_start - K, None)]
        for name, src, st, n, side in specs:
            if n <= 0:
                continue
            out = td / f"{name}.mp4"
            if side is not None and method in PIL_ZOOM:
                cx, cy, zmax = PIL_ZOOM[method]
                seg_pil(str(src), st, n,
                        lambda arr, s=side: pil_zoom(arr, cx, cy, zmax, forward=s),
                        str(out), then_smear=method in PIL_THEN_SMEAR)
            elif side is not None and method == "shared_occluder":
                seg_pil(str(src), st, n,
                        lambda arr, s=side: slide_occluder(arr, occ, forward=s), str(out))
            else:
                filt = "null" if side is None else FF_FX[method][0 if side else 1]
                seg(str(src), st, n, filt, str(out))
            parts.append(out)
        lst = td / "list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        joined = td / "joined.mp4"
        ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
        shutil.copy2(joined, dst)
        return na          # 接縫落在輸出的第 na 格


def score(video, cut, k=K):
    """回 cut_prominence / cut_ratio / 視窗內最大跳動。"""
    g = measure.read_frames(video, scale=(176, 320), gray=True)
    d = measure.frame_deltas(g)
    lo, hi = max(0, cut - k - 1), min(len(d), cut + k)
    win = d[lo:hi]
    outside = np.concatenate([d[:lo], d[hi:]]) if lo > 0 or hi < len(d) else d
    base = float(np.median(outside))
    cut_d = float(d[cut - 1])
    wmax = float(win.max())
    return {"cut_delta": round(cut_d, 2), "window_max": round(wmax, 2),
            "baseline": round(base, 2),
            "cut_prominence": round(cut_d / wmax, 3) if wmax > 0 else None,
            "cut_ratio": round(cut_d / base, 2) if base > 0 else None}


def main():
    argv = sys.argv[1:]
    only_sc = argv[argv.index("--scenario") + 1] if "--scenario" in argv else None
    only_me = argv[argv.index("--methods") + 1:] if "--methods" in argv else None
    methods = only_me or METHODS

    rows = []
    for sc, cfg in SCENARIOS.items():
        if only_sc and sc != only_sc:
            continue
        if not cfg["a"].exists() or not cfg["b"].exists():
            print(f"[!] 情境 {sc} 素材缺檔，跳過")
            continue
        print(f"\n═══ 情境 {sc}：{cfg['desc']} ═══")
        print(f"    A={cfg['a'].name}　B={cfg['b'].name}（從第 {cfg['b_start']} 格起）")
        for me in methods:
            dst = OUT / f"{sc}_{me}.mp4"
            try:
                cut = build(cfg["a"], cfg["b"], cfg["b_start"], me, dst)
                s = score(dst, cut)
            except Exception as e:
                print(f"  ❌ {me}：{e}")
                rows.append({"scenario": sc, "method": me, "error": str(e)[:300]})
                continue
            s.update({"scenario": sc, "method": me, "file": dst.name,
                      "cut_frame": cut, "note": NOTES.get(me, "")})
            rows.append(s)
            verdict = ("✅ 刀口被蓋住" if (s["cut_prominence"] or 9) < 0.5
                       else "△ 部分" if (s["cut_prominence"] or 9) < 0.8 else "❌ 藏不住")
            print(f"  {me:16} prominence {s['cut_prominence']}　"
                  f"ratio {s['cut_ratio']}　{verdict}")
        # 每個情境挑三種做對照圖（人眼才看得出「合不合理」）
        for me in ("hardcut", "white_flash", "object_fills"):
            f = OUT / f"{sc}_{me}.mp4"
            if f.exists():
                _seam_sheet(f, measure.probe(cfg["a"])["frames"], OUT / f"{sc}_{me}_seam.png",
                            f"{sc} {me}")

    (OUT / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(f"\n[ok] {len(rows)} 組 → {OUT / 'results.json'}")
    return 0


def _seam_sheet(video, cut, dst, label):
    """接縫前後各 3 格排成一張，人眼直接看刀口。"""
    from PIL import Image, ImageDraw
    idx = [cut - 3, cut - 2, cut - 1, cut, cut + 1, cut + 2]
    imgs = [measure.read_frames(video, i, 1, scale=(300, 533))[0] for i in idx]
    sheet = Image.new("RGB", (300 * 6, 533 + 26), (20, 20, 20))
    for j, im in enumerate(imgs):
        sheet.paste(Image.fromarray(im), (300 * j, 26))
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), f"{label}　接縫在 f{cut}（第 4 格）", fill=(255, 255, 0))
    for j, i in enumerate(idx):
        d.text((300 * j + 6, 32), f"f{i}", fill=(255, 255, 0))
    sheet.save(dst)


if __name__ == "__main__":
    sys.exit(main())
