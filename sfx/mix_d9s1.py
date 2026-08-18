# -*- coding: utf-8 -*-
"""D9S1 紅酒地毯 12 秒雙鏡版的音效配方（新聲音文法第一支）。

新文法出處：2026-08-18 賢賢聽出四支片「聲音超奇怪」，逐秒實測他打 9 分的
標準片（Chihuahua Pushes Remote，10 秒）得到的數據：
    0s -91dB（靜音開場）→ 1-3s -42~-63（幾乎無聲）→ 4s -27（落地咚）
    → 7s -52（回歸安靜）→ 8-9s -17（結尾 Nova 吐槽，全片最大聲）
    整體平均 -25.3 dB，峰值打滿＝動態範圍極大。

規則（跟舊配方的差異）：
  1. 不鋪全程底噪——只留 -45dB 的空氣感讓噪聲地板活著，其他時間就是安靜
  2. 每支片只放少數「真實物理事件」聲，對齊畫面
  3. 禁止豬／馬採樣冒充狗呼吸（舊配方最怪的來源）
  4. 結尾允許一聲真實狗聲當 punchline（全片最大聲）
  5. build() 帶 target_lufs=None——不准正規化拉大聲，安靜就是設計

畫面時間軸（12.07 秒剪輯版）：
  0.00-1.82  S1 慢速開場：災難定格   → 靜音
  2.0-2.9    S1 轉頭看 Nova          → 吊牌輕響一聲
  5.1-6.0    S1 撇頭裝沒事           → 極輕吊牌
  6.16       ── 硬切 ──              → 濕黏「啪唧」跨在剪接點（污漬變大的暗示）
  6.7-7.7    S2 低頭看著滿毯災難     → 安靜
  8.7-9.7    S2 抬頭轉向鏡頭瞪大眼   → 吊牌輕響
  10.2-12.0  S2 慢速定格凝視         → Nova 一聲嗚咽吐槽（全片最大聲）

用法：python mix_d9s1.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    # 空氣感：勉強高於數位靜音的噪聲地板，不是「環境音」
    ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
     0.0, -45, "highpass=f=120,lowpass=f=4000,afade=t=in:st=0:d=1.5", True),

    # S1 轉頭看 Nova → 吊牌輕碰
    ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
     2.05, -24, "atrim=0:0.3,highpass=f=650", False),
    # S1 撇頭 → 更輕的一聲
    ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
     5.30, -27, "atrim=0:0.25,highpass=f=650", False),

    # 剪接點 6.16s：濕黏一聲「啪唧」——動作發生在剪接裡，聲音替畫面補完
    # ⚠ 用預渲染檔：ffmpeg 7.1.1 的 atempo 會讓後面的 adelay 整個失效（NOPTS 地雷），
    #    配方 extra 裡禁用 atempo／atrim，變速素材一律先渲染進 lib\_prerendered\
    ("_prerendered/mud_splat_slow70.wav", 6.10, -17, "", False),

    # S2 抬頭轉向鏡頭 → 吊牌
    ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
     8.75, -25, "atrim=0:0.3,highpass=f=650", False),

    # 結尾 punchline：Nova 的嗚咽吐槽（真狗聲，全片最大聲，音高壓低裝大狗）
    ("_prerendered/nova_whimper_at1105.wav", 0.0, -6, "", False),  # 延遲已烤進檔案（見下註）
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
