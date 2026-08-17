# -*- coding: utf-8 -*-
"""D14S1 點金手的音效配方（5.21 秒迴力鏢靜態片）。

照 mix_d8s1.py 的家規：不改 mix.py，每支片一個配方檔，
聲音對齊**這一支自己**的畫面事件（密集幀確認過）。

影片是迴力鏢剪輯（正播 0–2.60s ＋ 反播回首幀，全長 5.21 秒），
轉折點 2.60s 是中心，聲音做成兩側鏡像的弧線。

畫面事件（密集幀確認）：
  0.00-0.60s  定格，Taco 盯鏡頭；0.6s 他眨了一次單眼   → 底噪＋Nova 鼻息
  1.20-2.60s  Nova 開始睡迷糊地抬頭（眼睛全程閉著）    → 睡嗚咽＋吊牌輕聲
  2.60s       **轉折點**（她抬到一半）                → 金光「叮」一聲蓋住剪接點
  2.60-5.21s  反播：她慢慢躺回去，Taco 在 4.5s 再眨一次 → 鏡像收乾淨

聲音方向：**安靜、貴氣、閃亮**。金色的語彙是高頻小「叮」，
不是低頻怪物（黑洞）、不是濕黏（史萊姆）、不是乾粉（麵粉）。
狗全程沒走動，不准有腳步聲。

用法：python mix_d14s1.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

BRACELET = "ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav"

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    # ── bed 層：同一間客廳，跟 d6/d7/d8 維持聽感連續性 ──────────────
    ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
     0.0, -29, "highpass=f=90,lowpass=f=6000", True),
    ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
     0.0, -32, "lowpass=f=1300", True),

    # ── 0.00-1.20s（正播前段）：定格，Nova 熟睡的鼻息 ────────────────
    ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.45, -20, "atempo=0.7,lowpass=f=900", False),

    # ── 1.20-2.60s：Nova 睡迷糊抬頭 ＋ Taco 微動吊牌輕碰 ─────────────
    ("dog-whimper/EFX INT Dog Wimper 06 A.M.wav", 2.20, -23,
     "atrim=0:0.6,atempo=0.85,lowpass=f=2200", False),           # 睡嗚咽，小聲
    (BRACELET, 1.70, -20, "atrim=0:0.3,highpass=f=650", False),  # 吊牌輕碰一聲

    # ── 2.60s 轉折點：金光「叮」，剛好蓋住剪接縫 ─────────────────────
    (BRACELET, 2.52, -18,
     "asetrate=48000*1.45,aresample=48000,atrim=0:0.4,highpass=f=1200", False),

    # ── 2.60-5.21s（反播段）：鏡像收乾淨 ────────────────────────────
    (BRACELET, 3.55, -22, "atrim=0:0.28,highpass=f=650", False),  # 吊牌回程更輕
    ("dog-whimper/EFX INT Dog Wimper 06 A.M.wav", 3.30, -26,
     "atrim=0:0.5,atempo=0.8,lowpass=f=1800", False),             # 嗚咽尾音
    ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 4.35, -21, "atempo=0.65,lowpass=f=850", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE):
        print("完成：", out)
