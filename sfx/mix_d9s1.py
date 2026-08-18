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
# v3（2026-08-19 規則 11/12 版）：三個事件全部「延遲烤進檔案」start=0，
# 不用 adelay（atempo/NOPTS 地雷徹底繞開）。每聲都有畫面根據：
#   2.05s 吊牌微響 ＝ S1 轉頭（項圈吊牌看得見）——新素材（車鑰匙微動），不再用舊手鍊聲
#   8.75s 吊牌微響 ＝ S2 轉頭（同一顆吊牌，同檔不同段）
#  11.05s Nova 低嗚 ＝ 結尾吐槽（閉嘴能發的音；降音高 0.88 裝大狗）——新素材 Wimper 26
# 剪接點 6.16s 刻意無聲：畫面上沒有東西掉落或噴濺（規則 11）。
RECIPE = [
    ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
     0.0, -21, "highpass=f=120,lowpass=f=4000,afade=t=in:st=0.8:d=1.5", True),
    ("_prerendered/tag_at205.wav",        0.0,  -1, "aecho=0.8:0.88:32:0.18,lowpass=f=7000", False),
    ("_prerendered/tag_at875.wav",        0.0,  -4, "aecho=0.8:0.88:32:0.18,lowpass=f=7000", False),
    ("_prerendered/nova_whine_at1105.wav", 0.0,  -5, "aecho=0.8:0.88:32:0.18,lowpass=f=7000", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
