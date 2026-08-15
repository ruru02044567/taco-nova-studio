# -*- coding: utf-8 -*-
"""EXP-01：建立 Nova V2 訓練集（人工判定標籤 + 場景多樣性）

V1 的問題：5 張訓練圖全是「乾淨客廳裡的狗」，LoRA 把「乾淨」也當成角色特徵，
權重一上去就把災難主體（紅酒漬）抹掉。

V2 的作法：同一隻 Nova，出現在不同場景狀態與不同光線下，
讓模型學不到「Nova ⇒ 乾淨客廳」這條捷徑。

⚠️ 自動標籤（前景面積大的是 Nova）已證實完全錯誤 ——
Taco 在前景貼近鏡頭，畫素面積比背景的 Nova 還大。
本檔的標籤全部是逐張目視判定後手寫的。

用法：python 20_build_nova_v2.py
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8")

PROJ = Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼")
STUDIO = PROJ / "LOCAL-AI-STUDIO"
CAND = STUDIO / "DATASET" / "_candidates"
V1 = STUDIO / "DATASET" / "dog_support" / "TRAIN"
OUT = STUDIO / "DATASET" / "dog_support_v2"
for d in ["TRAIN", "REVIEW", "REJECT"]:
    (OUT / d).mkdir(parents=True, exist_ok=True)

# ── 人工判定表 ────────────────────────────────────────────────
# (候選檔名, 裁切框比例 or None=整張, 場景, 光線, 判定, 備註)
# 裁切框 = (x0, y0, x1, y1)，只在需要從雙狗畫面裡取出 Nova 時使用
PICKS = [
    # 淹水場景：Nova 單獨全身，是整批最有價值的素材
    ("dog_main/taco_d3s1-flood_f002.png", None, "flood", "indoor-daylight", "TRAIN",
     "Nova 單獨站姿全身，藍眼與臉罩清楚"),
    ("dog_main/taco_d3s1-flood_f005.png", None, "flood", "indoor-daylight", "TRAIN",
     "Nova 單獨坐姿正面"),
    ("dog_main/taco_d3s1-flood_f007.png", None, "flood", "indoor-daylight", "TRAIN",
     "Nova 單獨坐姿，與 f005 角度略異"),
    # 麵粉場景：Nova 躺睡在後方，需裁切
    ("dog_main/unknown_d4s1-flour_f001.png", (0.63, 0.09, 1.00, 0.52), "flour", "warm-window",
     "TRAIN", "Nova 側躺睡，麵粉場景"),
    ("dog_main/unknown_d4s1-flour_f003.png", (0.58, 0.05, 1.00, 0.48), "flour", "warm-window",
     "TRAIN", "Nova 側躺睡，另一角度"),
    # 岩漿場景：橘色底光，是 V1 完全沒有的光線
    ("dog_main/unknown_d5s1-lava_f002.png", (0.00, 0.08, 0.75, 0.38), "lava", "orange-underlight",
     "TRAIN", "Nova 在沙發上，戲劇性橘光 ★ 光線多樣性"),
    ("dog_main/unknown_d5s1-lava_f004.png", (0.00, 0.08, 0.75, 0.38), "lava", "orange-underlight",
     "TRAIN", "同上，另一幀"),
    # 雙狗同框：Nova 站姿清楚，裁切後可用
    ("dog_main/unknown_d3s1-flood_f008.png", (0.46, 0.00, 1.00, 0.86), "flood", "indoor-daylight",
     "REVIEW", "Nova 站在背景，較小需確認解析度"),
    ("dog_main/unknown_d3s1-flood_f011.png", (0.02, 0.00, 1.00, 0.55), "flood", "indoor-daylight",
     "REVIEW", "Nova 橫躺，畫面被 Taco 遮住一部分"),
    # 明確排除
    ("dog_main/taco_d1s1-blackhole_f008.png", None, "-", "-", "REJECT", "畫面裡根本沒有狗，是盆栽"),
    ("dog_main/taco_d1s1-blackhole_f002.png", None, "-", "-", "REJECT", "這是 Taco 不是 Nova"),
    ("dog_main/unknown_d3s1-flood_f009.png", None, "-", "-", "REJECT", "這是 Taco 特寫"),
    ("dog_main/unknown_d3s1-flood_f010.png", None, "-", "-", "REJECT", "這是 Taco 特寫"),
]

# V1 的 5 張乾淨素材：保留當「乾淨場景」那一類的錨點
V1_CLEAN = [
    ("nova_01_closeup.png", "clean-livingroom", "warm-window", "臉部特寫"),
    ("nova_02_front_fullbody.png", "clean-livingroom", "warm-window", "正面坐姿全身"),
    ("nova_03_front_fullbody.png", "clean-livingroom", "warm-window", "正面坐姿全身"),
    ("nova_04_34standing_SIZEREF.png", "clean-livingroom", "warm-window", "3/4 站姿，體型黃金範本"),
    ("nova_05_34lying.png", "clean-livingroom", "warm-window", "3/4 側躺"),
]


def main():
    manifest = []

    # ── V1 乾淨素材 ──
    for fn, scene, light, note in V1_CLEAN:
        src = V1 / fn
        if not src.exists():
            print(f"  ⚠ 缺 {fn}")
            continue
        dst = OUT / "TRAIN" / f"nova_clean_{fn}"
        shutil.copy2(src, dst)
        im = Image.open(dst)
        manifest.append({"filename": dst.name, "identity": "nova", "scene": scene,
                         "lighting": light, "split": "TRAIN", "reason": note,
                         "source": f"V1/{fn}", "size": f"{im.width}x{im.height}"})

    # ── 影片抽幀 ──
    for rel, box, scene, light, split, note in PICKS:
        src = CAND / rel
        if not src.exists():
            print(f"  ⚠ 缺 {rel}")
            continue
        if split == "REJECT":
            dst = OUT / "REJECT" / Path(rel).name
            shutil.copy2(src, dst)
            manifest.append({"filename": dst.name, "identity": "not-nova", "scene": scene,
                             "lighting": light, "split": "REJECT", "reason": note,
                             "source": rel, "size": "-"})
            continue
        im = Image.open(src).convert("RGB")
        if box:
            W, H = im.size
            im = im.crop((int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)))
        name = f"nova_{scene}_{Path(rel).stem.split('_')[-1]}.png"
        dst = OUT / split / name
        im.save(dst)
        manifest.append({"filename": name, "identity": "nova", "scene": scene,
                         "lighting": light, "split": split, "reason": note,
                         "source": rel, "size": f"{im.width}x{im.height}"})

    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    n = {s: sum(1 for m in manifest if m["split"] == s) for s in ["TRAIN", "REVIEW", "REJECT"]}
    print(f"TRAIN {n['TRAIN']} / REVIEW {n['REVIEW']} / REJECT {n['REJECT']}")
    scenes = {}
    for m in manifest:
        if m["split"] == "TRAIN":
            scenes[m["scene"]] = scenes.get(m["scene"], 0) + 1
    print("TRAIN 的場景分布：", scenes)

    # 對照表
    fs = sorted((OUT / "TRAIN").glob("*.png"))
    if fs:
        TH = 300
        ims = [Image.open(f).convert("RGB") for f in fs]
        ims = [i.resize((int(i.width * TH / i.height), TH)) for i in ims]
        W = sum(i.width for i in ims) + 5 * (len(ims) + 1)
        sh = Image.new("RGB", (W, TH + 20), (24, 24, 24))
        dr = ImageDraw.Draw(sh); x = 5
        for f, i in zip(fs, ims):
            sh.paste(i, (x, 16)); dr.text((x + 2, 2), f.stem[:26], fill=(255, 220, 120))
            x += i.width + 5
        sh.save(OUT / "_TRAIN_SHEET.jpg", quality=90)
        print(f"✅ {OUT / '_TRAIN_SHEET.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
