# -*- coding: utf-8 -*-
"""D12S1 藍腳印 12 秒版的音效配方（2026-08-20）。

聲音文法沿用 D9 建立的規則（見 mix_d9s1.py）：不鋪全程底噪、只放少數真實
物理事件聲、punchline 前壓低再爆最響、結尾不淡出。

**素材去重（PUBLISH_GATE 規則 12：連續兩支片用同一個音效檔＝FAIL）**
D11S1（8/20 已發布）用了 happyclappy BGM、tag_hit_07、mud_splat_slow70、
nova_whimper_low → 這支一律避開，改用 apple-cider BGM（audition.py 量測
94 分冠軍：100 BPM、F 大調、木琴亮度）與另一組吊牌／狗聲。

這支片沒有踩踏或碰撞動作（Wan 做不到，劇本刻意只留表情戲），所以不放濕黏聲——
畫面上沒有的東西不配音，是 PUBLISH_GATE 規則 11「聲音要指得出畫面錨點」。

畫面時間軸（12.14 秒）：
  0.00-2.60   S1a 站在藍漆裡、慢慢轉頭直視鏡頭（第 0 秒即前提）
  2.60-3.80   INS1 藍腳印特寫（第二鉤子）      → 轉場 whoosh
  3.80-5.90   S1b 耳朵下垂、慢眨               → 吊牌輕響
  5.90-7.10   INS2 punch-in 到臉（罪證表情）    → 轉場 whoosh
  7.10-12.14  S2 低頭看自己的藍腳掌→抬頭直視    → 抬頭吊牌一響
  11.0 起     BGM 壓低墊拍 → 11.4 嗚咽爆最響 → 動作中斷收尾
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    ("_prerendered/bgm_applecider_d10.wav", 0.0, -3,
     "volume=enable='between(t,11.0,12.2)':volume=0.4", False),
    ("whoosh/Organic_Whoosh_14.mp3", 2.52, -14, "", False),   # 切腳印特寫
    ("_prerendered/tag_at205.wav", 1.75, 2, "", False),       # 響在 3.80：轉頭定格
    ("whoosh/Whoosh_Rod_Pole_022.mp3", 5.82, -15, "", False), # punch-in
    ("_prerendered/tag_at875.wav", 1.05, -2, "", False),      # 響在 9.80：抬頭瞬間
    ("_prerendered/taco_whine_d10.wav", 11.40, 29, "", False),  # punchline 全片最響
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
