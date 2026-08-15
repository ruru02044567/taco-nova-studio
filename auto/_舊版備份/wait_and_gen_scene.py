# -*- coding: utf-8 -*-
"""守候遙控瀏覽器，鎖一釋放就立刻生場景圖。

為什麼要這支：隔壁卡通農場視窗會長時間佔用同一個 Edge（run_ab、diag 之類），
手動重試很浪費時間，而且容易在它剛放手那一刻錯過。
這支每 20 秒探一次，搶到就生，生完就走。

用法：python wait_and_gen_scene.py <prompt.txt> <out.jpg> [最多等幾分鐘，預設 40]
"""
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = HERE / ".browser.lock"

prompt_file, out = sys.argv[1], sys.argv[2]
max_min = int(sys.argv[3]) if len(sys.argv) > 3 else 40

t0 = time.time()
tries = 0
while time.time() - t0 < max_min * 60:
    if LOCK.exists():
        age = (time.time() - LOCK.stat().st_mtime) / 60
        holder = LOCK.read_text(encoding="utf-8", errors="replace").strip()[:40]
        if age < 30:
            if tries % 6 == 0:      # 每 2 分鐘報一次，不要洗版
                print(f"  [{int((time.time()-t0)/60)}分] 等待中，佔用者：{holder}", flush=True)
            tries += 1
            time.sleep(20)
            continue

    print(f"鎖空出來了（等了 {int((time.time()-t0)/60)} 分鐘），開始生圖", flush=True)
    r = subprocess.run(
        [sys.executable, str(HERE / "make_scene.py"), prompt_file, out],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=900)
    tail = (r.stdout or "").strip().splitlines()[-3:]
    for ln in tail:
        print("   ", ln)

    if r.returncode == 8:
        print("  又被搶走了，繼續等", flush=True)
        time.sleep(20)
        continue
    if r.returncode == 0 and Path(out).exists():
        print("SUCCESS", out)
        sys.exit(0)
    print(f"  生圖失敗 rc={r.returncode}，20 秒後重試", flush=True)
    time.sleep(20)

print(f"FAILED: 等滿 {max_min} 分鐘還是搶不到")
sys.exit(1)
