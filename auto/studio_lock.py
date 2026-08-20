"""產線互斥鎖 —— 同一時間只准一個視窗操作影片產線。

## 為什麼需要（2026-08-20 賢賢問「為什麼兩個視窗在跑同一件事」查出來的）

8/19 夜到 8/20 晨，兩個 Claude 視窗同時在財富密碼產線上各做一支片
（本視窗 D10 藏破蛋、值班視窗 D11 黑漆熊貓），共用了四樣東西：

  1. 同一個 git repo   → 隔壁視窗 3 筆 commit 是「checkpoint: 另一視窗工作檔」
                          （它開工前把別人沒存的檔一起 commit 了）
  2. 同一個 state.json → 整檔讀寫、後寫覆蓋先寫。這次沒掉資料是運氣不是設計
  3. 同一張顯卡        → ComfyUI 單伺服器，兩邊同時生片只能排隊
  4. 同一份產線程式碼  → 隔壁 01:16 改了 finish_video，本視窗 02:00 後還在用它

結果：兩支片都出問題（一支被擅自發布、一支複審 FAIL）。

**這台機器只有一張顯卡，所以開兩個視窗做影片根本不會比較快** —— 兩個廚師搶同
一個爐子，菜不會更快出，只會互相燙到。所以規則是「產線工作一次只開一個視窗」，
這支檔案是那條規則的執法工具（文件靠運氣，程式才會擋 —— 8/18 的教訓）。

## 用法

腳本開頭：

    import studio_lock
    studio_lock.acquire("pipeline tick d10s1")

拿不到鎖 → 印出誰在用、退出碼 9（＝讓路，不是失敗）。

可重入：pipeline 用 subprocess 呼叫 gen_scene_flux／make_video_local_5s，
子行程的 pid 跟父行程不同，會被自己的鎖擋死。所以父行程拿到鎖後把根 pid 寫進
環境變數 STUDIO_LOCK_OWNER，subprocess 預設繼承環境變數，子行程看到自己屬於
同一條工作鏈就直接放行。

人要查／強制解：

    python auto\\studio_lock.py status     # 現在誰在用產線
    python auto\\studio_lock.py release    # 強制解鎖（確定對方已經死了才用）
"""
import atexit
import os
import sys
import threading
import time
from pathlib import Path

LOCK = Path(__file__).parent / ".studio.lock"
# 生一段 5 秒影片實測 8 分鐘，一輪 tick 可能連生場景圖＋兩段影片，冷載入再加幾分鐘。
# 給得寬是因為「誤判對方已死而搶鎖」比「多等一下」危險得多。
STALE_MIN = 45
ENV_OWNER = "STUDIO_LOCK_OWNER"
EXIT_BUSY = 9


def _read():
    """回 (who, pid, age_min)；鎖不存在或讀不到回 None。"""
    if not LOCK.exists():
        return None
    try:
        raw = LOCK.read_text(encoding="utf-8", errors="replace").strip()
        age = (time.time() - LOCK.stat().st_mtime) / 60
    except Exception:
        return None
    pid = ""
    for tok in raw.split():
        if tok.startswith("pid="):
            pid = tok[4:]
    return raw, pid, age


def acquire(who="unknown"):
    """拿產線鎖。拿不到就 exit 9（讓路）。同一條工作鏈的子行程直接放行。"""
    cur = _read()
    root = os.environ.get(ENV_OWNER)

    if cur:
        raw, pid, age = cur
        if root and pid and pid == root:
            return                      # 同一條工作鏈的子行程，放行
        if age < STALE_MIN:
            print(f"⛔ 產線被另一個視窗佔用中：{raw[:90]}（{age:.0f} 分鐘前）")
            print(f"   這台只有一張顯卡，同時跑不會比較快，只會互相踩。")
            print(f"   等它跑完，或去做不碰產線的事（看數據／寫企劃／整理文件）。")
            print(f"   確定對方已經死了才強制解：python auto\\studio_lock.py release")
            sys.exit(EXIT_BUSY)
        print(f"  蓋掉過期的產線鎖（{age:.0f} 分鐘沒更新，前一支應該已經死了）")

    me = os.getpid()
    LOCK.write_text(f"{who} pid={me} {time.strftime('%m-%d %H:%M:%S')}",
                    encoding="utf-8")
    os.environ[ENV_OWNER] = str(me)     # 讓 subprocess 認得自己人
    atexit.register(release)
    _start_heartbeat(who, me)


def _start_heartbeat(who, me):
    """每分鐘更新時間戳證明還活著，免得跑超過 STALE_MIN 的工作被別人蓋掉。"""
    def beat():
        while True:
            time.sleep(60)
            try:
                cur = _read()
                if not cur or f"pid={me}" not in cur[0]:
                    return              # 已 release 或鎖已易主，別亂蓋回去
                LOCK.write_text(f"{who} pid={me} {time.strftime('%m-%d %H:%M:%S')}",
                                encoding="utf-8")
            except Exception:
                return

    threading.Thread(target=beat, daemon=True).start()


def release():
    """只解自己的鎖 —— 子行程結束時不可以把父行程的鎖收掉。"""
    try:
        cur = _read()
        if cur and f"pid={os.getpid()}" in cur[0]:
            LOCK.unlink(missing_ok=True)
    except Exception:
        pass


def _cli():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    cur = _read()
    if cmd == "status":
        if not cur:
            print("✅ 產線閒置，可以開工")
            return 0
        raw, _, age = cur
        state = "過期（可蓋掉）" if age >= STALE_MIN else "使用中"
        print(f"🔒 產線{state}：{raw}（{age:.0f} 分鐘前）")
        return 0
    if cmd == "release":
        if not cur:
            print("產線本來就沒鎖")
            return 0
        LOCK.unlink(missing_ok=True)
        print(f"已強制解鎖（原持有：{cur[0][:80]}）")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(_cli())
