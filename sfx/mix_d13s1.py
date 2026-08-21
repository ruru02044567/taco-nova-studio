# -*- coding: utf-8 -*-
"""D13S1 羽毛 12 秒版的音效配方（2026-08-21）。

聲音文法沿用 D9 建立的規則（見 mix_d9s1.py）：不鋪全程底噪、只放少數真實
物理事件聲、punchline 前壓低再爆最響、結尾不淡出。

**素材去重（PUBLISH_GATE 規則 12：連續兩支片用同一個音效檔＝FAIL）**
D12S1（8/21 已發布）用了 bgm_applecider_d10、Organic_Whoosh_14、
Whoosh_Rod_Pole_022、tag_at205／tag_at875、taco_whine_d10 → 這支一律避開。
BGM 改用 happyclappy（上一次用是 D11S1，隔了一支，不算連續），
whoosh 改用庫裡第三支 knife_swing 降調當空氣聲，
嗚咽改成從原始 EFX 檔重新升調渲染的 d13_taco_whine（跟 D10/D12 用的是不同渲染）。

**聲音要指得出畫面錨點（PUBLISH_GATE 規則 11）**
這支片的畫面上只有三種會發聲的東西：飄浮的羽毛、睡著的哈士奇、Taco 本人。
所以只放這三種聲音。沒有踩踏、沒有碰撞（Wan 做不到，劇本刻意只留表情戲），
就不配腳步聲與撞擊聲。

⚠️ mix.py 8/19 起的硬閘門：extra 欄不准出現 atempo 與非零起點 atrim
（adelay 會被 NOPTS 抵銷＝事件音靜默消失）。所以變速素材一律先渲染進
lib\_prerendered\ 再引用，這支用到的五個 d13_* 檔就是這樣來的。

畫面時間軸（12.125 秒）：
  0.00-2.60   S1a 站在羽毛暴風中、慢慢轉頭直視鏡頭   → 哈士奇鼾聲＋羽毛細聲
  2.60-3.80   INS1 破枕＋羽毛堆特寫（第二鉤子）       → 轉場 whoosh
  3.80-5.90   S1b 慢眨、開始把頭轉開                  → 羽毛細聲第二次
  5.90-7.10   INS2 臉部 punch-in（沾羽毛的鼻子）      → punch-in whoosh
  7.10-12.13  S2 主鏡：緩慢推近＋全程直視，動作中斷收尾
  10.8 起     BGM 壓低墊拍 → 11.35 Taco 嗚咽爆最響 → 不淡出直接切斷

第一版全體低 3dB，score_video 量到整體 -26.4dB（要 -25～-16.5）、峰值 -3.5dB
（要 >=-3.0）兩項 FAIL。全表 +3dB 重混才過 —— 這就是為什麼自審要用量的，
不是用聽的：低 1.4dB 人耳分不出來，演算法分得出來。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    ("_prerendered/bgm_happyclappy_nofade.wav", 0.0, -1,
     "volume=enable='between(t,10.8,12.2)':volume=0.42", False),
    ("_prerendered/d13_husky_snore.wav", 0.55, -17, "", False),    # 背景睡著的哈士奇
    ("_prerendered/d13_feathers.wav", 0.90, -14, "", False),       # 空中飄的羽毛
    ("_prerendered/d13_whoosh_in.wav", 2.52, -10, "", False),      # 切到罪證特寫
    ("_prerendered/d13_whoosh_back.wav", 3.72, -16, "", False),    # 切回主鏡
    ("_prerendered/d13_feathers.wav", 4.60, -17, "", False),       # 羽毛第二次（慢眨時）
    ("_prerendered/d13_whoosh_in.wav", 5.82, -11, "", False),      # punch-in 到臉
    ("_prerendered/d13_husky_snore.wav", 7.60, -21, "", False),    # 哈士奇還在睡（S2 裡看得到）
    ("_prerendered/d13_taco_whine.wav", 11.35, 9, "", False),      # punchline 全片最響
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
