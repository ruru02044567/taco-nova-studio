# -*- coding: utf-8 -*-
"""把音效混進無聲的 Veo 影片。

Veo 給的音軌實測只有 -47dB（等於無聲），所以整條音訊由我們自己鋪：
  bed 層（環境底噪、黑洞嗡鳴）  -30 ~ -22 dB  全程鋪底
  foley 層（爪子、布料）        -18 ~ -12 dB  在指定秒數出現
  impact 層（掉落、被吞）       -12 ~ -8  dB  重點事件
最後用 loudnorm 統一到 -14 LUFS（YouTube 播放參考電平，只降不升，做太小聲就是吃虧）。

用法：python mix.py <影片> <輸出> [配方名稱]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
LIB = HERE / "lib"

# ── 音效配方：每支影片的劇情對應哪些聲音、在第幾秒、多大聲 ──────────
RECIPES = {
    # D1 黑洞：襪子遙控器掉進洞 → 拖地毯來蓋 → 地毯也被吞 → 洞變大
    # D1 黑洞：襪子遙控器掉進洞 → 拖地毯來蓋 → 地毯也被吞 → 洞變大
    # 密度目標：10 秒約 20 個事件（第一版只有 9 個，聽起來太空）
    "blackhole": [
        # ── bed 層：只是墊底，不能搶戲。v2 太厚把動作音壓掉了，這版整體降 6dB ──
        ("roomtone/Roomtone,Hvac,Drone,Hum,Low Mids,Loop.mp3", 0.0, -37, "highpass=f=80", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -39, "lowpass=f=1400", True),                      # 隔著窗戶的鳥叫與遠處車聲
        ("drone-low/hollow_drone_001.mp3", 0.0, -28, "lowpass=f=130,highpass=f=28", True),   # 黑洞嗡鳴
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3", 0.0, -33, "lowpass=f=700,highpass=f=60", True),  # 被吸進去的氣流
        # ── 0-1s：災難已成形，兩個物件分開落地才有層次（全部提 3dB 讓它們跳出來） ──
        ("cloth-drop/Drop Soft - Single Plank, Drop 02.mp3", 0.15, -13, "lowpass=f=3500", False),   # 襪子
        ("plastic-drop/Vibration,Case,Objects,Rattle,Clatter,Rapid,Violent,Loop.mp3", 0.45, -10, "atrim=0:0.8", False),  # 遙控器
        ("rumble-sub/Low Boom 3.mp3", 0.9, -14, "lowpass=f=180", False),                    # 東西被吞下去的悶響
        # ── 2-6s：拖地毯（爪步＋抓地＋布料，三軌疊） ──
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 1.9, -11, "atempo=1.15", False),             # 真正的狗爪小跑
        ("claw-scratch/nails_on_towel_single_003.mp3", 2.3, -15, None, False),
        ("fabric-fine/Blanket-Lift_06.wav", 2.5, -9, "atempo=0.75", False),                 # 咬起地毯
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 3.1, -13, "atempo=0.8", False),
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 3.8, -12, "atempo=1.1", False),
        ("cloth-drag/ICE Skater cloth move 10.mp3", 4.4, -10, "atempo=0.85", False),        # 地毯拖過地板
        ("claw-scratch/nails_on_velvet_single_002.mp3", 5.2, -15, None, False),
        ("fabric-fine/Blanket-Lift_06.mp3", 5.6, -12, "atempo=0.9", False),
        # ── 6-7s：地毯被吞（三軌同時，這是全片最重的一下） ──
        ("whoosh/Organic_Whoosh_14.mp3", 6.25, -5, "asetrate=48000*0.6,aresample=48000,lowpass=f=900", False),
        ("fabric-fine/Blanket-Lift_06.wav", 6.4, -9, "atempo=1.6", False),                  # 布料被快速抽走
        ("rumble-sub/Low Boom 3.mp3", 6.85, -10, "lowpass=f=200", False),                   # 吞下去的低頻
        # ── 8-10s：退開、定格裝無辜 ──
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 7.9, -14, "atempo=1.2", False),
        ("claw-scratch/nails_on_towel_single_003.mp3", 8.9, -18, None, False),
    ],

    # D4 麵粉：開場已成災 → 慌張撥麵粉 → 袋子噴更多 → 坐定裝無辜（哈士奇全程在睡）
    # 這支的聲音重點跟黑洞不同：沒有低頻怪物，全部是「乾的、細的、粉狀的」。
    # 低頻只留房間底噪，任何 boom 都會讓麵粉聽起來像石頭。
    "flour": [
        # ── bed 層：安靜的午後客廳。哈士奇的鼻息當第二層底 ──
        # ⚠️ 第一版把 bed 鋪在 -38/-41，開頭兩秒整體只有 -52dB，
        # 量出來 LRA 11.0 LU（目標 ≤5）、整體 -16 LUFS（目標 -14）。
        # 而且 Shorts 開頭沒聲音很危險 —— 觀眾會以為影片壞掉直接滑走。
        # 「留白」要靠事件密度做，不是靠把底噪也關掉。bed 整體提 8dB。
        ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
         0.0, -30, "highpass=f=90,lowpass=f=6000", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -33, "lowpass=f=1300", True),
        # ── 0-2s：定格，只有眼睛動。事件少但底要在，開頭不能是死寂 ──
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.5, -19, "atempo=0.7,lowpass=f=900", False),
        ("fabric-fine/Blanket-Lift_06.mp3", 1.1, -17, "atempo=1.4,highpass=f=400", False),   # 空氣裡的粉塵
        ("dirt/Impacts Soft - Short, Crack.mp3", 1.6, -19, "atempo=1.6,highpass=f=400", False),  # 粉粒落地
        # ── 2-6s：慌張撥麵粉。爪子刮木地板＋粉末推動，兩軌交錯製造忙亂感 ──
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 2.1, -12, "atempo=1.25", False),
        ("claw-scratch/nails_on_towel_single_003.mp3", 2.5, -14, "highpass=f=300", False),
        ("dirt/Impacts Soft - Short, Crack.mp3", 2.9, -15, "atempo=1.3,highpass=f=250", False),
        ("fabric-fine/Blanket-Lift_06.wav", 3.3, -13, "atempo=0.85", False),                 # 胸口壓上粉堆
        ("claw-scratch/nails_on_ceramic_tile_single_001.mp3", 3.8, -16, "lowpass=f=5000", False),
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 4.3, -12, "atempo=0.8", False),     # 拖麵粉袋
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 4.9, -14, "atempo=1.2", False),
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 5.4, -13, "atempo=1.15", False),
        # ── 6-8s：反效果，袋子又噴一團。全片最重的一下，但要「鬆」不要「硬」 ──
        ("whoosh/Organic_Whoosh_14.mp3", 6.1, -7, "asetrate=48000*0.85,aresample=48000,highpass=f=200", False),
        ("dirt/Impacts Soft - Short, Crack.mp3", 6.35, -11, "atempo=0.9", False),            # 粉堆塌下來
        ("fabric-fine/Blanket-Lift_06.mp3", 6.6, -10, "atempo=1.8,highpass=f=500", False),   # 粉塵騰空
        ("dog-small/Dog_German Short-Haired Pointer_Bark and Whimper_Fienup_001.mp3",
         7.1, -13, "atrim=0:0.5,atempo=1.4,highpass=f=350", False),                          # 打噴嚏（截短當噴嚏用）
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 7.5, -16, "atempo=1.5", False),       # 噴嚏後落粉
        # ── 8-10s：坐定裝無辜。收乾淨，只留呼吸，讓定格更有戲 ──
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 8.2, -17, "atempo=0.9", False),
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 9.1, -22, "atempo=0.65,lowpass=f=800", False),
    ],

    # D4 麵粉「原地甩身」版（5 秒，2026-08-13 夜間 R&D seed 424243）
    # 跟 10 秒版最大的差別：全片只有一個動作，聲音必須跟著它走。
    # 狗甩身最招牌的聲音不是毛，是**項圈牌連續碰撞** —— 沒有那串 rattle，
    # 觀眾只會覺得「有東西在動」，不會認出「牠在甩身」。
    # 低頻一律不進場：任何 boom 都會讓麵粉聽起來像石頭（沿用 flour 的判斷）。
    "flour_shake": [
        # ── bed 層：安靜午後客廳。沿用 flour 的兩軌，維持與已發布影片的聽感連續性 ──
        ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
         0.0, -30, "highpass=f=90,lowpass=f=6000", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -33, "lowpass=f=1300", True),
        # ── 0-1s：站著不動，只有眼睛動。事件少，但底噪要在，開頭死寂觀眾會直接滑走 ──
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.35, -20, "atempo=0.7,lowpass=f=900", False),
        ("fabric-fine/Blanket-Lift_06.mp3", 0.75, -20, "atempo=1.5,highpass=f=450", False),
        # ── 1.0-1.5s：起手。重心移動，毛開始動 ──
        ("paws-wood/FS Wood Civilian Crouch N03.mp3", 1.05, -17, "atempo=1.1", False),
        ("fabric-fine/Blanket-Lift_06.wav", 1.30, -16, "atempo=1.2", False),
        # ── 1.5-2.5s：甩身。全片最重的一秒，三軌以上同時堆疊 ──
        ("whoosh/Organic_Whoosh_14.mp3", 1.50, -8, "asetrate=48000*1.1,aresample=48000,highpass=f=250", False),
        ("plastic-drop/Vibration,Case,Objects,Rattle,Clatter,Rapid,Violent,Loop.mp3",
         1.55, -7, "atrim=0:0.9,highpass=f=600", False),          # ★ 項圈銀牌連續碰撞，甩身的招牌
        ("fabric-fine/Blanket-Lift_06.mp3", 1.62, -8, "atempo=2.2,highpass=f=350", False),
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 1.80, -10, "atempo=1.9", False),
        ("fabric-fine/Blanket-Lift_06.wav", 1.98, -9, "atempo=2.4,highpass=f=400", False),
        ("whoosh/Whoosh_Rod_Pole_022.mp3", 2.10, -11, "atempo=1.3,highpass=f=300", False),   # 反向甩回來
        ("plastic-drop/Vibration,Case,Objects,Rattle,Clatter,Rapid,Violent,Loop.mp3",
         2.22, -10, "atrim=0:0.5,highpass=f=650", False),          # 項圈第二波，衰減
        ("cloth-drag/ICE Skater cloth move 10.mp3", 2.35, -12, "atempo=1.7", False),
        # ── 2.5-3.5s：粉塵撲落、站穩。這裡是「乾的、細的」，不能有硬撞擊 ──
        ("dirt/Impacts Soft - Short, Crack.mp3", 2.55, -11, "atempo=0.95,highpass=f=200", False),
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 2.80, -14, "atempo=1.3,highpass=f=300", False),
        ("fabric-fine/Blanket-Lift_06.mp3", 3.05, -15, "atempo=1.6,highpass=f=500", False),
        ("paws-wood/FS Wood Civilian Crouch N05.mp3", 3.30, -16, "atempo=1.05", False),
        ("dirt/Impacts Soft - Short, Crack.mp3", 3.45, -18, "atempo=1.5,highpass=f=400", False),
        # ── 3.5-5s：站定看鏡頭。收乾淨，只留餘粉與呼吸，讓定格有戲 ──
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 3.85, -20, "atempo=1.6,highpass=f=450", False),
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 4.20, -21, "atempo=0.7,lowpass=f=850", False),
        ("fabric-fine/Blanket-Lift_06.mp3", 4.60, -23, "atempo=1.3,highpass=f=500", False),
    ],

    # D5 岩漿：地板變熔岩 → Taco 拖抱枕當踏腳石丟下去 → 坐定裝無辜（Nova 在沙發上抬頭看他一眼）
    # 這支的底層跟前兩支都不同：整個房間有一片會發聲的熔岩，所以 bed 要厚、要一直在。
    # lib/lava/ 是 8/11 為這支補下載的，主力是夏威夷基拉韋厄火山的實地錄音（不是合成音）。
    #
    # ⚠️ 時間軸對應的是「慢速開頭版」的定剪：前 0.7 秒放慢成約 1.8 秒當鋪陳拍，
    # 所以 0~1.8 秒只有熔岩自己的聲音，狗的動作音從 1.9 秒才進來。
    "lava": [
        # ── bed 層：客廳底噪 ＋ 熔岩三件套。這支不怕底厚，怕的是聽起來不像「地板在燒」 ──
        # ⚠️ 第一版 bed 鋪在 -25~-33，量出來 LRA 19.3 LU（目標 ≤5）：
        # 前半靠密集動作音撐到 -11 dB，後半事件一少就掉到 -30 dB —— 收尾像聲音斷了。
        # 但畫面上熔岩是**整片一直在燒**的，聲音沒有理由消失。bed 整體提 6dB。
        # （flour 配方踩過同一個坑，原因不同：那支是開頭太安靜，這支是結尾太安靜。）
        # ⚠️⚠️ 這三軌一定要掛 dynaudnorm，理由是量出來才發現的（2026-08-11）：
        # `Lava Lava Gets Close.mp3` 是夏威夷火山的**實地錄音**，素材本身逐秒起伏 20 dB
        # （前 10 秒在 -28 ~ -47 之間跳），而我們只用它的前 10 秒 ——
        # 剛好吃到最不穩的那一段，於是整支片的結尾憑空掉了 20 dB，LRA 衝到 18.4 LU。
        # 對照組：那支 5.1 萬爆款全片落差只有 3.4 dB。
        # **實地錄音當 bed 用之前，先假設它不平，掛 dynaudnorm 把它壓成一條線。**
        # 合成音（roomtone、drone）沒這個問題，不用掛。
        ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
         0.0, -33, "highpass=f=90,lowpass=f=6000", True),
        # bed 音量比前兩支配方厚得多，是因為這支畫面上有**一整片一直在燒的熔岩**，
        # 它本來就該是持續的聲音地板。事件音在 -10~-14，比 bed 高 8~12 dB，不會被蓋掉。
        ("lava/Metal_Souls_Ambient_Drone_Volcanic_Eruption.mp3",
         0.0, -19, "dynaudnorm=f=200:g=15,lowpass=f=220", True),              # 地底低頻，讓畫面有重量
        ("lava/Lava Lava Gets Close.mp3", 0.0, -16,
         "dynaudnorm=f=200:g=15,lowpass=f=5000", True),                       # 熔岩流動主體
        ("lava/FireCracklingInAWoodstove.mp3", 0.0, -22,
         "dynaudnorm=f=200:g=15,highpass=f=500", True),                       # 表面細碎劈啪
        # ── 0-1.8s：鋪陳拍。畫面放慢了，但**聲音不能跟著變小** ──
        #
        # ⚠️ 這是量出來才知道的（2026-08-11）：那支 5.1 萬爆款的 LRA 只有 **1.4 LU**，
        # 也就是它的聲音幾乎是全平的 —— 儘管它的畫面動量對比高達 35 倍。
        # 第一版我讓聲音跟著畫面一起安靜，LRA 衝到 19.3，等於前段在手機上根本聽不到。
        # **畫面的節奏和聲音的節奏要分開想：畫面可以留白，響度不行。**
        # 所以這段改成用熔岩自己的聲音鋪滿，音量跟中段動作音同級。
        ("lava/Elemental - Water Bubbles Big_4.mp3", 0.15, -12, "atempo=0.75,lowpass=f=2500", False),
        ("lava/Lava Lava Short Windy Crackles.mp3", 0.5, -13, "highpass=f=280", False),
        ("lava/sci-fi metal boiling metal spill 05.mp3", 0.95, -12, "atempo=0.8", False),
        ("lava/Elemental - Water Bubbles Big_4.mp3", 1.35, -13, "atempo=0.9,lowpass=f=2000", False),
        ("lava/Lava Lava Short Windy 10.mp3", 1.6, -14, "highpass=f=200", False),
        # ── 1.9-5.8s：拖抱枕。爪子在地毯上（不是木地板）＋布料重量，兩軌交錯 ──
        ("paws-carpet/1806 - Footsteps - Sneakers on Carpet - 90 fpm - Loop.mp3",
         1.9, -14, "atempo=1.3,highpass=f=200", False),
        ("claw-scratch/nails_on_towel_single_003.mp3", 2.3, -15, None, False),
        ("fabric-fine/Blanket-Lift_06.mp3", 2.5, -10, "atempo=0.7", False),   # 咬起抱枕
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 3.0, -12, "atempo=0.75", False),
        ("lava/Elemental - Water Bubbles Big_4.mp3", 3.4, -17, "atempo=1.1", False),
        ("paws-carpet/1806 - Footsteps - Sneakers on Carpet - 90 fpm - Loop.mp3",
         3.7, -14, "atempo=1.2,highpass=f=200", False),
        ("cloth-drag/ICE Skater cloth move 10.mp3", 4.2, -11, "atempo=0.8", False),  # 抱枕拖過地毯
        ("claw-scratch/nails_on_velvet_single_002.mp3", 4.7, -14, None, False),
        ("fabric-fine/Blanket-Lift_06.wav", 5.2, -11, "atempo=0.85", False),
        # ── 5.9-6.6s：抱枕碰到熔岩。全片最重的一下，三軌同時 ──
        ("whoosh/Organic_Whoosh_14.mp3", 5.9, -7, "asetrate=48000*0.8,aresample=48000,lowpass=f=1200", False),
        ("liquid/mud_splat_heavy_03.mp3", 6.15, -9, "atempo=0.85,lowpass=f=1800", False),   # 落進熔岩的悶噗
        ("lava/sci-fi metal boiling metal spill 05.mp3", 6.3, -8, "atempo=0.9", False),     # 燒起來的滋滋
        ("lava/Lava Lava Short Windy Crackles.mp3", 6.5, -12, "highpass=f=300", False),     # 火舌竄起
        # ── 6.9s 之後：坐定裝無辜、Nova 抬頭。收乾淨，只留熔岩自己在冒泡 ──
        ("paws-carpet/1806 - Footsteps - Sneakers on Carpet - 90 fpm - Loop.mp3",
         7.0, -16, "atempo=0.95,highpass=f=200", False),
        # 收尾畫面安靜，但熔岩還在燒，聲音要撐住到最後一格。
        # ⚠️ 試過在這裡疊一軌 20.7 秒的長素材想把後段填滿，**結果反而更糟**
        # （落差 15.4 → 17.4 dB，第 9 秒從 -18 掉到 -28）。原因沒查到底，
        # 但方向很明確：後段不要再加東西了，這個配方到此為止。
        # 現況 LRA 11.3 LU，跟 d4s1 最終版（10.4）同級，前 6 秒都在 -11~-16 很扎實。
        ("lava/Elemental - Water Bubbles Big_4.mp3", 7.4, -13, "atempo=0.85,lowpass=f=2400", False),
        ("fabric-fine/Blanket-Lift_06.mp3", 8.0, -15, "atempo=0.6", False),   # Nova 抬頭，沙發布料
        ("lava/sci-fi metal boiling metal spill 05.mp3", 8.4, -13, "atempo=0.75", False),
        ("lava/Elemental - Water Bubbles Big_4.mp3", 8.8, -14, "atempo=0.8,lowpass=f=2200", False),
        ("lava/Lava Lava Short Windy Crackles.mp3", 9.2, -13, "highpass=f=350", False),
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 9.5, -18, "atempo=0.7,lowpass=f=900", False),
    ],

    # D6 盆栽土「原地甩身」版（5 秒，2026-08-14）
    #
    # ⚠️ 這個配方存在的理由：賢賢看 v06 時說「聲音怪怪的」。
    # 當時直接套 flour_shake，錯在兩件事：
    #   ① 時間軸是為麵粉片的動作設計的，事件點對不上這支
    #   ② flour_shake 整組是「乾粉」音色（高頻 fabric 粉塵、禁用低頻），
    #      但這支地上是**濕的盆栽土**——濕土有重量，落地是「啪」不是「沙」。
    #
    # 所以跟 flour_shake 三個結構性差異：
    #   ① 拿掉所有 fabric-fine 高頻粉塵騰空音（那是乾粉專屬的語彙）
    #   ② 加入 mud_splat（濕泥拍擊）與 dirt impacts（土塊落地），並允許少量低頻
    #      —— flour 配方刻意禁低頻是怕麵粉聽起來像石頭，濕土沒這個顧慮，土本來就有重量
    #   ③ 項圈改用 ceramic 的銀飾 shake（金屬牌互擊），比 plastic-drop 的塑膠 rattle 準
    "soil_shake": [
        # ── bed 層：同一間客廳。沿用前幾支的兩軌，維持頻道的聽感連續性 ──
        ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
         0.0, -30, "highpass=f=90,lowpass=f=6000", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -33, "lowpass=f=1300", True),
        # ── 0-1.0s：站定，只有眼睛動。事件少但底要在，開頭死寂觀眾直接滑走 ──
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.30, -20, "atempo=0.7,lowpass=f=900", False),
        ("dirt/Impacts Soft - Short, Crack.mp3", 0.70, -21, "atempo=0.8,lowpass=f=3000", False),   # 土堆自己塌一小塊
        # ── 1.0-1.5s：起手，重心壓低 ──
        ("paws-wood/FS Wood Civilian Crouch N03.mp3", 1.05, -17, "atempo=1.1", False),
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 1.30, -18, "atempo=0.9,lowpass=f=2600", False),
        # ── 1.5-2.6s：甩身。全片最重的一段，四軌堆疊 ──
        ("whoosh/Organic_Whoosh_14.mp3", 1.50, -9, "asetrate=48000*0.95,aresample=48000,highpass=f=180", False),
        ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
         1.55, -7, "atrim=0:1.0,highpass=f=500", False),                                          # ★ 項圈銀牌互擊＝甩身的招牌
        ("liquid/mud_splat_heavy_03.mp3", 1.70, -10, "atempo=1.3,lowpass=f=4000", False),          # ★ 濕土甩離身體
        ("dirt/Impacts Hard - Short Wobbly Tail 01.mp3", 1.88, -12, "atempo=1.2,lowpass=f=3500", False),  # 土塊砸地
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 2.02, -13, "atempo=1.8", False),          # 鬆皮甩動
        ("whoosh/Whoosh_Rod_Pole_022.mp3", 2.18, -12, "atempo=1.3,highpass=f=250", False),         # 反向甩回來
        ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
         2.30, -11, "atrim=0:0.6,highpass=f=550", False),                                          # 項圈第二波，衰減
        ("dirt/Impacts Soft - Short, Crack.mp3", 2.45, -14, "atempo=1.1,lowpass=f=3200", False),
        # ── 2.6-3.6s：土落定，零星散落 ──
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 2.72, -15, "atempo=1.15,lowpass=f=2800", False),
        ("liquid/mud_splat_heavy_03.mp3", 2.95, -16, "atempo=1.6,lowpass=f=3600", False),
        ("dirt/Impacts Soft - Short, Crack.mp3", 3.25, -18, "atempo=1.4,highpass=f=200", False),
        ("paws-wood/FS Wood Civilian Crouch N05.mp3", 3.50, -18, "atempo=0.95", False),             # 站定，重心回正
        # ── 3.6-5.0s：抬頭裝無辜。收乾淨，只留呼吸讓定格有戲 ──
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 3.95, -20, "atempo=1.3,lowpass=f=2400", False),
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 4.45, -21, "atempo=0.65,lowpass=f=800", False),
    ],

    # D6 盆栽土「站定裝無辜」版（5 秒，2026-08-14）
    #
    # 為什麼要有這個配方：v09 的畫面實測**沒有甩身動作**（密集幀 1.2-3.0 秒逐格看過，
    # 狗全程站著只有轉頭，土屑沒飛起）。這種時候硬套 soil_shake 就是拿甩身音效
    # 配靜止畫面 —— 那才是真正的「聲音跟畫面不同步」，比沒配音更糟。
    #
    # 這版的設計是「安靜的犯罪現場」：事件密度低但絕不死寂。
    # 響度仍然要平（LRA 越低越好）—— 畫面可以留白，響度不行，
    # 開頭沒聲音觀眾會以為影片壞掉直接滑走。
    #
    # ⚠️ 時間點是對齊 **d6s1-v09-slowstart.mp4（5.83 秒）**，不是原始的 5.04 秒素材。
    # 那支的開頭 0.8 秒被放慢成 1.6 秒（動量對比 2.7→3.1 倍），
    # 所以原片 t<0.8 的事件要 ×2，t≥0.8 的事件要 +0.8。直接套原始素材會整組對不上。
    #
    # 畫面事件對照（密集幀逐格看出來的）：
    #   0.0-1.6s 站定不動，只有頭微偏   → 只有底噪＋Nova 鼻息＋土堆自己塌
    #   2.0-3.8s 轉頭看向鏡頭            → 爪子壓土、項圈銀牌叮噹
    #   2.75s    動量峰值                → 土粒滾落壓在這裡
    #   3.8-5.8s 定住看鏡頭、鏡頭緩推近  → 收乾淨，只留零星土粒與呼吸
    "soil_still": [
        # ── bed 層：同一間客廳，跟前幾支維持聽感連續性。整體比 shake 版提 1dB 補事件稀疏 ──
        ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
         0.0, -29, "highpass=f=90,lowpass=f=6000", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -32, "lowpass=f=1300", True),
        # ── 0-1.6s（慢動作段）：定格。Nova 的鼻息是唯一的生命跡象，土堆自己塌一小塊 ──
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.60, -19, "atempo=0.7,lowpass=f=900", False),
        ("dirt/Impacts Soft - Short, Crack.mp3", 1.65, -20, "atempo=0.85,lowpass=f=2800", False),
        # ── 2.0-3.0s：重心微移、轉頭。爪子壓在濕土上是畫面唯一真的在動的東西 ──
        ("paws-carpet/1806 - Footsteps - Sneakers on Carpet - 90 fpm - Loop.mp3",
         2.05, -20, "atrim=0:0.5,atempo=0.8,lowpass=f=3000", False),                                # 爪子壓進土裡
        ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
         2.35, -14, "atrim=0:0.35,highpass=f=600", False),                                          # 項圈銀牌單聲，很輕
        # ── 2.75s：動量峰值，土粒滾落壓在這裡 ──
        ("dirt/Impacts Soft - Short, Crack.mp3", 2.75, -18, "atempo=1.2,lowpass=f=3200", False),
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 3.15, -20, "atempo=1.25,lowpass=f=2400", False),
        ("liquid/mud_splat_heavy_03.mp3", 3.60, -22, "atempo=1.8,lowpass=f=3000", False),           # 濕土黏著感，很小聲
        # ── 3.9-5.8s：定住看鏡頭、鏡頭緩推近。收乾淨，只留零星土粒與呼吸 ──
        ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
         3.90, -16, "atrim=0:0.3,highpass=f=650", False),                                           # 抬頭定住時吊牌晃一下
        ("dirt/Impacts Soft - Short, Crack.mp3", 4.35, -21, "atempo=1.4,highpass=f=250", False),
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 4.80, -19, "atempo=0.65,lowpass=f=800", False),
        ("dirt/Drop Soft - Single Plank, Drop 02.mp3", 5.20, -23, "atempo=1.3,lowpass=f=2200", False),
    ],

    # D7 傳送門吞拖鞋（5 秒，2026-08-14）
    #
    # 直接改編自 blackhole 配方 —— 那支是 5.1 萬觀看的爆款，題材同構（洞吞東西），
    # 素材語彙（低頻嗡鳴＋氣流吸力＋吞下去的悶響）可以整組沿用，不需要重新摸索。
    #
    # 跟 blackhole 的三個差異：
    #   ① 片長 5 秒不是 10 秒，事件要壓縮，密度反而更高
    #   ② 這支的主角全程站著不動，沒有拖地毯那段 foley，爪步音只在片尾轉頭時一下
    #   ③ 傳送門是「發光的」，所以嗡鳴帶一點高頻脈動感（highpass 拉高一點），
    #      不像黑洞那樣純粹是低頻黑幕
    #
    # 畫面事件對照（依 prompt 設計，實際時間點在影片生出來後用密集幀複核）：
    #   0.0-1.0s 漩渦慢轉、鞋卡著        → bed 嗡鳴＋氣流，Nova 鼻息
    #   1.0-3.0s 漩渦加速、鞋逐漸下沉     → whoosh 漸強＋布料摩擦下沉
    #   3.0-3.5s 鞋完全沒入              → ★ 全片最重的一下：低頻 boom
    #   3.5-5.0s 空轉的傳送門、狗轉頭看鏡頭 → 氣流回吸、項圈叮噹、收在呼吸上
    "portal": [
        # ── bed 層：客廳底噪 ＋ 傳送門的持續嗡鳴 ＋ 被吸進去的氣流 ──
        ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
         0.0, -31, "highpass=f=90,lowpass=f=6000", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -34, "lowpass=f=1300", True),
        ("drone-low/hollow_drone_001.mp3", 0.0, -26, "lowpass=f=220,highpass=f=45", True),          # ★ 傳送門嗡鳴，比黑洞高一點
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3",
         0.0, -32, "lowpass=f=900,highpass=f=70", True),                                            # ★ 持續的吸力氣流
        # ── 0-1.0s：漩渦慢轉，鞋卡著。Nova 的鼻息是唯一的生命跡象 ──
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.35, -20, "atempo=0.7,lowpass=f=900", False),
        # ── 1.0-3.0s：漩渦加速，鞋一路下沉。兩波 whoosh 交錯布料摩擦，堆出「正在被吃掉」 ──
        ("whoosh/Organic_Whoosh_14.mp3", 1.15, -13, "asetrate=48000*0.75,aresample=48000,lowpass=f=1100", False),
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 1.45, -14, "atempo=0.7", False),           # 拖鞋布料磨過門緣
        ("fabric-fine/Blanket-Lift_06.wav", 1.90, -13, "atempo=0.65", False),
        ("whoosh/Whoosh_Rod_Pole_022.mp3", 2.25, -11, "atempo=0.85,lowpass=f=1400", False),
        ("cloth-drag/ICE Skater cloth move 10.mp3", 2.55, -12, "atempo=0.75", False),               # 鞋跟最後刮一下
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3",
         2.75, -14, "atrim=0:0.8,lowpass=f=1200", False),                                           # 吸力加強
        # ── 3.0-3.5s：完全沒入。全片最重的一下，低頻 boom ──
        ("whoosh/Organic_Whoosh_14.mp3", 3.05, -7, "asetrate=48000*0.6,aresample=48000,lowpass=f=900", False),
        ("rumble-sub/Low Boom 3.mp3", 3.20, -9, "lowpass=f=190", False),                            # ★ 吞下去的悶響
        ("fabric-fine/Blanket-Lift_06.mp3", 3.30, -12, "atempo=1.7,highpass=f=300", False),         # 布料被抽走的尾巴
        # ── 3.5-5.0s：空轉的門，狗轉頭。氣流回吸後收乾淨 ──
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3",
         3.70, -17, "atrim=0:0.9,lowpass=f=800,areverse", False),                                   # 回吸（倒放氣流）
        ("ceramic/Apparel,bracelet,silver,ceramic,glass,leather,shake,single,bright,alternate.M.wav",
         4.15, -15, "atrim=0:0.3,highpass=f=620", False),                                           # 轉頭時項圈吊牌
        ("paws-wood/FS Wood Civilian Crouch N05.mp3", 4.30, -19, "atempo=1.0", False),              # 重心微調
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 4.65, -20, "atempo=0.65,lowpass=f=800", False),
    ],

    # D7 傳送門「迴力鏢版」（9.375 秒，2026-08-14）
    #
    # 影片結構：首幀凍 0.4s → 正播到 4.5s（鏡頭緩慢推近）→ 反播回首幀（鏡頭緩慢拉遠）。
    # 反播是為了解掉 loop 硬跳（末幀對首幀差 33.97、9.7 倍基準 → 迴力鏢後 0.66、0.2 倍）。
    #
    # ★ 這個結構給了一個很自然的聲音設計：**讓聲音跟著鏡頭距離走。**
    #   推近 → 傳送門能量漸強；4.9s 中點（離門最近）→ 最強；拉遠 → 漸弱。
    #   聲音的弧線和鏡頭的弧線是同一條，觀眾不會意識到，但會覺得「對」。
    #
    # 跟 5 秒版 portal 配方的差異：沒有「拖鞋被吞」那一下低頻 boom ——
    # 這支拖鞋全程卡在洞裡沒有沉下去，硬配 boom 就是拿音效演畫面沒有的事。
    "portal_boomerang": [
        # ── bed 層：客廳底噪 ＋ 傳送門嗡鳴 ＋ 持續的吸力氣流 ──
        ("roomtone/Hvac,Cooling unit,Refrigerator,Int,Drone,Rattle,Roomtone,Loop.mp3",
         0.0, -31, "highpass=f=90,lowpass=f=6000", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -34, "lowpass=f=1300", True),
        ("drone-low/hollow_drone_001.mp3", 0.0, -27, "lowpass=f=220,highpass=f=45,dynaudnorm=f=250:g=7", True),
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3",
         0.0, -32, "lowpass=f=900,highpass=f=70,dynaudnorm=f=250:g=7", True),
        # ── 0-1.2s：凍結＋起步。Nova 的鼻息是唯一的生命跡象 ──
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 0.50, -20, "atempo=0.7,lowpass=f=900", False),
        # ── 1.2-4.9s：鏡頭推近，能量一路漸強（-17 → -10）──
        ("whoosh/Organic_Whoosh_14.mp3", 1.25, -17, "asetrate=48000*0.55,aresample=48000,lowpass=f=950", False),
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 2.05, -19, "atempo=0.6", False),      # 拖鞋布料被門緣拉扯
        ("whoosh/Whoosh_Rod_Pole_022.mp3", 2.85, -15, "atempo=0.6,lowpass=f=1200", False),
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3",
         3.60, -14, "atrim=0:1.0,lowpass=f=1100", False),
        ("whoosh/Organic_Whoosh_14.mp3", 4.40, -12, "asetrate=48000*0.7,aresample=48000,lowpass=f=1000", False),
        # ── 4.9s：中點，鏡頭離傳送門最近。全片能量最高的一下（低頻湧動，不是撞擊）──
        ("rumble-sub/Low Boom 3.mp3", 4.85, -11, "lowpass=f=200", False),
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3",
         4.95, -12, "atrim=0:1.2,lowpass=f=1300", False),
        # ── 4.9-9.4s：鏡頭拉遠，能量一路漸弱（-13 → -20），與推近段對稱 ──
        ("whoosh/Whoosh_Rod_Pole_022.mp3", 5.70, -15, "atempo=0.6,lowpass=f=1150,areverse", False),
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 6.50, -19, "atempo=0.6", False),
        ("whoosh/Organic_Whoosh_14.mp3", 7.20, -17, "asetrate=48000*0.55,aresample=48000,lowpass=f=950,areverse", False),
        ("dog-sleep/G4F SFX06 - HORSES - Snort 03.mp3", 8.05, -17, "atempo=0.7,lowpass=f=900", False),
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3",
         8.55, -14, "atrim=0:1.0,lowpass=f=900,areverse", False),
        # 結尾補一顆低頻脈動：loop 會把 9.3s 接回 0.0s，兩端響度必須對得上，
        # 否則每次循環都會突然變大聲（實測原本結尾比開頭低 18dB）
        ("drone-low/hollow_drone_001.mp3", 8.95, -16, "atrim=0:0.45,lowpass=f=260,highpass=f=50", False),
    ],
}


def build(video, out, recipe, target_lufs=-14.0):
    """target_lufs=None 時跳過響度正規化（只留防爆表 limiter）。

    2026-08-18 加：賢賢聽出四支片「聲音超奇怪」，逐秒量 9 分標準片
    （Chihuahua Pushes Remote）發現它整體遠比 -14 LUFS 安靜——
    靜音開場、全片只有 2-3 個真實事件、動態範圍極大。
    「一律拉到 -14」會把安靜文法整個毀掉，所以改成配方可選。
    舊配方不帶參數＝行為不變。
    """
    out = Path(out)          # 命令列傳進來是字串，下面 with_suffix 需要 Path
    dur = float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video],
        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip())

    inputs, filters, labels = ["-i", str(video)], [], []
    for i, (rel, start, gain, extra, loop) in enumerate(recipe):
        src = LIB / rel
        if not src.exists():
            print(f"  ! 缺檔跳過：{rel}")
            continue
        # ── 硬閘門（2026-08-19）：ffmpeg 7.1.1 的 atempo 輸出 NOPTS 幀，
        # 會讓後面的 adelay 被 atrim 抵銷＝整個事件音靜默消失、全堆回 0 秒。
        # 8/18 賢賢聽出的「四支片聲音超奇怪」根因就是它。
        # extra 裡禁用 atempo 與非零起點 atrim；變速／裁段素材先渲染進
        # lib\_prerendered\ 再引用。寧可炸在這裡，不准靜默壞在成品裡。
        if extra and ("atempo" in extra or re.search(r"atrim=(?!0[:,])", extra)):
            print(f"  ✗ 配方錯誤（{rel}）：extra 含 atempo／非零起點 atrim，"
                  f"adelay 會失效（NOPTS 地雷）。請預渲染進 _prerendered\\ 再引用。")
            return False
        if loop:
            inputs += ["-stream_loop", "-1", "-i", str(src)]
        else:
            inputs += ["-i", str(src)]
        idx = len(labels) + 1
        chain = f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
        if extra:
            chain += f",{extra}"
        chain += f",volume={gain}dB"
        if start > 0:
            ms = int(start * 1000)
            chain += f",adelay={ms}|{ms}"
        chain += f",atrim=0:{dur:.3f},afade=t=in:st=0:d=0.02"
        chain += f"[a{idx}]"
        filters.append(chain)
        labels.append(f"[a{idx}]")

    mix = "".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0[mixed]"
    base_fc = ";".join(filters) + ";" + mix

    def run(post, dst):
        cmd = ["ffmpeg", "-v", "error", "-y", *inputs,
               "-filter_complex", base_fc + ";" + post,
               "-map", "0:v", "-map", "[aout]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "384k", "-ar", "48000",
               "-movflags", "+faststart", "-shortest", str(dst)]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            print("ffmpeg 失敗：", (p.stderr or "")[-900:])
            return False
        return True

    # 第一階段：先量測混完之後的整體響度。
    # 不能直接用 loudnorm 一次到位 —— 它預設是動態模式，會邊走邊壓縮，
    # 把落地聲、被吞那一下的尖峰全部壓平，聽起來就變成「一直有聲音但沒有重點」。
    probe = out.with_suffix(".probe.mp4")
    if not run("[mixed]anull[aout]", probe):
        return False
    meas = subprocess.run(["ffmpeg", "-i", str(probe), "-af", "ebur128=framelog=quiet",
                           "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    lufs = None
    for ln in meas.splitlines():
        if "I:" in ln and "LUFS" in ln:
            try:
                lufs = float(ln.split("I:")[1].split("LUFS")[0].strip())
            except Exception:
                pass
    probe.unlink(missing_ok=True)
    if target_lufs is None:
        if lufs is not None:
            print(f"混音後 {lufs:.1f} LUFS → 不正規化（安靜文法），只掛防爆表 limiter")
        return run("[mixed]alimiter=limit=-1.5dB:level=disabled[aout]", out)
    if lufs is None:
        print("量不到響度，退回 loudnorm")
        return run(f"[mixed]loudnorm=I={target_lufs}:TP=-1.5:LRA=11[aout]", out)

    gain = target_lufs - lufs
    print(f"混音後 {lufs:.1f} LUFS → 套用固定增益 {gain:+.1f} dB（動態完整保留）")
    # 第二階段：純線性增益 + 只在真的爆表時才動作的 limiter
    return run(f"[mixed]volume={gain:.2f}dB,alimiter=limit=-1.5dB:level=disabled[aout]", out)


if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "blackhole"
    if build(video, out, RECIPES[name]):
        chk = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-i", out, "-af",
             "astats=metadata=1:reset=48000,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
             "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        levels = [l.split("=")[1] for l in chk.stdout.splitlines() if "RMS_level" in l]
        print(f"完成：{out}")
        print("每秒音量(dB)：", " ".join(f"{float(x):.0f}" for x in levels if x != "-inf"))
