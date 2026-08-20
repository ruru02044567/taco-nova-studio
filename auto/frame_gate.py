# -*- coding: utf-8 -*-
r"""逐幀強制 gate —— 「不逐幀寫下你看到什麼，就不准出片」。

## 為什麼需要（2026-08-20 賢賢抓到 D10 哈士奇身體是一團白肉）

那個問題**第二輪審片就抓到過**（「哈士奇前伸肢體麵條化」），第三輪的檢查清單裡
也寫了要看，結果我只看了兩三張幀圖就宣告「10/10 待驗收」，又漏了。

根因不是「不知道要看什麼」，是**沒有東西強迫我真的看完**：
  - 數字類（片長／音量／鏡頭數）→ score_video.py 會擋 → 從來不出錯
  - 視覺類（解剖／角色數／招牌／崩壞）→ 全靠當下注意力 → 每輪都在打地鼠

所以這支腳本把視覺審查也變成硬閘門：抽出每一幀，逼你對每一幀**寫下你看到什麼**
（不是打勾，打勾可以閉著眼睛打），填完才發憑證，finish_video 沒憑證不給出片。

## 用法

    python auto\frame_gate.py <影片> --init     # 抽幀 + 產生待填的 gate 表
    （逐幀填寫產生的 _gate\gate_<hash>.md）
    python auto\frame_gate.py <影片> --verify   # 驗證填寫完整 → 發憑證

憑證綁影片內容 hash：影片重生過，舊憑證自動失效，必須重審。
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTO = Path(__file__).resolve().parent
GATE = AUTO / "_gate"

# 每幀必答：偷懶的答案（OK／無／-）會被驗證擋下來
PER_FRAME = [
    ("動物數", "畫面裡有幾隻動物？寫數字，只有一隻寫 1"),
    ("解剖", "主角的腿/身體/頭頸有沒有不合解剖處？看得到關節嗎？"),
    ("崩壞", "道具、背景、增生物、多餘肢體、合成痕跡？"),
]
# 全片答一次
WHOLE = [
    ("黑點眉連戲", "每個鏡頭黑點眉在哪、幾顆、大小一致嗎？逐鏡寫"),
    ("道具連戲", "同一個道具跨鏡頭有沒有自己變形/移位/材質跳動？"),
    ("結尾", "最後一秒是動作進行中戛然而止，還是靜止定格？"),
    ("一眼讀懂", "第 0 秒這一格，沒看標題的人知道發生什麼事嗎？"),
]
LAZY = re.compile(r"^\s*(ok|OK|無|沒有|正常|-|—|n/?a|待填|todo)?\s*$", re.I)


def vid_hash(video):
    h = hashlib.md5()
    with open(video, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()[:12]


def cmd_init(video, fps):
    vh = vid_hash(video)
    d = GATE / vh
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("f_*.png"):
        old.unlink()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                    "-vf", f"fps={fps}", str(d / "f_%02d.png")], check=True)
    frames = sorted(d.glob("f_*.png"))
    md = d / f"gate_{vh}.md"
    L = [f"# 逐幀 gate — {Path(video).name}", f"", f"影片 hash：`{vh}`　幀數：{len(frames)}"
         f"（{fps} fps 抽樣）", "",
         "**規則：每一格都要寫下你看到什麼。空白、OK、「無」一律不算，verify 會擋。**", ""]
    for f in frames:
        L.append(f"## {f.name}　`{d / f.name}`")
        for key, hint in PER_FRAME:
            L.append(f"- **{key}**（{hint}）：")
        L.append("")
    L.append("## 全片")
    for key, hint in WHOLE:
        L.append(f"- **{key}**（{hint}）：")
    L.append("")
    md.write_text("\n".join(L), encoding="utf-8")
    print(f"✅ 抽出 {len(frames)} 幀 → {d}")
    print(f"📝 逐幀填寫：{md}")
    print(f"   填完跑：python auto\frame_gate.py \"{video}\" --verify")
    return 0


def cmd_verify(video):
    vh = vid_hash(video)
    d = GATE / vh
    md = d / f"gate_{vh}.md"
    if not md.exists():
        print(f"✗ 找不到 gate 表（{md}）。先跑 --init")
        return 1
    blanks = []
    section = "?"
    for ln in md.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            section = ln[3:].split("　")[0].strip()
            continue
        m = re.match(r"- \*\*(.+?)\*\*（.*?）：(.*)$", ln)
        if m and LAZY.match(m.group(2)):
            blanks.append(f"{section} / {m.group(1)}")
    if blanks:
        print(f"✗ 還有 {len(blanks)} 格沒填（或填了偷懶答案），不發憑證：")
        for b in blanks[:12]:
            print(f"   - {b}")
        if len(blanks) > 12:
            print(f"   ...另外 {len(blanks) - 12} 格")
        return 1
    (GATE / f"pass_{vh}").write_text(f"gate passed for {Path(video).name}", encoding="utf-8")
    print(f"✅ 逐幀 gate 全部填寫完整 → 憑證 pass_{vh}")
    return 0


def has_pass(video):
    """給 finish_video 呼叫：這支影片有沒有通過逐幀 gate。"""
    try:
        return (GATE / f"pass_{vid_hash(video)}").exists()
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--fps", type=float, default=2)
    a = ap.parse_args()
    if not Path(a.video).is_file():
        print(f"✗ 找不到影片：{a.video}")
        return 1
    if a.init:
        return cmd_init(a.video, a.fps)
    if a.verify:
        return cmd_verify(a.video)
    print(f"逐幀 gate 狀態：{'✅ 已通過' if has_pass(a.video) else '❌ 未通過'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
