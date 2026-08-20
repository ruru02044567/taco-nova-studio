# -*- coding: utf-8 -*-
r"""d12s1 藍腳印 畫面組裝（2026-08-20）。

跟 D10 的差別（都是 D10 三輪失敗學到的）：
  - 單狗：Nova 完全不入鏡。雙狗大面積同框是 Wan 解剖崩壞的根源
    （賢賢 8/20 抓到 D10 插入鏡裡哈士奇是一團沒關節的白肉）
  - 插入鏡有資訊量：INS1 是藍腳印（扣標題的罪證），不是 D10 那種零資訊空鏡
  - 結尾不放慢、不定格：D10 被冷觀眾判「最後 2.5 秒靜止」，這支直接在
    S2 的動作進行中切斷（對標 8/8 如此）

時間軸（12.14 秒）：
  0.00-2.60   S1a 站在藍漆裡、慢慢轉頭直視鏡頭（第 0 秒即前提）
  2.60-3.80   INS1 藍腳印特寫（第二鉤子落在 2.6s，對標區間 1.6-2.6s）
  3.80-5.90   S1b 耳朵下垂慢眨（跳過 S1 的 2.60-2.80，jump cut 藏在插入鏡後）
  5.90-7.10   INS2 藍腳掌特寫（罪證；S2 已是近景，不再用臉部 punch-in 免重複）
  7.10-12.14  S2 主鏡 5.04s（低頭看自己的藍腳掌→抬頭直視），動作中斷收尾

用法：python auto\_build_d12.py [S1] [S2] [輸出]
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIPS = Path(__file__).resolve().parent / "clips"
s1_src = Path(sys.argv[1]) if len(sys.argv) > 1 else CLIPS / "d12s1.mp4"
s2_src = Path(sys.argv[2]) if len(sys.argv) > 2 else CLIPS / "d12s1_s2.mp4"
out_src = Path(sys.argv[3]) if len(sys.argv) > 3 else CLIPS / "d12s1-cut.mp4"

# 插入鏡裁框（1080x1920 座標系；486x864 是 9:16 的裁切窗，再放大回 1080x1920）
INS1 = "100:1000"    # 藍腳印特寫（畫面下方腳印區）
INS2 = "330:850"     # 藍腳掌＋漆灘特寫（罪證，引出 S2 低頭看自己的腳）

FC = f"""
[0:v]trim=0.00:2.60,setpts=PTS-STARTPTS[s1a];
[0:v]trim=0.40:1.60,setpts=PTS-STARTPTS,crop=486:864:{INS1},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins1];
[0:v]trim=2.80:4.90,setpts=PTS-STARTPTS[s1b];
[0:v]trim=3.60:4.80,setpts=PTS-STARTPTS,crop=486:864:{INS2},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins2];
[1:v]trim=0.00:5.04,setpts=PTS-STARTPTS[s2];
[s1a][ins1][s1b][ins2][s2]concat=n=5:v=1:a=0[cat];
[cat]noise=alls=5:allf=t+u,unsharp=3:3:0.25[v]
"""
# noise+輕銳化：壓「純繪畫無毛感」的 AI 光滑（賢賢 8/19 裁示）

with tempfile.TemporaryDirectory(prefix="build12_") as td:
    t1, t2, to = Path(td) / "s1.mp4", Path(td) / "s2.mp4", Path(td) / "out.mp4"
    shutil.copy2(s1_src, t1)
    shutil.copy2(s2_src, t2)
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(t1), "-i", str(t2),
                        "-filter_complex", FC, "-map", "[v]", "-an",
                        "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", str(to)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not to.exists():
        print("[X] 組裝失敗：", (p.stderr or "")[-800:])
        sys.exit(1)
    shutil.copy2(to, out_src)

dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(out_src)],
                     capture_output=True, text=True).stdout.strip()
print(f"[ok] 組裝完成：{out_src.name}  片長 {dur}s")
