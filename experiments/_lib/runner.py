# -*- coding: utf-8 -*-
r"""runner.py — 實驗跑批器（2026-08-21 建立）

負責「跑一組、記一組」的機械部分，好讓各實驗的 run.py 只寫**變數表**。

### 三個不可妥協的設計

1. **只呼叫正式腳本，不複製它的邏輯。**
   生片一律 `subprocess` 叫 `auto\make_video_local_5s.py`，一行都不改它。
   複製一份改成「實驗版」是最常見的自欺：實驗過了、產線沒過，
   查半天才發現兩邊的 workflow 早就不一樣了。

2. **每一組把完整設定寫成 JSON 落地。**
   8/14 那輪實驗之所以結論可信，是因為每組都有 .log；8/9 那輪之所以
   結論下錯（「本機不能接龍」），是因為當時沒有留下可回溯的設定。

3. **可重跑、可跳過。**
   輸出檔存在就跳過（除非 --force）。一支 6.3 分鐘，掃 5 組要半小時，
   中途斷了不該從頭再燒一次算力。
"""
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parents[2]
AUTO = PROJECT / "auto"
MAKE = AUTO / "make_video_local_5s.py"
SYS_PY = Path(r"C:\Users\TUF Gaming\AppData\Local\Programs\Python\Python313\python.exe")
PY = str(SYS_PY if SYS_PY.exists() else sys.executable)


class GpuWatch:
    """生成期間背景輪詢 nvidia-smi，記 VRAM 峰值。

    為什麼要量：RTX 5050 只有 8 GB，接龍餵越多格 → VAE encode 的張量越大。
    「anchor 25 會不會 OOM」是這輪實驗必須回答的成本問題，不能等出事才知道。
    """

    def __init__(self, interval=5.0):
        self.interval, self.peak, self._stop = interval, 0, threading.Event()
        self._t = None

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=10).stdout.strip()
                self.peak = max(self.peak, int(out.splitlines()[0]))
            except Exception:
                pass                      # 量不到就算了，不能因為監控失敗害實驗中斷

    def __enter__(self):
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def gen(out_mp4, prompt_file, scene=None, prev=None, anchor=None,
        seed=None, steps=8, shift=None, length=None, sampler=None,
        extra=None, timeout=2400, force=False):
    """跑一組生成。回 dict（時間、VRAM 峰值、stdout、指令）。

    scene / prev 二選一：scene = 單張場景圖起頭；prev = 多幀接龍。
    make_video_local_5s.py 的位置參數是 (起始圖, prompt, 輸出)，
    接龍模式起始圖給 `-`（那支腳本自己的約定，不是我發明的）。
    """
    out_mp4 = Path(out_mp4)
    meta_json = out_mp4.with_suffix(".json")
    if out_mp4.exists() and meta_json.exists() and not force:
        log(f"  跳過（已存在）：{out_mp4.name}")
        return json.loads(meta_json.read_text(encoding="utf-8"))

    cmd = [PY, str(MAKE), str(scene) if scene else "-", str(prompt_file), str(out_mp4)]
    if prev:
        cmd += ["--continue", str(prev)]
    if anchor is not None:
        cmd += ["--anchor", str(anchor)]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    if steps is not None:
        cmd += ["--steps", str(steps)]
    if shift is not None:
        cmd += ["--shift", str(shift)]
    if length is not None:
        cmd += ["--length", str(length)]
    if sampler is not None:
        cmd += ["--sampler", sampler]
    cmd += list(extra or [])

    log(f"  ▶ {out_mp4.name}")
    log(f"    {' '.join(cmd[2:])}")
    t0 = time.time()
    with GpuWatch() as w:
        for attempt in range(6):
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace", cwd=str(PROJECT))
            # 退出碼 9 ＝ studio_lock 說「產線被別人佔用，讓路」，那不是失敗。
            # 排程器每 20 分鐘會叫一次 pipeline tick，剛好撞上就會拿到 9 ——
            # 如果照失敗記錄，實驗會平白少一組，而且原因看起來像是模型崩了。
            if p.returncode != 9:
                break
            log(f"    ⏸ 產線被佔用（第 {attempt + 1} 次），3 分鐘後重試")
            time.sleep(180)
    dt = time.time() - t0
    meta = {
        "out": str(out_mp4),
        "cmd": cmd,
        "returncode": p.returncode,
        "ok": p.returncode == 0 and out_mp4.exists(),
        "minutes": round(dt / 60, 2),
        "vram_peak_mb": w.peak,
        "when": datetime.now().isoformat(timespec="seconds"),
        "params": {"scene": str(scene) if scene else None, "prev": str(prev) if prev else None,
                   "anchor": anchor, "seed": seed, "steps": steps, "shift": shift,
                   "length": length, "sampler": sampler,
                   "prompt_file": str(prompt_file),
                   "prompt_chars": len(Path(prompt_file).read_text(encoding="utf-8").strip())},
        "stdout": (p.stdout or "")[-4000:],
        "stderr": (p.stderr or "")[-2000:],
    }
    meta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"    {'✅' if meta['ok'] else '❌'} {meta['minutes']} 分鐘 / VRAM 峰值 {w.peak} MB")
    if not meta["ok"]:
        log(f"    stdout 末段：{(p.stdout or '')[-500:]}")
    return meta
