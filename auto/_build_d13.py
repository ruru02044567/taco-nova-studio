# -*- coding: utf-8 -*-
r"""d13s1 羽毛 畫面組裝（2026-08-21）。

沿用 D12 打通的公式（D10 崩三輪換來的）：
  - 單狗演出：哈士奇只在背景睡著不動，不做大面積同框演出
  - 插入鏡要有資訊量：INS1 是爆開的抱枕＋羽毛堆（扣標題的罪證），不是零資訊空鏡
  - 結尾不放慢、不定格：直接在 S2 的動作進行中切斷（對標 8/8 如此）

跟 D12 的差別：D12 的 S2 已是近景所以不做臉部 punch-in；D13 兩鏡都是同一顆
中景（同一張起始圖），所以 INS2 改成臉部 punch-in，讓中段有一次景別變化。

時間軸（12.14 秒）：
  0.00-2.60   S1a 站在羽毛暴風中、慢慢轉頭直視鏡頭（第 0 秒即前提）
  2.60-3.80   INS1 爆開抱枕＋羽毛堆特寫（第二鉤子落在 2.6s，對標區間 1.6-2.6s）
  3.80-5.90   S1b 耳朵下垂慢眨（跳過 S1 的 2.60-2.80，jump cut 藏在插入鏡後）
  5.90-7.10   INS2 臉部 punch-in（取 S1 的 1.60-2.80：那段還正臉，3.6s 之後牠已經轉開了）
  7.10-12.14  S2 主鏡 5.04s，動作中斷收尾
              （實拍結果：Wan 沒演出 prompt 寫的「低頭看爪子」，
               給的是緩慢推近＋全程直視鏡頭。當收尾用反而更穩，予以採用）

用法：python auto\_build_d13.py [S1] [S2] [輸出]
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIPS = Path(__file__).resolve().parent / "clips"
s1_src = Path(sys.argv[1]) if len(sys.argv) > 1 else CLIPS / "d13s1.mp4"
s2_src = Path(sys.argv[2]) if len(sys.argv) > 2 else CLIPS / "d13s1_s2.mp4"
out_src = Path(sys.argv[3]) if len(sys.argv) > 3 else CLIPS / "d13s1-cut.mp4"

# 插入鏡裁框（1080x1920 座標系；486x864 是 9:16 的裁切窗，再放大回 1080x1920）
# 座標從 d13s1_scene.jpg（704x1280）量出來再乘 1080/704＝1.534：
#   狗臉中心 (340,520) → (521,780)；羽毛堆／破枕中心 (350,912) → (537,1400)
INS1 = "608:1080:236:840"   # 爆開的抱枕＋腳邊羽毛堆（罪證）。
# 第一版用 486x864（2.2 倍）試拍太緊：只看到狗胸口和一團白，讀不出「抱枕爆了」。
# 改成 608x1080（1.78 倍），把破枕、羽毛堆、狗腿一起框進來才扣得住標題。
INS2 = "486:864:278:348"    # 臉部 punch-in（沾羽毛的鼻子與黑點眉）

FC = f"""
[0:v]trim=0.00:2.60,setpts=PTS-STARTPTS[s1a];
[0:v]trim=0.40:1.60,setpts=PTS-STARTPTS,crop={INS1},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins1];
[0:v]trim=2.80:4.90,setpts=PTS-STARTPTS[s1b];
[0:v]trim=1.60:2.80,setpts=PTS-STARTPTS,crop={INS2},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4[ins2];
[1:v]trim=0.00:5.04,setpts=PTS-STARTPTS[s2];
[s1a][ins1][s1b][ins2][s2]concat=n=5:v=1:a=0[cat];
[cat]noise=alls=5:allf=t+u,unsharp=3:3:0.25[v]
"""
# noise+輕銳化：壓「純繪畫無毛感」的 AI 光滑（賢賢 8/19 裁示）

with tempfile.TemporaryDirectory(prefix="build13_") as td:
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
