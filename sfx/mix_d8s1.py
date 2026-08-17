# -*- coding: utf-8 -*-
"""D8S1 粉紅史萊姆的音效配方（5.04 秒靜態片）。

刻意**不改 mix.py**，而是 import 它的 build()：
D6 的教訓是「直接套用別支的配方」導致賢賢聽出「聲音怪怪的」——
配方必須對齊這一支自己的畫面事件，所以每支片一個檔比共用一個 RECIPES 表更誠實。

影片是**迴力鏢剪輯**（正播 0–2.40s ＋ 反播回首幀，全長 4.75 秒），
所以音效也要做成對稱的弧線 —— 轉折點 2.40s 是中心，兩側鏡像。
這是照 D7S1 `portal_boomerang` 的作法（聲音弧線跟著畫面弧線走）。

畫面事件（密集幀確認）：
  0.00-1.60s  定格，只有眼睛動；耳朵抖一下  → 底噪＋Nova 鼻息＋吊牌極輕一聲
  1.60-2.40s  泡泡升起（正播段結尾）        → 泡泡聲爬升
  2.40s       **轉折點**                    → 泡泡破掉，剛好蓋住剪接點
  2.40-4.75s  反播：動作倒回去              → 鏡像收乾淨，只留黏液微聲與呼吸

聲音方向：**濕、黏、安靜**。沒有低頻怪物（那是黑洞／傳送門的語彙），
沒有乾粉音（那是麵粉片的語彙），沒有爪步聲 —— 這支狗四腳黏死在原地，
生不出腳步聲才是對的。

用法：python mix_d8s1.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    # ── bed 層：同一間客廳，跟前面幾支維持聽感連續性 ──────────────
    ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
     0.0, -29, "highpass=f=90,lowpass=f=6000", True),
    ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
     0.0, -32, "lowpass=f=1300", True),

    # ── 0.00-1.60s（正播前段）：定格。Nova 的鼻息是唯一的生命跡象 ──────
    ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.50, -20, "atempo=0.7,lowpass=f=900", False),
    # 史萊姆自己在流動：泥漿聲放很慢＋重低通＝黏稠而不是水花
    ("liquid/mud_splat_heavy_03.mp3", 1.00, -24, "atempo=0.55,lowpass=f=1800", False),
    ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
     1.75, -19, "atrim=0:0.3,highpass=f=650", False),          # 耳朵一抖，銀吊牌輕碰

    # ── 2.20-2.55s：泡泡升起 → 破掉。破的那一下剛好蓋住 2.40s 的剪接點 ──
    ("liquid/water_bubble_19.mp3", 2.15, -18, "atempo=0.8,lowpass=f=2600", False),   # 升起
    ("liquid/water_bubble_19.mp3", 2.52, -15, "atempo=1.35,highpass=f=300,lowpass=f=4000", False),  # 破

    # ── 2.55-4.75s（反播段）：鏡像收乾淨，只留黏液微聲與呼吸 ────────────
    ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
     3.05, -21, "atrim=0:0.28,highpass=f=650", False),         # 耳朵回位，比去程更輕
    ("liquid/mud_splat_heavy_03.mp3", 3.75, -25, "atempo=0.5,lowpass=f=1600", False),
    ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 4.25, -21, "atempo=0.65,lowpass=f=800", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE):
        print("完成：", out)
