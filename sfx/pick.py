# -*- coding: utf-8 -*-
"""從 Sonniss 索引挑出這個頻道要用的音效並下載到本機庫。

用法：python pick.py            # 下載預設清單
      python pick.py 關鍵字      # 只看某類有哪些檔（不下載）
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
INDEX = json.loads((HERE / "sonniss_index.json").read_text(encoding="utf-8"))

# 分類 → (正規表示式, 要幾個)　檔名比對用小寫
WANT = {
    "roomtone":    (r"roomtone|room tone|indoor.*ambience|silentscape", 4),
    "paws-wood":   (r"(paw|claw|nails).*(wood|floor)|footstep.*wood|foot.*hardwood", 4),
    "cloth-drag":  (r"(drag|slid).*(carpet|rug|fabric)|cloth.*(move|drag)|fabric.*drag", 4),
    "cloth-drop":  (r"cloth.*drop|fabric.*(fall|drop)|soft.*drop|light.*impact", 3),
    "plastic-drop": (r"plastic.*(drop|fall|impact)|remote.*drop|clatter", 3),
    "dog-small":   (r"dog.*(bark|yip|yap)|small dog|anmldog.*bark", 3),
    "dog-whimper": (r"dog.*(wimper|whimper|whine)", 2),
    "dog-sleep":   (r"dog.*(breath|snore|grunt|shuffle)|snor", 3),
    "drone-low":   (r"low_drone|low drone|drone.*(low|deep)|sub.*rumble|rumble.*low", 3),
    "whoosh":      (r"whoosh|swirl", 3),
    "ceramic":     (r"ceramic|pottery|terracotta|crockery|pot.*(break|smash)", 3),
    "dirt":        (r"dirt|soil|gravel.*scatter|debris", 3),
    "liquid":      (r"(liquid|water|wine).*(spill|pour)|pour.*(wine|water)|splash", 3),
    # ── 8/9 補：原本音效太稀疏，缺的是「連續動作」和「生物氣息」這兩類 ──
    "paws-more":   (r"footstep.*(wood|floor).*(walk|run)|foot.*wood.*(single|step)|barefoot.*wood", 8),
    "paws-carpet": (r"footstep.*(carpet|rug)|foot.*(carpet|soft)", 5),
    "breath-dog":  (r"dog.*(pant|breath|sniff|snuff)|animal.*breath", 5),
    "breath-sleep": (r"(snore|snoring|sleep.*breath|heavy.*breath)", 4),
    "fabric-fine": (r"(fabric|cloth|textile).*(rub|friction|slide|stretch)|blanket|sheet.*move", 6),
    "air-suck":    (r"(air|wind).*(suck|rush|gust|draft)|vacuum|suction", 5),
    "rumble-sub":  (r"(sub|deep|low).*(rumble|boom|hum)|earthquake|tremor", 4),
    "amb-birds":   (r"(bird|sparrow).*(distant|window|garden)|garden.*ambience", 3),
    "amb-street":  (r"(distant|far).*(traffic|street|city)|suburb.*ambience", 3),
    "house-creak": (r"(house|wood|floor).*(creak|settle)|door.*(creak|distant)", 4),
    "claw-scratch": (r"(claw|nail|scratch).*(wood|floor|surface)|scratching", 4),
}

MAX_MB = 12          # 太大的檔不要（有些是好幾分鐘的長素材）


def matches(pattern, limit):
    rx = re.compile(pattern, re.I)
    hits = [f for f in INDEX if rx.search(f["name"]) and 0 < f["size"] <= MAX_MB * 1024 * 1024]
    hits.sort(key=lambda f: f["size"])          # 小檔優先，通常是單一音效不是長 loop
    return hits[:limit]


if len(sys.argv) > 1:                            # 查詢模式
    for f in matches(sys.argv[1], 25):
        print(f"{f['size']/1024/1024:6.2f} MB  {f['name']}")
    sys.exit(0)

total = 0
for cat, (pattern, n) in WANT.items():
    out_dir = HERE / "lib" / cat
    out_dir.mkdir(parents=True, exist_ok=True)
    hits = matches(pattern, n)
    print(f"\n[{cat}] 找到 {len(hits)} 個")
    for f in hits:
        dst = out_dir / Path(f["name"]).name
        if dst.exists():
            print(f"  已有 {dst.name}")
            continue
        try:
            req = urllib.request.Request(f["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as r, open(dst, "wb") as w:
                w.write(r.read())
            total += 1
            print(f"  ↓ {dst.name}  ({f['size']/1024/1024:.2f} MB)")
        except Exception as e:
            print(f"  ✗ {Path(f['name']).name[:50]}: {str(e)[:60]}")

print(f"\n下載完成，新增 {total} 個檔案到 {HERE / 'lib'}")
