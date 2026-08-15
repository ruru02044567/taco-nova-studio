# -*- coding: utf-8 -*-
"""V2 資料集：從已發布成品片抽「髒亂場景」幀，自動篩選後產出候選集。

為什麼要做這件事：
V1 的 5 張訓練圖全是「乾淨客廳裡的狗」，LoRA 把「乾淨」也當成角色特徵學進去了。
A/B/C/D 實測證明：LoRA 權重一上去，紅酒漬就被抹掉——它在跟 prompt 打架。
要打斷這個聯想，唯一的辦法是讓它看到同一隻狗在髒亂場景也長得一樣。

三道自動門檻（機械判斷，不做主觀取捨）：
  1. 清晰度   Laplacian 變異數，擋動態模糊
  2. 主體佔比 rembg 前景面積，擋狗太小（黑點眉撐不住有一部分是這個原因）
  3. 去重     dHash 感知雜湊，near-duplicate 只留最清晰那張

⚠️ 這批素材是 AI 生成的成品影片抽幀，不是實拍。品質天花板受限於現有水準，
   而且 mp4 壓縮會比原始 PNG 參考圖糊。原本那 5 張高品質參考圖要保留當錨點。

用法（要用系統 Python，rembg 和 cv2 裝在那裡）：
  "C:/Users/TUF Gaming/AppData/Local/Programs/Python/Python313/python.exe" 09_extract_frames.py
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

PROJ = Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼")
OUT = PROJ / "LOCAL-AI-STUDIO" / "DATASET" / "_candidates"
RAW = OUT / "_raw"
for d in [OUT / "dog_main", OUT / "dog_support", OUT / "_sheets", RAW]:
    d.mkdir(parents=True, exist_ok=True)

# (影片, 場景標籤, 抽幀 fps)
# 場景標籤直接就是 caption 裡「要能被剝離」的那一欄
SOURCES = [
    (PROJ / "待審核/d1s1-有聲.mp4",        "d1s1-blackhole", 0.8),
    (PROJ / "待審核/d2s1-巧克力-有聲.mp4",  "d2s1-chocolate", 1.0),
    (PROJ / "待審核/d3s1-15秒-淹水.mp4",    "d3s1-flood",     0.8),
    (PROJ / "待審核/d4s1-麵粉-最終版.mp4",  "d4s1-flour",     0.8),
    (PROJ / "待審核/d5s1-岩漿-有聲.mp4",    "d5s1-lava",      0.8),
]

SHARP_MIN = 60.0      # Laplacian 變異數下限
AREA_MIN = 0.06       # 前景佔畫面比例下限
DHASH_DIST = 6        # 漢明距離小於此視為重複


def dhash(img, size=8):
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a, b):
    return bin(a ^ b).count("1")


def lap_var(img):
    """Laplacian 變異數＝清晰度。

    不用 cv2.imread —— 這台機器的專案路徑有中文，OpenCV 在 Windows 上
    讀不了非 ASCII 路徑（會回傳 None，然後在下一行才爆，很難查）。
    改用 PIL 讀檔、numpy 自己做 3×3 拉普拉斯卷積，結果一樣。
    """
    g = np.asarray(img.convert("L"), dtype=np.float64)
    k = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1])
    return float(k.var())


def main():
    import cv2
    from rembg import new_session, remove

    print("載入 rembg 模型…")
    sess = new_session("u2net")

    # ── 抽幀 ──
    frames = []
    for vid, tag, fps in SOURCES:
        if not vid.exists():
            print(f"⚠️ 找不到 {vid.name}")
            continue
        d = RAW / tag
        d.mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vid),
                        "-vf", f"fps={fps}", str(d / "f%03d.png")], check=True)
        got = sorted(d.glob("*.png"))
        frames += [(p, tag) for p in got]
        print(f"   {tag:<18} 抽出 {len(got)} 幀")

    print(f"\n共 {len(frames)} 幀，開始篩選…\n")

    kept, seen = [], []
    stats = {"blur": 0, "small": 0, "dup": 0, "ok": 0}
    for p, tag in frames:
        img = Image.open(p).convert("RGB")

        sharp = lap_var(img)
        if sharp < SHARP_MIN:
            stats["blur"] += 1
            continue

        cut = remove(img, session=sess)
        alpha = np.asarray(cut.split()[-1])
        area = float((alpha > 40).mean())
        if area < AREA_MIN:
            stats["small"] += 1
            continue

        h = dhash(img)
        dup = next((i for i, (hh, ss) in enumerate(seen) if hamming(h, hh) < DHASH_DIST), None)
        if dup is not None:
            if sharp > seen[dup][1]:
                seen[dup] = (h, sharp)
                kept[dup] = (p, tag, sharp, area, alpha)
            stats["dup"] += 1
            continue

        seen.append((h, sharp))
        kept.append((p, tag, sharp, area, alpha))
        stats["ok"] += 1

    print(f"篩選結果：保留 {stats['ok']}／模糊剔除 {stats['blur']}"
          f"／太小剔除 {stats['small']}／重複合併 {stats['dup']}\n")

    # ── 依前景連通區塊自動切出單隻狗 ──
    # Nova 站立約 Taco 的 3 倍，所以同一幀裡「大的是 Nova、小的是 Taco」是可用的啟發式，
    # 但 Nova 在背景遠處時會失準 → 明天目視確認，這裡只做「提案」。
    import cv2 as cv
    n_main = n_sup = 0
    for p, tag, sharp, area, alpha in kept:
        img = Image.open(p).convert("RGB")
        mask = (alpha > 40).astype(np.uint8)
        num, lab, st, _ = cv.connectedComponentsWithStats(mask, connectivity=8)
        blobs = sorted([(st[i, cv.CC_STAT_AREA], i) for i in range(1, num)], reverse=True)[:2]
        blobs = [b for b in blobs if b[0] / mask.size > 0.015]
        if not blobs:
            continue
        for rank, (barea, idx) in enumerate(sorted(blobs, key=lambda b: -b[0])):
            x, y, w, h = (st[idx, cv.CC_STAT_LEFT], st[idx, cv.CC_STAT_TOP],
                          st[idx, cv.CC_STAT_WIDTH], st[idx, cv.CC_STAT_HEIGHT])
            pad = int(0.10 * max(w, h))
            box = (max(0, x - pad), max(0, y - pad),
                   min(img.width, x + w + pad), min(img.height, y + h + pad))
            crop = img.crop(box)
            if min(crop.size) < 220:
                continue
            # 面積大的當 Nova（大型犬），小的當 Taco
            who, folder = ("nova", "dog_support") if rank == 0 and len(blobs) > 1 else ("taco", "dog_main")
            if len(blobs) == 1:
                who, folder = "unknown", "dog_main"
            t = p.stem.replace("f", "")
            name = f"{who}_{tag}_f{t}.png"
            crop.save(OUT / folder / name)
            if folder == "dog_support":
                n_sup += 1
            else:
                n_main += 1

    print(f"自動切圖：dog_main {n_main} 張／dog_support {n_sup} 張")

    # ── 對照表，明天挑圖用 ──
    from PIL import ImageDraw
    for folder in ["dog_main", "dog_support"]:
        fs = sorted((OUT / folder).glob("*.png"))
        if not fs:
            continue
        COLS, TH = 8, 240
        rows = []
        for i in range(0, len(fs), COLS):
            chunk = fs[i:i + COLS]
            ims = [Image.open(f).convert("RGB") for f in chunk]
            ims = [im.resize((int(im.width * TH / im.height), TH)) for im in ims]
            W = sum(im.width for im in ims) + 6 * (len(ims) + 1)
            row = Image.new("RGB", (W, TH + 26), (24, 24, 24))
            dr = ImageDraw.Draw(row)
            x = 6
            for f, im in zip(chunk, ims):
                row.paste(im, (x, 22))
                dr.text((x + 2, 6), f.stem[:30], fill=(255, 220, 120))
                x += im.width + 6
            rows.append(row)
        W = max(r.width for r in rows)
        big = Image.new("RGB", (W, sum(r.height for r in rows)), (24, 24, 24))
        y = 0
        for r in rows:
            big.paste(r, (0, y)); y += r.height
        sheet = OUT / "_sheets" / f"_PICK_{folder}.jpg"
        big.save(sheet, quality=85)
        print(f"   對照表 {sheet.name}  ({len(fs)} 張)")

    print(f"\n✅ 候選集在 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
