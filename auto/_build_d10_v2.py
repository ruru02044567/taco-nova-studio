# -*- coding: utf-8 -*-
r"""d10s1 破蛋（單狗復活版）畫面組裝（2026-08-21）。

跟 8/19 那版 _build_d10.py 的差別 —— 那版是雙狗時代寫的：
  - 舊版 INS1 是「哈士奇睡臉特寫」，賢賢抓到那是一團沒關節的白肉。
    新劇本 Nova 完全不入鏡，這顆插入鏡直接拿掉。
  - 兩顆插入鏡都改成「有資訊量的罪證」（D12S1 的成功公式第 5 條）：
    INS1 打翻的蛋盒、INS2 沾黃的腳掌泡在蛋液裡。

S2 是多幀接龍生的，前 17 格（0.71s）是餵進去那 17 格被 VAE 還原回來的版本，
跟 S1 原檔差一個來回誤差。這裡用 trim 從 0.71 起跳把它切掉 ——
接縫色差被前面那顆 INS2 隔開，看不到。

時間軸（12.17 秒）：
  0.00-2.80   S1a  站在蛋液正中央、慢慢轉頭直視鏡頭（第 0 秒即前提）
  2.80-4.25   INS1 打翻的蛋盒特寫（第二鉤子）
  4.25-6.39   S1b  接 S1 的 2.90-5.04（jump cut 藏在插入鏡後）
  6.39-7.84   INS2 沾黃腳掌＋蛋液特寫（罪證，引出 S2 的低頭）
  7.84-12.17  S2   主鏡 4.33s（低頭聞蛋液→抬頭直視），動作中斷收尾

用法：python auto\_build_d10_v2.py [S1] [S2] [輸出]
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

# 插入鏡裁框（1080x1920 座標系；486x864 是 9:16 的裁切窗，再放大回 1080x1920）
# 座標是對 d10s1.mp4 第 10 幀畫格線量的：蛋盒 x0-420 y720-960、腳掌 x480-660 y1020-1180
INS1 = "0:600"      # 打翻的蛋盒（畫面左側）＋ 旁邊的蛋液
INS2 = "327:900"    # 狗的沾黃腳掌泡在蛋液裡（罪證）

FC = f"""
[0:v]trim=0.00:2.80,setpts=PTS-STARTPTS[s1a];
[0:v]trim=0.30:1.75,setpts=PTS-STARTPTS,crop=486:864:{INS1},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins1];
[0:v]trim=2.90:5.04,setpts=PTS-STARTPTS[s1b];
[0:v]trim=3.30:4.75,setpts=PTS-STARTPTS,crop=486:864:{INS2},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins2];
[1:v]trim=0.71:5.04,setpts=PTS-STARTPTS[s2];
[s1a][ins1][s1b][ins2][s2]concat=n=5:v=1:a=0[cat];
[cat]noise=alls=5:allf=t+u,unsharp=3:3:0.25[v]
"""
# noise+輕銳化：壓「純繪畫無毛感」的 AI 光滑（賢賢 8/19 裁示）

with tempfile.TemporaryDirectory(prefix="build10_") as td:
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
