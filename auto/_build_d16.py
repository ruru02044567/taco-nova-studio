# -*- coding: utf-8 -*-
r"""d16s1 蜂蜜 畫面組裝（2026-08-22）。

跟 D13 的差別有兩個，都是這輪疊代的重點：

1. **主鏡改用多幀接龍的長鏡**（8/21 驗證：接縫 2.68，是舊做法硬接 24.56 的 1/9）。
   所以不再是「兩顆各自生的鏡硬接」，而是一顆 9.4 秒的連續鏡，中間只插一次
   罪證特寫做景別變化。對標 Tim & Jeffy 的「一顆主鏡撐全片」。

2. **全片套持續推鏡（zoompan）**。原因是量出來的：
   Wan 生的原片運動量中位數只有 0.0051，跟 D13S1 的 0.0052 一樣過不了 8/22 新
   立的門檻 0.0100。這輪先試「把環境運動寫進 videoPrompt」（蜂蜜持續流動），
   實測**完全無效**（0.0051，一個數字都沒動）。改用剪輯推鏡才拉得起來：
       推鏡係數 0.0008 → 0.0098（差一點）
       推鏡係數 0.0016 → 0.0122 ✅
       推鏡係數 0.0028 → 0.0139 ✅（對標實測值是 0.0137）
   ⚠️ zoompan 的坑：d=1 時 `zoom` 變數每幀重置，累積要用輸出幀號 `on`。
   用 z='min(zoom+K,…)' 量出來會跟原片一模一樣（三種強度都 0.0051）＝沒生效。

時間軸（約 12.2 秒，對標區間 12.1-14.9）：
  0.00-2.60   主鏡前段：轉頭直視鏡頭（第 0 秒即前提：狗站在蜂蜜湖裡）
  2.60-4.10   INS1 罪證特寫：倒下的蜂蜜罐（第二鉤子落在 2.6s，對標區間 1.6-2.6s）
  4.10-6.80   主鏡中段（jump cut 藏在插入鏡後）
  6.80-8.30   INS2 臉部 punch-in：中段的景別變化（沿用 D13 的做法）
  8.30-12.2   主鏡後段：密集頭部動作，動作進行中切斷收尾（不淡出）
  第一版只有 10.21 秒被 score_video 判 FAIL（要 12.1-14.9），加 INS2 補足。

用法：python auto\_build_d16.py [長鏡] [輸出]
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIPS = Path(__file__).resolve().parent / "clips"
src = Path(sys.argv[1]) if len(sys.argv) > 1 else CLIPS / "d16s1_長鏡.mp4"
out_src = Path(sys.argv[2]) if len(sys.argv) > 2 else CLIPS / "d16s1-cut.mp4"

# 罪證特寫裁框（1080x1920 座標系）：倒下的玻璃罐＋罐口流出的蜂蜜。
# 座標對長鏡 t=1.0s 那幀疊 100px 格線量出來：罐子佔 x700-1000 / y830-1080，
# 蜂蜜湖 y1000-1500，狗的前腳 x400-700。取 (760,1080) 當框心 → 罐子完整入框、
# 左緣帶到一隻沾蜂蜜的前腳、下緣帶到蜂蜜湖，罪證與主角的關係讀得出來。
# 第一版 608x1080 框心 (640,1150) 試過：把狗頭切掉一半、罐子卻只進來半個，作廢。
# D13 的教訓：放大倍率 2.2 倍太緊讀不出來，這裡是 1.93 倍。
INS1 = "460:816:620:800"   # 罪證純特寫：只有倒下的玻璃罐＋流出的蜂蜜，不含狗（2.35 倍）
INS2 = "486:864:300:430"   # 臉部 punch-in：黑點眉與沾蜂蜜的鼻子（2.22 倍）

# 鏡頭運動：Ken Burns（推鏡＋平移）。參數是量出來的，不是憑感覺調的——
# score_video 用的是 ffmpeg 的 scene_score（內容變化），對「純縮放」幾乎不敏感：
#     原始長鏡（無運鏡）            scene 中位數 0.0042
#     純推鏡 z+0.0028/幀            0.0057   ← 縮放拉不動這把尺
#     推鏡＋慢平移 x0.9/幀          0.0060
#     推鏡＋快平移 x2.2 y0.8/幀     0.0148 ✅ 過 0.0100
# 組裝後第二版全片 0.0099（差門檻 0.0001）：逐鏡看是兩個插入鏡在拖
# （INS 0.0054，主鏡段 0.0134），因為 INS 原本給的運鏡參數比主鏡弱一半。
# 把 INS 調到跟主鏡同級後反而更低（0.0097）：逐鏡發現最長那段 S5（93 幀）
# 從 0.0085 掉到 0.0075。根因是 **平移撞到畫面邊界後就靜止**——
# zoompan 的 x 上限是 (iw - iw/zoom)，平移越快越早撞，撞完剩下的幀完全不動。
# S5 用 2.8px/幀 只要 40 幀就撞界，後面 53 幀（57%）是死的，中位數當然被拉下去。
# 正解是讓平移速度配合可移動範圍：px ≈ (iw-iw/zoom)/2 ÷ 該段幀數，全程剛好用完。
#     S1/S3 62-65 幀、S5 93 幀，zoom 0.0040/幀 → px 1.6 全段都不撞界。
# 插入鏡另計：裁切放大後畫面內容本身幾乎不動（罐子和蜂蜜是靜物），
# 給主鏡同級的運鏡只量到 0.0030（低於 0.0050 警示線），要用兩倍的推鏡速度
# （0.0080/幀、36 幀推 29%）才拉得起來。特寫鏡頭快推本來就是強調罪證的手法。
# ⚠️ INS1 試過兩版都切到狗頭：往右搖推到後段只剩狗腿＋罐子；改往左搖仍頂到框頂。
# 根因是**裁框本身就含狗頭**，一放大必然頂出去。第三版改成 D13 那種「純罪證」
# 插入鏡：框裡只有倒下的罐子和流出的蜂蜜、完全不含狗，就沒有主體出框的問題。
# （D13 的教訓是「插入鏡要有資訊量、不能是空鏡」——罐子＋蜂蜜是罪證本身，有資訊量。）
# INS2 是臉部特寫、主體就在框心，往右搖沒問題，維持原樣。
# 灰階幀差那把尺量純推鏡是 0.0144、score_video 只認 0.0068 —— 兩把尺量的是
# 不同東西（一把認全域位移、一把認內容變化），一律以 score_video 為準。
PAN_X, PAN_Y, K = 1.6, 0.35, 0.0040


def zp(cap=1.45, px=PAN_X, py=PAN_Y, k=K):
    """推鏡＋平移。x/y 超出可移動範圍時 zoompan 會自行 clamp。"""
    return (f"zoompan=z='min(1+{k}*on,{cap})':d=1:"
            f"x='(iw-iw/zoom)/2+{px}*on':y='(ih-ih/zoom)/2+{py}*on':s=1080x1920:fps=24")


FC = f"""
[0:v]trim=0.00:2.60,setpts=PTS-STARTPTS,{zp()}[a];
[0:v]trim=0.60:2.10,setpts=PTS-STARTPTS,crop={INS1},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4,{zp(1.30,-2.0,-0.4,0.0070)}[i1];
[0:v]trim=2.70:5.40,setpts=PTS-STARTPTS,{zp()}[b];
[0:v]trim=3.00:4.50,setpts=PTS-STARTPTS,crop={INS2},scale=1080:1920:flags=lanczos,unsharp=5:5:0.4,{zp(1.35,3.0,0.6,0.0080)}[i2];
[0:v]trim=5.50:9.38,setpts=PTS-STARTPTS,{zp()}[c];
[a][i1][b][i2][c]concat=n=5:v=1:a=0[cat];
[cat]noise=alls=5:allf=t+u,unsharp=3:3:0.25[v]
"""
# noise+輕銳化：壓「純繪畫無毛感」的 AI 光滑（賢賢 8/19 裁示）

with tempfile.TemporaryDirectory(prefix="build16_") as td:
    t1, to = Path(td) / "s.mp4", Path(td) / "out.mp4"
    shutil.copy2(src, t1)          # 中文路徑坑：先複製到英文暫存再給 ffmpeg
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(t1),
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
