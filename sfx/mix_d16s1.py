# -*- coding: utf-8 -*-
"""D16S1 蜂蜜 12 秒版的音效配方（2026-08-22）。

聲音文法沿用 D9 建立、D13 驗證過的規則：不鋪全程底噪、只放少數真實物理
事件聲、punchline 前壓低再爆最響、結尾不淡出。

**素材去重（PUBLISH_GATE 規則 12：連續兩支片用同一個音效檔＝FAIL）**
D13S1（待審，排在這支前面）用了 bgm_happyclappy_nofade、d13_husky_snore
（馬 snort 渲染）、d13_feathers、d13_whoosh_in／back（knife_swing）、
d13_taco_whine（EFX Wimper 06）→ 這支一律避開，五個事件音全部換原始檔重渲染：

  d16_husky_snore  ← EFX SD Pig 02 Snort 18（豬鼻息，不是 D13 的馬）
  d16_taco_whine   ← EFX INT Dog Wimper 26（D13 用的是 06 號）
  d16_honey_ooze   ← mud_splat_heavy_03 慢到 0.25 倍＋低通 900Hz（黏稠流動）
  d16_whoosh_in    ← Whoosh_Fast_02（新下載）
  d16_whoosh_back  ← texture_whoosh_02_fast_02（新下載）

BGM 用 bgm_applecider_d10：上次用是 D12S1（8/21 發布），中間隔了 D13，
不構成「連續兩支」。⚠️ 但音樂庫至今只有兩首，再往下排一定會撞，見報告待辦。

**聲音要指得出畫面錨點（PUBLISH_GATE 規則 11）**
這支片畫面上只有三種會發聲的東西：持續流動的蜂蜜、睡著的哈士奇、Taco 本人。
所以只放這三種。沒有腳步聲、沒有碰撞聲（Wan 做不到，劇本刻意只留表情戲），
就不配。Taco 全程站著不動，只用閉嘴能發的嗚咽，不放吠叫。

畫面時間軸（12.21 秒，見 auto\_build_d16.py）：
  0.00-2.60   主鏡前段：轉頭直視鏡頭        → 蜂蜜流動＋哈士奇鼾聲
  2.60-4.10   INS1 罪證特寫：倒下的蜂蜜罐   → whoosh 進，蜂蜜聲拉近
  4.10-6.80   主鏡中段                      → whoosh 回、鼾聲第二次
  6.80-8.30   INS2 臉部 punch-in            → whoosh 進
  8.30-12.21  主鏡後段：密集頭部動作        → whoosh 回、蜂蜜第三次
  10.6 起     BGM 壓低墊拍 → 10.80 Taco 嗚咽爆最響 → 不淡出直接切斷

第一版全表比這裡高 4dB，score_video 量到整體 -15.4dB（要 -25～-16.5）FAIL，
全表 -4dB 才過 —— 跟 D13 第一版低 3dB 的情況相反，方向不同但都是量出來才知道。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    ("_prerendered/bgm_applecider_d10.wav", 0.0, -5,
     "volume=enable='between(t,10.6,12.3)':volume=0.42", False),
    ("_prerendered/d16_honey_ooze.wav", 0.35, -19, "", False),    # 罐口流出的蜂蜜
    ("_prerendered/d16_husky_snore.wav", 0.80, -22, "", False),   # 沙發上睡著的哈士奇
    ("_prerendered/d16_whoosh_in.wav", 2.48, -14, "", False),     # 切到罪證特寫（2.60）
    ("_prerendered/d16_honey_ooze.wav", 2.80, -15, "", False),    # 特寫裡蜂蜜正在流（離鏡頭最近）
    ("_prerendered/d16_whoosh_back.wav", 4.00, -20, "", False),   # 切回主鏡（4.10）
    ("_prerendered/d16_husky_snore.wav", 5.00, -25, "", False),   # 哈士奇第二次鼾聲
    ("_prerendered/d16_whoosh_in.wav", 6.68, -15, "", False),     # punch-in 到臉（6.80）
    ("_prerendered/d16_whoosh_back.wav", 8.20, -20, "", False),   # 切回主鏡（8.30）
    ("_prerendered/d16_honey_ooze.wav", 9.00, -20, "", False),    # 主鏡後段蜂蜜還在流
    ("_prerendered/d16_taco_whine.wav", 10.80, 5, "", False),     # punchline 全片最響
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
