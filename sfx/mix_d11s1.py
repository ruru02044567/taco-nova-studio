# -*- coding: utf-8 -*-
"""D11S1 熊貓油漆 13 秒雙鏡版的音效配方（新聲音文法，沿 mix_d9s1 v7b 規則）。

畫面時間軸（13.00 秒剪輯版：S2 慢開場＋S2 正常＋硬切＋S1 慢收尾）：
  0.00-2.63  S2 慢速開場：熊貓 Taco 坐在油漆灘裡看鏡子   → 靜音（BGM 低鋪）
  2.63-7.05  S2 正常速：歪頭自我欣賞＋抬下巴 pose        → 2.7s 吊牌輕響一聲
  7.05       ── 硬切 ──                                → 濕黏「啪唧」跨在剪接點
  7.05-11.2  S1：轉頭面向鏡頭、得意直視、慢眨眼          → 9.4s 極輕吊牌
  11.2-13.0  S1 慢速收尾：定住得意臉                    → 鏡中 Nova 一聲低嗚咽吐槽（全片最大聲）

規則沿襲 v7b：不鋪底噪、少數真實事件、結尾生物吐槽、target_lufs=None 不正規化。
用法：python mix_d11s1.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否 loop 鋪底)
# 增益整體 +4～5（首版峰值只有 -6.0dB 被 score 擋下；對標峰值要打到 -0.5~-2.4，
# 防爆表交給 limiter -1.5）
RECIPE = [
    ("_prerendered/bgm_happyclappy_nofade.wav", 0.0, 6,
     "volume=enable='between(t,10.9,13.0)':volume=0.30", True),
    ("_prerendered/tag_hit_07.wav",       2.70, -6, "", False),
    ("_prerendered/mud_splat_slow70.wav", 6.95, -4, "", False),
    ("_prerendered/tag_hit_07.wav",       9.40, -10, "", False),
    # 結尾吐槽要當全片最大聲（v7b 文法），首兩版被 BGM 蓋掉，+13 站出來
    ("_prerendered/nova_whimper_low.wav", 11.20, 13, "", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
