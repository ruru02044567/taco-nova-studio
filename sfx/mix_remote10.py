# -*- coding: utf-8 -*-
"""remote10 遙控器 10 秒（2026-09-04 賢賢指定：duo-scene-remote.jpg 起始圖、Wan 2.2 5B、多幀接龍）音效配方。
新文法：BGM 鋪滿（pop-on-ice，全庫首次使用）＋畫面錨點音＋punchline 前壓低再爆、結尾不淡出。
時間軸（依成片校正）：
  0.0-2.0   Taco 盯鏡頭壞笑，靜         → 只有 BGM
  2.0-5.0   用鼻子推遙控器三下          → 塑膠滑動聲 ×3（錨點：畫面在推）
  ~5.3      遙控器掉下桌（接龍段開頭）   → 掉落撞擊（全片最響前奏）
  ~5.9      Taco 彈直坐好               → 吊牌聲＋whoosh
  ~7.3      裝無辜（閉嘴）              → 小聲嗚咽（punchline 1）
  ~8.6      仍裝無辜（哈士奇沒抬頭，鼻息取消）→ 吊牌聲 punchline 2
  10.0      戛然而止
用法：python mix_remote10.py <影片> <輸出>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

RECIPE = [
    ("_prerendered/bgm_poponice_remote10_ducked.wav", 0.00, -6, "", False),
    ("_prerendered/remote10_slide.wav",   2.80, -10, "", False),
    ("_prerendered/remote10_slide.wav",   3.60, -9,  "", False),
    ("_prerendered/remote10_slide.wav",   4.40, -8,  "", False),
    ("_prerendered/remote10_slide.wav",   5.20, -7,  "", False),
    ("_prerendered/remote10_clatter.wav", 6.05, -3,  "", False),
    ("_prerendered/remote10_whoosh.wav",  6.35, -14, "", False),
    ("_prerendered/remote10_tag.wav",     6.50, -10, "", False),
    ("_prerendered/remote10_whine.wav",   7.80, 2,   "", False),
    ("_prerendered/remote10_tag.wav",     9.10, -6,  "", False),
    ("_prerendered/remote10_tag.wav",     9.80, -9,  "", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
