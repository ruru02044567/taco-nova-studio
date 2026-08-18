# -*- coding: utf-8 -*-
"""D9S1 紅酒地毯的音效配方（6.17 秒：慢速開頭 1.8s ＋ 正常速 4.34s）。

對齊的是**剪輯後**的時間軸（clips\d9s1-edit.mp4，慢速開頭版），
不是 Wan 原片——原片 t 秒對應剪輯後：t<0.7 → t*2.6；t>=0.7 → t+1.12。

畫面事件（真 v3 密集幀確認，19:24 版）：
  0.00-1.80s  慢速定格：酒杯倒著、酒漬滿毯、Taco 前爪抬著站在正中
              → 只有環境底噪＋Nova 鼻息＋一次極輕的濕地毯微聲
  1.90-2.75s  Taco 轉頭看向 Nova（心虛確認有沒有被看到）
              → 吊牌輕響一聲
  3.80-4.60s  面對鏡頭裝無辜瞪大眼（全片核心 beat）
              → Nova 一聲鼻哼（審判感），其他全靜
  4.75-5.60s  撇頭裝沒事（動量峰值 4.75s）
              → 吊牌再輕一聲＋濕毯微聲收尾
  5.60-6.17s  定格餘韻 → 只留呼吸

聲音方向：**濕、安靜、尷尬**。紅酒是已經潑完的——不要倒酒聲、
不要玻璃聲（杯子從頭到尾沒動）；狗四腳踩在濕毯上，只有極輕的
濕纖維聲。沒有低頻怪物（那是黑洞／傳送門語彙），沒有乾粉音。

用法：python mix_d9s1.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    # ── bed 層：同一間客廳，跟 d8s1 同底保持聽感連續性 ──────────────
    ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
     0.0, -29, "highpass=f=90,lowpass=f=6000", True),
    ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
     0.0, -32, "lowpass=f=1300", True),

    # ── 0.00-1.80s（慢速定格）：Nova 的鼻息是唯一的生命跡象 ──────────
    ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.55, -21, "atempo=0.7,lowpass=f=900", False),
    # 濕地毯極輕微聲：泥漿聲放很慢＋重低通＝濕纖維，不是水花
    ("liquid/mud_splat_heavy_03.mp3", 1.30, -26, "atempo=0.5,lowpass=f=1500", False),

    # ── 1.90-2.75s：轉頭看 Nova → 吊牌輕響 ────────────────────────
    ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
     1.95, -19, "atrim=0:0.3,highpass=f=650", False),

    # ── 3.80-4.60s：面對鏡頭裝無辜 → Nova 鼻哼一聲當審判 ────────────
    ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 4.05, -19, "atempo=0.85,lowpass=f=1100", False),

    # ── 4.75-5.60s：撇頭裝沒事 → 吊牌＋濕毯收尾 ────────────────────
    ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
     4.80, -20, "atrim=0:0.28,highpass=f=650", False),
    ("liquid/mud_splat_heavy_03.mp3", 5.35, -27, "atempo=0.5,lowpass=f=1300", False),

    # ── 5.60-6.17s：餘韻只留呼吸 ──────────────────────────────────
    ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 5.75, -23, "atempo=0.6,lowpass=f=800", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE):
        print("完成：", out)
