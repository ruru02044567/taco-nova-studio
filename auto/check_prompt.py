# -*- coding: utf-8 -*-
r"""check_prompt.py — Wan 2.2 六崩壞規律 prompt 健檢（2026-08-19 建立）

依據：2026-08-13 D6S1 六版單變數實測（每條都是實測不是推論）＋
Hell Grind prompt 健檢器思路。規律本體見 D6S1_迭代紀錄與PROMPT模板.md。

檢查對象：
  python auto\check_prompt.py --key d10s1            # clips\d10s1_video.txt（＋scene 檔若在）
  python auto\check_prompt.py --day 10               # schedule.json 該天的 scene+video prompt
  python auto\check_prompt.py --all                  # schedule.json 全部 19 天
  python auto\check_prompt.py --file X.txt [--kind video|scene]

結果：✗ FAIL（實測必崩）→ exit 1；⚠ WARN（有風險）；✓ PASS。
定位：出拍前的免費體檢（30 秒），不是守門（plan_model 才是守門）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
AUTO = Path(__file__).resolve().parent
CLIPS = AUTO / "clips"

TS = re.compile(r"\[?(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\]?|\[(\d{1,2}):(\d{2})\]")
SINGLE_PAW = re.compile(r"\b(one|a|single)\s+(front\s+|back\s+|hind\s+|left\s+|right\s+)?paw\b[^.]{0,60}", re.I)
PAW_MOTION = re.compile(r"\b(lift|rais|wav|dig|scratch|swip|tap|push|pull|point|paws?\s+at)\w*", re.I)
EAR_BAD = re.compile(r"\b(flap|flop|floppy|bend|fold|curl|droop|twist|wiggl)\w*", re.I)
FACE_DIRT = re.compile(r"\b(mud|dirt|stain|mess|sauce|yolk|paint|cream|flour|smear|goo|slime)\w*", re.I)
FACE_WORD = re.compile(r"\b(face|cheek|muzzle|snout)\b", re.I)
FACE_TOKENS = ("eye", "muzzle", "nose", "mask", "face", "chin")


def sentences(text):
    return re.split(r"(?<=[.!?])\s+", text)


def check(text: str, kind: str, clip_len: int):
    """回傳 [(等級, 規則, 訊息)]，等級 FAIL/WARN/PASS。"""
    out = []
    low = text.lower()

    if kind == "video":
        # R1 時間軸超過影片長度（角色會融解成另一個犬種）
        ends = []
        for m in TS.finditer(text):
            g = [x for x in m.groups() if x is not None]
            ends.append(int(g[-2]) * 60 + int(g[-1]))
        if ends and max(ends) > clip_len:
            out.append(("FAIL", "時間軸", f"寫到 {max(ends)} 秒但影片只有 {clip_len} 秒 → 角色會融解。時間軸只寫到片長內，動作壓到 1 個"))
        else:
            out.append(("PASS", "時間軸", "OK" if not ends else f"最長 {max(ends)}s ≤ {clip_len}s"))

        # R2 局部單肢動作（會長第三條腿）
        hits = [m.group(0) for m in SINGLE_PAW.finditer(text) if PAW_MOTION.search(m.group(0))]
        if hits:
            lvl = "WARN" if "all four paws" in low else "FAIL"
            out.append((lvl, "單肢動作", f"「{hits[0][:50]}…」→ 會長第三條腿。改全身同步動作＋all four paws staying planted flat"))
        else:
            out.append(("PASS", "單肢動作", "OK"))

        # R4 耳朵動作詞（耳朵會扭成角狀物）——以「壞詞」為圓心判定：
        # 壞詞自己前 100 字有 never＝鎖定句，跳過；否則壞詞 ±80 字內有 ear 才算冤有頭。
        # （舊版以 ear 為圓心開窗，鎖定句的 never 會被窗界切掉造成誤報，d11 實案）
        bad = []
        for m in EAR_BAD.finditer(text):
            neg = text[max(0, m.start() - 100): m.end()].lower()
            if "never" in neg or "not " in neg:
                continue
            near = text[max(0, m.start() - 80): m.end() + 80]
            if re.search(r"\bears?\b", near, re.I):
                bad.append(near)
        if bad:
            out.append(("FAIL", "耳朵", "有耳朵擺動詞且不是鎖定句 → 耳朵會扭成角。用：ears stay upright, triangular, straight and rigid — never fold, flap, bend, curl, droop, or twist"))
        elif re.search(r"\bears?\b", low) and not re.search(r"ears?[^.]{0,80}(upright|rigid|stay|keep)", low):
            out.append(("WARN", "耳朵", "提到耳朵但沒有鎖定句（沒寫到的就會崩）"))
        else:
            out.append(("PASS", "耳朵", "OK"))

        # R5 配角臉部鎖定（配角的臉會糊成白團）
        if re.search(r"\bhusky\b|\bnova\b", low):
            n = sum(1 for t in FACE_TOKENS if t in low)
            if n < 2:
                out.append(("FAIL", "配角臉", "配角在場但幾乎沒有臉部特徵句 → 後段會糊成白團。補：臉罩、吻型、鼻子、眼瞼線、頭部比例"))
            else:
                out.append(("PASS", "配角臉", f"OK（{n} 個臉部特徵詞）"))

        # R6 招牌黑點（會退化成逗號）
        if "dot" in low:
            shape = ("round" in low or "circular" in low)
            anti = re.search(r"not\s+eyebrow|no\s+tail|no\s+hook|no\s+comma|not\s+curved", low)
            hold = re.search(r"last\s+frame|entire\s+(shot|time)", low)
            if not (shape and anti):
                out.append(("FAIL", "黑點", "只寫「dot」不夠 → 會退化成逗號。補：perfectly circular, no tail no hook no comma shape"))
            elif not hold:
                out.append(("WARN", "黑點", "有形狀鎖但沒寫「撐到最後一幀」（including the very last frame）"))
            else:
                out.append(("PASS", "黑點", "OK"))

        # 通則2 過鎖（v05 實測：never 加滿後動作生不出來，變慢推照片）
        n_never = len(re.findall(r"\bnever\b", low))
        if n_never >= 8:
            out.append(("WARN", "過鎖", f"never × {n_never}，v05 教訓：鎖太滿動作會死，變一張慢推的照片"))
        else:
            out.append(("PASS", "過鎖", f"never × {n_never}"))

    if kind == "scene":
        # R3 臉部遮擋（i2v 會把髒污糊開吃掉整張臉）
        bad = [s for s in sentences(text) if FACE_DIRT.search(s) and FACE_WORD.search(s)
               and not re.search(r"clean|clear of|free of|untouched|spotless|away from", s, re.I)
               # 抱枕的「face」不是狗臉（d12 實案：cushion...face 誤報）
               and not re.search(r"(cushion|pillow|sofa|clock|wall)[^.]{0,80}\bface", s, re.I)]
        if bad:
            out.append(("FAIL", "臉部遮擋", "髒污寫在臉上 → i2v 會糊開吃掉整張臉。髒污放身體，臉明確寫乾淨"))
        else:
            out.append(("PASS", "臉部遮擋", "OK"))
        # AI 感開頭（gen_scene_flux 出圖時會自動換，這裡提醒劇本庫可以先改）
        if low.startswith("photorealistic photo"):
            out.append(("WARN", "AI感開頭", "Photorealistic photo 開頭會推向完美攝影作品（gen_scene_flux 會自動換掉，劇本庫可先改）"))
        else:
            out.append(("PASS", "AI感開頭", "OK"))

    return out


def report(name, results):
    icons = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}
    fails = sum(1 for r in results if r[0] == "FAIL")
    warns = sum(1 for r in results if r[0] == "WARN")
    print(f"\n── {name} ──")
    for lvl, rule, msg in results:
        if lvl == "PASS":
            print(f"  {icons[lvl]} {rule}")
        else:
            print(f"  {icons[lvl]} {rule}：{msg}")
    return fails, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="clips\\{key}_video.txt（＋同名 scene 檔）")
    ap.add_argument("--day", type=int, help="schedule.json 的某一天")
    ap.add_argument("--all", action="store_true", help="schedule.json 全部")
    ap.add_argument("--file", help="任意 prompt 檔")
    ap.add_argument("--kind", choices=["video", "scene"], default="video", help="--file 用")
    ap.add_argument("--len", dest="clip_len", type=int, default=5, help="片長秒數（預設 5）")
    args = ap.parse_args()

    jobs = []  # (名稱, 文字, kind)
    if args.key:
        vf = CLIPS / f"{args.key}_video.txt"
        if vf.exists():
            jobs.append((f"{args.key} video", vf.read_text(encoding="utf-8"), "video"))
        for suffix in ("_scene_flux.txt", "_scene.txt"):
            sf = CLIPS / f"{args.key}{suffix}"
            if sf.exists():
                jobs.append((f"{args.key} scene", sf.read_text(encoding="utf-8"), "scene"))
        if not jobs:
            print(f"[X] clips 裡找不到 {args.key} 的 prompt 檔")
            return 1
    elif args.day or args.all:
        sched = json.loads((AUTO / "schedule.json").read_text(encoding="utf-8"))["schedule"]
        for e in sched:
            if args.all or e["day"] == args.day:
                k = f"d{e['day']}s{e['slot']}"
                jobs.append((f"{k} scene", e.get("scenePrompt", ""), "scene"))
                jobs.append((f"{k} video", e.get("videoPrompt", ""), "video"))
        if not jobs:
            print(f"[X] schedule.json 裡沒有 day {args.day}")
            return 1
    elif args.file:
        p = Path(args.file)
        jobs.append((p.name, p.read_text(encoding="utf-8"), args.kind))
    else:
        ap.error("要嘛 --key，要嘛 --day N／--all，要嘛 --file")

    tf = tw = 0
    for name, text, kind in jobs:
        if not text.strip():
            print(f"\n── {name} ──\n  ⚠ 空 prompt")
            tw += 1
            continue
        f, w = report(name, check(text, kind, args.clip_len))
        tf += f
        tw += w

    print(f"\n總計：FAIL {tf}、WARN {tw}（{len(jobs)} 份 prompt）")
    return 1 if tf else 0


if __name__ == "__main__":
    sys.exit(main())
