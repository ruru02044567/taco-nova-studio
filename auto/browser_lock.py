"""遙控瀏覽器的互斥鎖 —— 同一時間只准一支腳本操作那個 Edge 視窗。

為什麼需要（8/10 傍晚花了三輪才看懂）：
產線由工作排程器每 20 分鐘叫醒一次，而人在對話視窗裡也會手動跑同一批腳本。
兩邊都會 `page.goto('https://gemini.google.com/app')` 開新對話 ——
於是排程器一跑，就把手動那支「正在等 Veo 生片」的對話整個沖掉。

症狀偽裝得很好，害我一路修錯地方：
  - 等待中的那支看到對話消失 → 以為「Veo 生到一半自己斷線」
  - 或是頁面被導走 → Playwright 丟 Execution context was destroyed，腳本直接炸
  - 排程器那支也失敗，因為手動那支正卡在別的步驟

用法：任何會操作遙控瀏覽器的腳本，開頭加

    from browser_lock import acquire
    acquire("make_video_cloud")

拿不到鎖就 exit 8（＝讓路，不是失敗），上層看到 8 不要算進 Veo 失敗次數。
"""
import atexit
import os
import sys
import threading
import time
from pathlib import Path

LOCK = Path(__file__).parent / ".browser.lock"
# 超過這個時間沒更新就當成上一支已經死了（Veo 最長等 20 分鐘，留一點餘裕）
STALE_MIN = 30


def acquire(who="unknown"):
    if LOCK.exists():
        age_min = (time.time() - LOCK.stat().st_mtime) / 60
        if age_min < STALE_MIN:
            holder = LOCK.read_text(encoding="utf-8", errors="replace").strip()[:80]
            print(f"SKIP: 遙控瀏覽器被佔用中（{holder}，{age_min:.0f} 分鐘前），這輪讓路")
            sys.exit(8)
        print(f"  蓋掉過期的鎖（{age_min:.0f} 分鐘沒更新，前一支應該已經死了）")
    LOCK.write_text(f"{who} pid={os.getpid()} {time.strftime('%H:%M:%S')}",
                    encoding="utf-8")
    atexit.register(release)
    _start_heartbeat(who)


def _start_heartbeat(who):
    """每分鐘更新鎖檔時間戳，證明自己還活著。

    沒有這個的話，跑超過 STALE_MIN（30 分）的工作會被別人當成死掉、
    把鎖蓋掉接手 —— 正是這支檔案開頭在講的那場災難，只是換成我們自己當受害者。
    daemon thread：主程式結束就跟著死，不會卡住 exit。
    """
    me = os.getpid()

    def beat():
        while True:
            time.sleep(60)
            try:
                if not LOCK.exists():
                    return                      # 已經 release 了
                if f"pid={me}" not in LOCK.read_text(encoding="utf-8", errors="replace"):
                    return                      # 鎖已經易主，別亂蓋回去
                LOCK.write_text(f"{who} pid={me} {time.strftime('%H:%M:%S')}",
                                encoding="utf-8")
            except Exception:
                return

    threading.Thread(target=beat, daemon=True).start()


def release():
    try:
        LOCK.unlink(missing_ok=True)
    except Exception:
        pass
