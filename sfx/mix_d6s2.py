# -*- coding: utf-8 -*-
"""D6S2 盆栽續集（11.62 秒連續接龍版）音效配方 v2。

v1 的失敗（2026-08-28 賢賢打槍「音效明顯跟不上、用舊的」）：
用了 d4/d6 時代的「底噪＋細碎事件」舊文法，聲音主體比頻道第二部片（d16）
小 6~10 dB、開頭四秒近乎全空。v2 改用 D9 立規、D13/D16 驗證的新文法：
**BGM 鋪滿（Profile A 音樂驅動）＋少數大聲的畫面錨點音＋punchline 前壓低再爆最響、
結尾不淡出。**

畫面時間軸（剪點＝接龍續接幀，動作連續）：
  0.00-3.50   【第一幕】慌張扭動踩土、甩頭、尾巴翹起（運動量 0.235）
  3.50        接點（同幀續接）→【第二幕】旋身踢土、土花飛濺，背影大搖大擺走遠
  7.96        接點 →【第三幕】停步、僵住、緩緩回頭裝無辜——
  ~10.0       Nova 在後方坐起、直勾勾瞪著（punchline）
  11.62       結束，戛然而止

素材防撞（規則 12：連續兩支不重複）：最近發布的 d13 用 happyclappy BGM、
馬 snort、Wimper06、knife_swing → 本支 BGM 用 **playful_mood（全庫首次使用）**、
Nova 鼻息用豬 snort 新渲染、嗚咽用 Wimper26 升調渲染（d16 是原速）、
whoosh 用 Organic_14／Rod_Pole（d13 沒用過）。

規則 11（錨點）自查：爪步聲＝畫面在走、踢土聲＝畫面在踢、吊牌聲＝畫面甩頭、
嗚咽＝Taco 閉嘴回頭（閉嘴可發）、鼻息＝Nova 坐起（閉嘴可發）。無憑空音。

用法：python mix_d6s2.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    # ── BGM 鋪滿全程（Profile A）；9.0 起壓低給 punchline 讓路，結尾不淡出 ──
    # （v3 片長 12.125s，punch-in 剪點 1.6/2.6/9.5/10.7，尾段 10.7 起放慢 2 倍）
    ("_prerendered/d6s2v3_bgm_ducked.wav", 0.0, -6, "", False),
    # ↑ 壓低已直接烤進檔案（9.0-11.4 ×0.40、11.4 後 ×0.15）：
    #   volume enable 濾鏡經混音鏈沒生效（結尾 stinger 實測仍 -1.5dB），預渲染才是正解

    # ── punch-in 1（1.6 切入臉部特寫、2.6 切回）──
    ("_prerendered/d6s2v2_whoosh_b.wav", 1.52, -15, "", False),
    ("_prerendered/d6s2v2_whoosh_a.wav", 2.56, -17, "", False),

    # ── 第一幕 0.00-3.50：慌張扭動。爪步／土粒／吊牌，比 v1 提 4~5 dB ──
    ("_prerendered/d6s2_paw_a.wav",   0.25, -14, "", False),
    ("_prerendered/d6s2_crack_a.wav", 0.80, -14, "", False),
    ("_prerendered/d6s2_tag_a.wav",   1.10, -12, "", False),
    ("_prerendered/d6s2_paw_b.wav",   1.60, -13, "", False),
    ("_prerendered/d6s2_drop_a.wav",  2.20, -14, "", False),
    ("_prerendered/d6s2_tag_b.wav",   2.70, -13, "", False),
    ("_prerendered/d6s2_paw_c.wav",   3.05, -13, "", False),

    # ── 3.50 接點：旋身＋踢土爆發（whoosh 蓋接點，土花跟上）──
    ("_prerendered/d6s2v2_whoosh_a.wav", 3.42, -13, "", False),
    ("_prerendered/d6s2_mud_a.wav",      3.58, -12, "", False),
    ("_prerendered/d6s2_crack_d.wav",    3.75, -12, "", False),
    ("_prerendered/d6s2_drop_c.wav",     4.05, -13, "", False),

    # ── 第二幕 4.2-7.96：大搖大擺走遠。闊步爪聲漸遠（音量遞減）＋吊牌 ──
    ("_prerendered/d6s2_paw_d.wav",   4.40, -14, "", False),
    ("_prerendered/d6s2_tag_a.wav",   5.30, -15, "", False),
    ("_prerendered/d6s2_paw_c.wav",   5.80, -16, "", False),
    ("_prerendered/d6s2_drop_b.wav",  6.40, -17, "", False),
    # （6.90 的爪步已刪：驗片師抓到 8 秒後站定仍有腳步聲的錨點違規風險）

    # ── 7.96 接點：停步。whoosh 反向＋一聲土屑落定 ──
    ("_prerendered/d6s2v2_whoosh_b.wav", 7.90, -15, "", False),
    ("_prerendered/d6s2_drop_b.wav",     8.15, -16, "", False),

    # ── 第三幕 8.2-12.13：僵住回頭。BGM 已壓低，9.6 嗚咽、10.6 Nova 鼻息爆點 ──
    ("_prerendered/d6s2v2_whoosh_a.wav",   9.45, -14, "", False),  # punch-in 到臉（9.5）
    ("_prerendered/d6s2v2_taco_whine.wav", 9.58, 6, "", False),    # 回頭裝無辜，全片第二響
    ("_prerendered/d6s2v2_nova_snort.wav", 10.58, 9, "", False),   # Nova 品頭論足，全片最響（峰值打近滿刻度）
    ("_prerendered/d6s2_tag_c.wav",        11.70, -16, "", False), # 慢放區內，吊牌輕響收尾
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE, target_lufs=None):
        print("完成：", out)
