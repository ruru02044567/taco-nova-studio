#!/bin/sh
# 多幀接龍 vs 單張圖：換動作時擋不擋得住崩壞（單變數）
# 兩組同 prompt、同 seed、同 steps，唯一差別是起始條件餵幾格。
set -e
cd "/c/Users/TUF Gaming/Desktop/我的專案/財富密碼"
EXP="auto/_exp_20260821_接龍換動作"
PROMPT="$EXP/prompt_換動作.txt"
SEED=880821

echo "=== A 組（對照）：單張圖 = 前段最後一幀，零運動資訊 ==="
python auto/make_video_local_5s.py "$EXP/起始圖_前段末幀.jpg" "$PROMPT" "$EXP/A_單張圖.mp4" \
    --steps 8 --seed $SEED

echo "=== B 組（實驗）：接龍 = 前段末 17 格 ==="
python auto/make_video_local_5s.py - "$PROMPT" "$EXP/B_接龍17格.mp4" \
    --continue auto/clips/d12s1_s2_chain.raw704.mp4 --anchor 17 --steps 8 --seed $SEED

echo "=== 兩組都跑完 ==="
