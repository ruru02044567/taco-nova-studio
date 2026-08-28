# -*- coding: utf-8 -*-
"""D6S2 盆栽續集（11.67 秒三幕剪輯）的音效配方。

畫面事件（密集幀確認，H3 生成、三段硬切）：
  0.00-5.00s  【第一幕・被抓包】s2：Taco 在土堆裡慌張扭動、踩土、
              甩頭左右看、尾巴翹起——全片運動量最大的一段
  5.00s       硬切 → 【第二幕・否認】s3a：昂首挺胸裝清高（安靜段）
  7.50s       硬切 → 【第三幕・走人】s3b：踢土、轉身、大搖大擺走開
  9.17s       硬切 → 【結尾・目擊者】s1 尾段：鏡頭切回，Nova 根本醒著
              坐起來盯著看，Taco 站在原地僵住——突然安靜是這一拍的笑點
  11.67s      結束

聲音方向：**乾土、爪步、吊牌**（沿用 d4/d6 的土系語彙），
三個剪接點各用一聲土響蓋住；結尾反向操作——瞬間收乾淨，
只留 Nova 一聲重重的鼻息（她在品頭論足），安靜本身是 punchline。

⚠ mix.py 硬閘門：atempo／非零起點 atrim 必須預渲染。
本配方所有變速/裁切素材已烤進 lib/_prerendered/d6s2_*.wav（2026-08-28），
extra 欄一律留空或只放 highpass/lowpass。

用法：python mix_d6s2.py <影片> <輸出>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mix  # noqa: E402

# (檔案, 起始秒, dB, ffmpeg 濾鏡, 是否全程鋪底)
RECIPE = [
    # ── bed 層：同一間客廳，跟 d4/d6/d8 維持聽感連續性 ──────────────
    ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
     0.0, -29, "highpass=f=90,lowpass=f=6000", True),
    ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
     0.0, -32, "lowpass=f=1300", True),

    # ── 第一幕 0.00-5.00s：慌張扭動。爪步＋土粒＋吊牌，密度最高 ──────
    ("_prerendered/d6s2_paw_a.wav",   0.30, -19, "", False),
    ("_prerendered/d6s2_crack_a.wav", 0.75, -19, "", False),
    ("_prerendered/d6s2_tag_a.wav",   1.05, -15, "", False),
    ("_prerendered/d6s2_paw_b.wav",   1.55, -18, "", False),
    ("_prerendered/d6s2_drop_a.wav",  2.10, -19, "", False),
    ("_prerendered/d6s2_tag_b.wav",   2.60, -16, "", False),
    ("_prerendered/d6s2_paw_c.wav",   3.10, -18, "", False),
    ("_prerendered/d6s2_crack_b.wav", 3.70, -18, "", False),
    ("_prerendered/d6s2_mud_a.wav",   4.15, -22, "", False),
    ("_prerendered/d6s2_tag_b.wav",   4.45, -16, "", False),

    # ── 5.00s 剪接點：一聲土響蓋住 ──
    ("_prerendered/d6s2_crack_c.wav", 4.96, -17, "", False),

    # ── 第二幕 5.00-7.50s：昂首裝清高。收安靜，一聲傲嬌鼻息 ──────
    ("_prerendered/d6s2_snort_proud.wav", 5.80, -19, "", False),
    ("_prerendered/d6s2_tag_b.wav",       6.45, -18, "", False),
    ("_prerendered/d6s2_drop_b.wav",      7.05, -22, "", False),

    # ── 7.50s 剪接點＋第三幕 7.50-9.17s：踢土走人。土花四濺＋闊步 ──
    ("_prerendered/d6s2_mud_b.wav",   7.48, -18, "", False),
    ("_prerendered/d6s2_crack_d.wav", 7.62, -17, "", False),
    ("_prerendered/d6s2_paw_d.wav",   7.85, -18, "", False),
    ("_prerendered/d6s2_tag_a.wav",   8.30, -16, "", False),
    ("_prerendered/d6s2_drop_c.wav",  8.85, -19, "", False),

    # ── 9.17s 切結尾：瞬間收乾淨。安靜＝笑點，只留 Nova 品頭論足的鼻息 ──
    ("_prerendered/d6s2_snort_judge.wav", 9.85, -16, "", False),
    ("_prerendered/d6s2_tag_c.wav",       10.80, -20, "", False),
]

if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    if mix.build(video, out, RECIPE):
        print("完成：", out)
