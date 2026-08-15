# -*- coding: utf-8 -*-
"""單變數實驗：本機 Wan 2.2 到底能不能生出「會動、流暢」的片。

背景（2026-08-14 交接檔）：D6/D7 六支候選片實測「畫面能過 gate、動作過不了關」，
賢賢看完兩支成品的評語是「不會動、不流暢」。但「調 steps／shift 能不能救」
從來沒有乾淨驗證過 —— 8/14 早上試 steps 6 那次同時改了三個變數，結論不算數。

所以這支腳本把基準完全鎖死，一次只動一個變數：

    場景圖 = d6s1_scene_v2.jpg      （v09 用的那張，盆栽合理性已解決）
    prompt = d6s1_video.txt         （v06 的 prompt，裡面明寫「全身甩身」）
    seed   = 424244                 （v09 用的那顆）
    其餘   = steps 4 / shift 8.0 / 121 幀 / euler+simple

為什麼挑 v09 當基準：它是唯一 gate 十條全過的一版，
唯一的缺點就是「prompt 寫的甩身沒生出來」—— 正好是這次要驗的那件事。

E00 是拿同一組參數重跑一次。它的用途是**驗證重現性**：
如果 E00 跟現成的 d6s1-cand-v09.mp4 量出來不一樣，那底下所有比較都不能信。

用法：python exp_sweep.py [只跑某幾個的 id，例如 E04 E05]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼")
AUTO = ROOT / "auto"
CLIPS = AUTO / "clips"
OUT = ROOT / "LOCAL-AI-STUDIO" / "PRODUCTION" / "_exp_20260814"
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable

SCENE = CLIPS / "d6s1_scene_v2.jpg"
PROMPT = CLIPS / "d6s1_video.txt"
SEED = "424244"

RUNS = [
    ("E00_base",    "基準重現（steps 4 / shift 8 / 121 幀 / euler）", []),
    ("E01_steps6",  "steps 6",                    ["--steps", "6"]),
    ("E02_steps8",  "steps 8",                    ["--steps", "8"]),
    ("E03_steps10", "steps 10",                   ["--steps", "10"]),
    ("E04_shift5",  "shift 5.0",                  ["--shift", "5.0"]),
    ("E05_shift12", "shift 12.0",                 ["--shift", "12.0"]),
    ("E06_len81",   "81 幀（3.375 秒）",           ["--length", "81"]),
    ("E07_dpmpp2m", "sampler dpmpp_2m",           ["--sampler", "dpmpp_2m"]),
    ("E08_unipc",   "sampler uni_pc",             ["--sampler", "uni_pc"]),
    ("E09_eulera",  "sampler euler_ancestral",    ["--sampler", "euler_ancestral"]),
    # 第二批（2026-08-15 凌晨加）：第一批發現 steps 是唯一有效的變數，而且 4→10 一路單調上升。
    # 但「上升」不等於「上得去」——要回答「本機到底能不能達標」就必須找到它的天花板在哪，
    # 不然結論會變成「再加 steps 說不定就行了」這種永遠無法收斂的話。
    ("E10_steps16", "steps 16",                   ["--steps", "16"]),
    ("E11_steps24", "steps 24",                   ["--steps", "24"]),
]

only = [a for a in sys.argv[1:]]
if only:
    RUNS = [r for r in RUNS if any(r[0].startswith(o) for o in only)]

RESULT = OUT / "results.json"
results = json.loads(RESULT.read_text(encoding="utf-8")) if RESULT.exists() else {}


def run(cmd, timeout=3000):
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


for rid, label, extra in RUNS:
    mp4 = OUT / f"{rid}.mp4"
    print(f"\n{'='*60}\n▶ {rid}  {label}", flush=True)
    t0 = time.time()

    if mp4.exists():
        print("  （檔案已存在，跳過生成）", flush=True)
    else:
        rc, log = run([PY, str(AUTO / "make_video_local_5s.py"), str(SCENE),
                       str(PROMPT), str(mp4), "--seed", SEED] + extra)
        (OUT / f"{rid}.log").write_text(log, encoding="utf-8")
        if rc != 0 or not mp4.exists():
            print(f"  ❌ 生成失敗（rc={rc}）：{log[-500:]}", flush=True)
            results[rid] = {"label": label, "error": log[-800:]}
            RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                              encoding="utf-8")
            continue
    gen_min = round((time.time() - t0) / 60, 1)

    # 光流量測（動作幅度／流暢度）
    rc, out = run([PY, str(AUTO / "flow.py"), "--json", str(mp4)], timeout=600)
    flow = json.loads(out.strip().splitlines()[-1])[0] if rc == 0 else {}

    # 動量（跟過去的片同一套演算法，可以對照舊數字）
    rc, mout = run([PY, str(AUTO / "momentum.py"), str(mp4),
                    str(OUT / f"_tmp_{rid}")], timeout=600)
    ratio = None
    for line in mout.splitlines():
        if "峰值/基線" in line:
            ratio = line.strip()

    # 0.2 秒間隔的密集幀貼圖 —— 不能只看數字，要用眼睛確認動作到底有沒有發生
    sheet = OUT / f"{rid}_sheet.jpg"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4),
                    "-vf", "fps=5,scale=216:-1,tile=5x5", "-frames:v", "1",
                    str(sheet)], check=False)

    results[rid] = {"label": label, "gen_min": gen_min, "momentum": ratio, **flow}
    RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ {gen_min} 分鐘 / motion={flow.get('motion')} "
          f"peak={flow.get('peak')} jerk={flow.get('jerk')} "
          f"flow_ok={flow.get('flow_ok')}", flush=True)

print("\n\n" + "=" * 60)
print(f"{'id':<12}{'變數':<28}{'分鐘':>5}{'motion':>9}{'peak':>8}{'jerk':>7}{'flow_ok':>9}")
for rid, label, _ in RUNS:
    r = results.get(rid, {})
    if "error" in r:
        print(f"{rid:<12}{label:<28}  失敗")
        continue
    print(f"{rid:<12}{label:<28}{r.get('gen_min','?'):>5}{r.get('motion','?'):>9}"
          f"{r.get('peak','?'):>8}{r.get('jerk','?'):>7}{r.get('flow_ok','?'):>9}")
print(f"\n參考值：d1s1 黑洞(Veo,5.1萬觀看) motion 0.262 / peak 0.946 / jerk 0.191 / flow_ok 0.578")
print(f"        d6s1-cand-v09(現成檔)   motion 0.059 / peak 0.138 / jerk 0.533 / flow_ok 0.138")
print(f"\n結果寫在 {RESULT}")
