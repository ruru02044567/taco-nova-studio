#!/bin/bash
# 一次跑完整條 LoRA 產線。每個階段的輸出都寫進 run_all.log。
cd "$(dirname "$0")"
PY="/c/Users/TUF Gaming/ai-video-local/venv/Scripts/python.exe"
export PYTHONPATH="C:/Users/TUF Gaming/Desktop/我的專案/財富密碼/LOCAL-AI-STUDIO/_trainlib"
export PYTHONIOENCODING=utf-8
LOG=run_all.log
: > "$LOG"

stage () {
  echo ""                                    | tee -a "$LOG"
  echo "═══════════════════════════════════" | tee -a "$LOG"
  echo "▶ $1   $(date '+%H:%M:%S')"          | tee -a "$LOG"
  echo "═══════════════════════════════════" | tee -a "$LOG"
  shift
  "$@" 2>&1 | grep -vE "Fetching |UserWarning|warnings.warn|it/s\]$|^\s*$|should be kept in float32|HF_TOKEN|symlink|Developer Mode|local_dir_use_symlinks" | tee -a "$LOG"
}

stage "1/5  Nova LoRA 訓練（1000 步）"   "$PY" 02_train_lora.py --who nova
stage "2/5  Taco 預算快取"               "$PY" 01_precompute.py --who taco
stage "3/5  Taco LoRA 訓練（1000 步）"   "$PY" 02_train_lora.py --who taco
stage "4/5  Nova 測試生成"               "$PY" 03_test_lora.py --who nova
stage "5/5  Taco 測試生成"               "$PY" 03_test_lora.py --who taco

echo ""                              | tee -a "$LOG"
echo "🏁 全部完成 $(date '+%H:%M:%S')" | tee -a "$LOG"
