# -*- coding: utf-8 -*-
"""D10S1 藏破蛋 12.25 秒版音效配方（安靜文法＋對標動態）。

畫面時間軸（_build_d10.py 組裝版）：
  0.00-2.10   S1a 正面罪惡感直視（災難已成）
  2.10-2.95   INS1 哈士奇睡臉特寫       → whoosh 切入＋睡夢嗚咽（畫面有根據：目擊者睡死）
  2.95-5.15   S1b 撇頭裝沒事
  5.15-6.15   INS2 蛋盒證物特寫         → 輕 whoosh
  6.15-11.19  S2  主鏡：低頭盯蛋黃(6.4-8.6)→抬頭直視鏡頭「不是我」(8.9-11.19)
                                        → 7.15 輕濕黏（鼻子貼近蛋黃）
                                        → 8.90 吊牌一響對齊抬頭瞬間（實際幀校準）
  11.19-12.25 TAIL 慢動作踩蛋黃溜走     → 濕黏踩踏聲（畫面有根據：腳掌在蛋黃裡）
                                        → Taco 心虛嗚咽＝全片最響 punchline
  結尾動作中斷、不淡出（BGM nofade 檔 12.4s > 片長，載到底直接斷）

聲音規則（對標解剖）：
  - 歡樂 CC0 BGM 鋪滿（賢賢核可路線）＝零靜音段
  - 「靜音墊拍」：10.6s 起 BGM 壓低，讓 11.35s 的嗚咽爆最響（12dB 落差打在笑點）
  - 事件音全部畫面有根據；峰值目標 -0.5~-2.4dB；禁 atempo（NOPTS 地雷，變速先預渲染）

用法：python mix_d10s1.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    ("_prerendered/bgm_happyclappy_nofade.wav", 0.0, 6,
     "volume=enable='between(t,10.6,12.25)':volume=0.4", False),
    ("whoosh/Organic_Whoosh_14.mp3", 2.02, -9, "", False),
    ("_prerendered/nova_whimper_low.wav", 2.25, -10, "", False),
    ("whoosh/Whoosh_Rod_Pole_022.mp3", 5.07, -12, "", False),
    ("_prerendered/mud_splat_slow70.wav", 7.15, -12, "", False),  # 鼻子貼近蛋黃
    ("_prerendered/tag_at205.wav", 6.85, 4, "", False),      # 響在 8.90s：抬頭瞬間
    ("_prerendered/mud_splat_slow70.wav", 11.15, -6, "", False),  # 慢動作踩蛋黃
    ("_prerendered/taco_whine_d10.wav", 11.35, 29, "", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
