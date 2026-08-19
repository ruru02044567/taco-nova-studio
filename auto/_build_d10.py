# -*- coding: utf-8 -*-
r"""d10s1 畫面組裝（2026-08-19，對標結構）。

時間軸（對標製作標準）：
  0.00-2.10   S1a 正面罪惡感直視（第 0 秒即前提：站在蛋黃災難中央）
  2.10-2.95   INS1 哈士奇睡臉特寫（第二鉤子 2.1s 起，0.85s；左上帶到犯人腳掌）
  2.95-5.15   S1b 撇頭裝沒事（跳過 S1 的 2.10-2.40，jump cut 藏在插入鏡後）
  5.15-6.15   INS2 蛋盒證物特寫（1.0s，d9 酒杯特寫同款第二特寫位）
  6.15-11.19  S2  整段主鏡 5.04s ≥3.8s（看蛋黃→耳朵垂→看哈士奇→回看鏡頭）
  11.19-12.25 TAIL S1 尾段 0.65x 慢動作「踩著蛋黃溜走」，動作中斷收尾（不定格不淡出）

插入鏡裁框（S1 影片區域裁切，有真實呼吸微動；d9 精華：486x864 → 1080x1920）：
  INS1 (560,980)-(1046,1844)   INS2 (594,340)-(1080,1204)

用法：python auto\_build_d10.py [S1路徑] [S2路徑] [輸出路徑]
預設 S1=clips\d10s1.mp4、S2=clips\d10s1_s2.mp4、輸出=clips\d10s1-cut.mp4
中文路徑坑：全部先複製到英文暫存再餵 ffmpeg。
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIPS = Path(__file__).resolve().parent / "clips"
s1_src = Path(sys.argv[1]) if len(sys.argv) > 1 else CLIPS / "d10s1.mp4"
s2_src = Path(sys.argv[2]) if len(sys.argv) > 2 else CLIPS / "d10s1_s2.mp4"
out_src = Path(sys.argv[3]) if len(sys.argv) > 3 else CLIPS / "d10s1-cut.mp4"

FC = """
[0:v]trim=0.00:2.10,setpts=PTS-STARTPTS[s1a];
[0:v]trim=0.60:1.45,setpts=PTS-STARTPTS,crop=486:864:560:980,scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins1];
[0:v]trim=2.40:4.60,setpts=PTS-STARTPTS[s1b];
[0:v]trim=0.20:1.20,setpts=PTS-STARTPTS,crop=486:864:594:340,scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins2];
[1:v]trim=0.00:5.04,setpts=PTS-STARTPTS[s2];
[0:v]trim=4.35:5.04,setpts=(PTS-STARTPTS)/0.65[tail];
[s1a][ins1][s1b][ins2][s2][tail]concat=n=6:v=1:a=0[cat];
[cat]noise=alls=5:allf=t+u,unsharp=3:3:0.25[v]
"""
# noise+輕銳化：壓「純繪畫無毛感」的 AI 光滑（賢賢 8/19 回饋），
# 細顆粒讓平坦色塊出現底紋，手機上看起來像實拍雜訊。

with tempfile.TemporaryDirectory(prefix="d10cut_") as td:
    td = Path(td)
    t1, t2, to = td / "s1.mp4", td / "s2.mp4", td / "out.mp4"
    shutil.copy2(s1_src, t1)
    shutil.copy2(s2_src, t2)
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", t1, "-i", t2,
         "-filter_complex", FC.strip().replace("\n", ""),
         "-map", "[v]", "-an", "-r", "24",
         "-c:v", "libx264", "-preset", "slow", "-crf", "17",
         "-pix_fmt", "yuv420p", to],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not to.exists():
        print("[X] 組裝失敗：", (p.stderr or "")[-600:])
        sys.exit(1)
    shutil.copy2(to, out_src)

d = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                    "-of", "csv=p=0", out_src],
                   capture_output=True, text=True).stdout.strip()
print(f"[ok] 組裝完成：{out_src.name}  片長 {d}s")
