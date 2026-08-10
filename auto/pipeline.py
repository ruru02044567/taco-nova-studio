"""Taco & Nova 七天自動產線（不依賴 Claude 對話，由 Windows 工作排程器叫起來）。

每次被叫起來就做一件事：看 schedule.json 裡有沒有「該做但還沒做」的工作，有就做，做完寫進 state.json。
關機也沒關係：工作排程器設了「錯過就開機後盡快補跑」，補跑時這支腳本會自己判斷該補哪一格。

用法（排程器每 20 分鐘叫一次）：
    python pipeline.py tick

其他指令：
    python pipeline.py status    看目前進度
    python pipeline.py plan      印出未來 24 小時要做什麼
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
PROJECT = HERE.parent
CHAR = PROJECT / "character"
CLIPS = PROJECT / "auto" / "clips"
CLIPS.mkdir(parents=True, exist_ok=True)

SCHEDULE = HERE / "schedule.json"
STATE = HERE / "state.json"
LOG = HERE / "pipeline.log"
REVIEW = PROJECT / "待審核"          # 生好但還沒給賢賢看過的片子放這
REVIEW.mkdir(parents=True, exist_ok=True)

# Veo（雲端）失敗後隔多久再試一次 —— 依失敗次數遞增（小時）。
# 8/9 D1S1 那支就是死在固定等 1 小時：連失敗 3 次＝白等 3 小時，
# 但 8/10 實測服務端抽風（錯誤 1155）隔幾分鐘重送就過了。前幾次快點重試才對。
# 真正該等久的只有「額度用完」，那個走 quota_reset_h() 等到重置。
VEO_BACKOFF_H = [0.1, 0.1, 0.35, 0.35, 1, 1, 2, 2]   # 6分、6分、20分、20分、1時…
# 連續失敗幾次就不要再自動重試，等人來看
VEO_MAX_FAILS = 8

SCRATCH = Path(os.environ.get("GBOT_DIR", HERE))   # gbot.py 等工具放這
LOCAL_GEN = Path(r"C:\Users\TUF Gaming\ai-video-local")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = r"C:\Users\TUF Gaming\.config\gemini-bot-profile"

# 發布時段（台北時間，小時）
SLOT_HOURS = {1: 8, 2: 20, 3: 0}
# 超過幾小時就算「錯過」，改成盡快補發
LATE_TOLERANCE_H = 6

# 提前多久開始生片。生成＋審核都要時間，排在發布時刻才開工一定遲到。
# 16 小時＝ 08:00 的片子前一天 16:00 就開始生（剛好在 Veo 額度 15:00 重置之後，
# 額度最滿的時候），賢賢晚上或早上起床都能審，08:00 一到就能直接發。
LEAD_HOURS = 16


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_edge():
    """確保遙控用的 Edge 開著且 CDP 通。"""
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=4)
        return True
    except Exception:
        pass
    log("Edge/CDP 沒開，啟動中")
    subprocess.Popen([
        EDGE, "--remote-debugging-port=9222", f"--user-data-dir={PROFILE}",
        "--no-first-run", "--window-position=2000,2000", "--window-size=1400,1000",
        "https://gemini.google.com/app",
    ])
    for _ in range(20):
        time.sleep(3)
        try:
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=4)
            log("CDP 就緒")
            return True
        except Exception:
            continue
    log("FATAL: CDP 起不來")
    return False


def quota_reset_h():
    """離下一次台北 15:00 額度重置還有幾小時。"""
    now = datetime.now()
    reset = now.replace(hour=15, minute=5, second=0, microsecond=0)
    if now >= reset:
        reset += timedelta(days=1)
    return max(0.1, (reset - now).total_seconds() / 3600)


def veo_backoff_h(out, fails):
    """這次失敗該等多久。額度用完等重置，其他照 VEO_BACKOFF_H 遞增。"""
    if "額度用完" in out:
        return quota_reset_h()
    return VEO_BACKOFF_H[min(fails, len(VEO_BACKOFF_H)) - 1]


def run(script, *args, timeout=1800):
    """跑 scratchpad 裡的工具腳本。"""
    cmd = [sys.executable, str(SCRATCH / script), *[str(a) for a in args]]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    # encoding 一定要指定 utf-8：不指定的話 Windows 會用 cp950 解碼子腳本的輸出，
    # 只要對方印出一個中文字就 UnicodeDecodeError，錯誤訊息整段被吃掉、只剩 rc=1。
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    log(f"  $ {script} {' '.join(str(a) for a in args)[:70]} -> rc={p.returncode}")
    for ln in out.strip().splitlines()[-16:]:   # 留少了會把真正的失敗原因截掉，只剩 python 的堆疊尾巴
        log(f"    | {ln[:150]}")
    return p.returncode == 0, out


def contact_sheet(video, out_jpg):
    """抽 3 張影格拼成一張圖，讓賢賢在對話框裡一眼看完畫面對不對。"""
    try:
        subprocess.run(
            ["ffmpeg", "-v", "quiet", "-y", "-i", str(video),
             "-vf", "select='eq(n\\,8)+eq(n\\,90)+eq(n\\,200)',scale=360:-1,tile=3x1",
             "-frames:v", "1", str(out_jpg)],
            timeout=120, check=False)
        return out_jpg.exists()
    except Exception as e:
        log(f"  抽影格失敗（不影響流程）：{e}")
        return False


def to_review(key, item, video, source):
    """把片子送進待審，不發布。"""
    dst = REVIEW / f"{key}.mp4"
    try:
        dst.write_bytes(Path(video).read_bytes())
    except Exception as e:
        log(f"  複製到待審資料夾失敗：{e}")
        dst = Path(video)
    sheet = REVIEW / f"{key}-畫面.jpg"
    contact_sheet(video, sheet)
    (REVIEW / f"{key}-說明.txt").write_text(
        f"{item['title']}\n\n{item['description']}\n\n"
        f"生成方式：{source}\n影片：{dst}\n"
        f"核准發布： python pipeline.py ok {key}\n",
        encoding="utf-8")
    log(f"  ⏸ 已送待審（未發布）：{dst.name}　→ 賢賢過目後跑 `pipeline.py ok {key}`")


def publish(key, item, st, state):
    """真的發上 YouTube。只有核准過的才會走到這。"""
    video = Path(st["video"])
    t = CLIPS / f"{key}_title.txt"
    d = CLIPS / f"{key}_desc.txt"
    t.write_text(item["title"], encoding="utf-8")
    d.write_text(item["description"], encoding="utf-8")
    ok, out = run("publish_video.py", video, t, d, timeout=1200)
    url = ""
    for ln in out.splitlines():
        if "youtube.com/shorts/" in ln:
            url = ln.strip().split()[-1]
    if ok and url:
        st.update({"published": True, "url": url,
                   "at": datetime.now().isoformat(timespec="seconds")})
        state[key] = st
        save(STATE, state)
        log(f"  已發布：{url}")
        return True
    log("  發布失敗，下次再試")
    return False


def slot_datetime(day_index, slot, day1_date):
    """回傳該格的預定發布時間（datetime）。"""
    d = day1_date + timedelta(days=day_index - 1)
    hour = SLOT_HOURS[slot]
    dt = datetime(d.year, d.month, d.day, hour, 0)
    if slot == 3:          # 00:00 屬於當天的最後一格 → 隔天凌晨
        dt += timedelta(days=1)
    return dt


def due_items(sched, state):
    """找出現在該「開始生片」的項目。

    注意：生片提前 LEAD_HOURS 開工，發布仍照 planned 時刻。
    這樣賢賢在發布時刻之前就有片可審，不會像 8/10 那樣 08:00 才開工、必定遲到。
    """
    day1 = datetime.strptime(sched["day1_date"], "%Y-%m-%d")
    now = datetime.now()
    todo = []
    for item in sched["schedule"]:
        key = f"d{item['day']}s{item['slot']}"
        st = state.get(key, {})
        if st.get("published"):
            continue
        planned = slot_datetime(item["day"], item["slot"], day1)
        if now >= planned - timedelta(hours=LEAD_HOURS):
            late_h = (now - planned).total_seconds() / 3600   # 負數＝還沒到發布時刻
            todo.append((planned, late_h, item, key, st))
    todo.sort(key=lambda x: x[0])
    return todo


def ready_to_publish(planned):
    """核准過的片子，時間到了才真的發出去（提前生好不代表提前發）。"""
    return datetime.now() >= planned


def cmd_status():
    sched = load(SCHEDULE, {"schedule": []})
    state = load(STATE, {})
    done = sum(1 for k, v in state.items() if v.get("published"))
    print(f"排程共 {len(sched.get('schedule', []))} 支，已發布 {done} 支")
    for item in sched.get("schedule", []):
        key = f"d{item['day']}s{item['slot']}"
        st = state.get(key, {})
        mark = "OK " if st.get("published") else ("..." if st.get("video") else "   ")
        print(f"  {mark} D{item['day']}S{item['slot']}  {item['title'][:58]}")
        if st.get("url"):
            print(f"        {st['url']}")


def cmd_plan():
    sched = load(SCHEDULE, {"schedule": []})
    state = load(STATE, {})
    for planned, late_h, item, key, st in due_items(sched, state):
        print(f"DUE  {planned:%m-%d %H:%M}  (晚了 {late_h:.1f}h)  {item['title'][:50]}")


def cmd_tick():
    sched = load(SCHEDULE, None)
    if not sched:
        log("還沒有 schedule.json，跳過")
        return
    state = load(STATE, {})
    todo = due_items(sched, state)
    if not todo:
        log("目前沒有到期的工作")
        return

    # ── 0) 有核准過還沒發的，時間到了就發掉 ────────────
    day1 = datetime.strptime(sched["day1_date"], "%Y-%m-%d")
    for k, v in state.items():
        if v.get("approved") and not v.get("published"):
            it = next((i for i in sched["schedule"] if f"d{i['day']}s{i['slot']}" == k), None)
            if not it:
                continue
            planned = slot_datetime(it["day"], it["slot"], day1)
            if not ready_to_publish(planned):
                # 提前生好、也審過了，但還沒到發布時刻 → 等
                mins = (planned - datetime.now()).total_seconds() / 60
                log(f"✅ {k.upper()} 已核准，等 {planned:%m-%d %H:%M} 發布（還有 {mins:.0f} 分鐘）")
                return
            if ensure_edge():
                log(f"處理已核准的 {k.upper()}：{it['title'][:50]}")
                publish(k, it, v, state)
            return

    # ── 1) 有東西在等賢賢過目，就不要再生新的 ──────────
    waiting = [k for k, v in state.items()
               if v.get("awaiting_review") and not v.get("published")]
    if waiting:
        log(f"⏸ {', '.join(k.upper() for k in waiting)} 還在等賢賢過目，先不動作")
        return

    planned, late_h, item, key, st = todo[0]
    log(f"處理 D{item['day']}S{item['slot']}：{item['title'][:60]}（預定 {planned:%m-%d %H:%M}，晚 {late_h:.1f}h）")

    if late_h > LATE_TOLERANCE_H:
        log(f"  超過容忍 {LATE_TOLERANCE_H}h，改為立即補做（不再等原時段）")

    # Veo 剛失敗過就先別急著再試，等額度回來
    nxt = st.get("veo_retry_after")
    if nxt and datetime.now() < datetime.fromisoformat(nxt):
        log(f"  Veo 上次失敗，{nxt[:16]} 之後再試")
        return
    if st.get("veo_fails", 0) >= VEO_MAX_FAILS:
        log(f"  Veo 連續失敗 {st['veo_fails']} 次，停止自動重試 —— 等賢賢處理")
        return

    if not ensure_edge():
        return

    # 2) 場景圖
    # 只有 state 認得的檔案才敢重用。否則換題材時會撿到上一個題材留下的同名舊檔，
    # 8/8 就發生過：舊題材的本機片被當成新片送審。
    scene = CLIPS / f"{key}_scene.jpg"
    if scene.exists() and st.get("scene") != str(scene):
        log("  發現來路不明的同名場景圖（可能是舊題材留下的），砍掉重生")
        scene.unlink()
        (CLIPS / f"{key}.mp4").unlink(missing_ok=True)
    if not scene.exists():
        prompt_file = CLIPS / f"{key}_scene.txt"
        prompt_file.write_text(item["scenePrompt"], encoding="utf-8")
        ok, _ = run("make_scene.py", prompt_file, scene)
        if not ok or not scene.exists():
            log("  場景圖失敗，下次再試")
            return
    st["scene"] = str(scene)
    state[key] = st
    save(STATE, state)
    log(f"  場景圖 OK：{scene.name}")

    # 3) 影片 —— 只走 Veo。本機 ComfyUI 畫面會歪掉，不准拿來發布。
    video = CLIPS / f"{key}.mp4"
    if video.exists() and st.get("source") != "veo":
        log("  發現來路不明的同名影片，砍掉重生")
        video.unlink()
    if not video.exists():
        vp = CLIPS / f"{key}_video.txt"
        vp.write_text(item["videoPrompt"], encoding="utf-8")
        ok, out = run("make_video_cloud.py", scene, vp, video, timeout=1200)
        if not ok and "SKIP:" in out:
            # 有人在手動跑（對話視窗裡），瀏覽器讓給他。這不是 Veo 失敗，不要累計次數，
            # 否則手動操作一久，產線就自己把 veo_fails 撞到上限停擺。
            log("  遙控瀏覽器被別人佔用，這輪讓路（不算失敗）")
            return
        if not ok or not video.exists():
            fails = st.get("veo_fails", 0) + 1
            wait_h = veo_backoff_h(out, fails)
            st["veo_fails"] = fails
            st["veo_retry_after"] = (datetime.now() + timedelta(hours=wait_h)).isoformat(timespec="seconds")
            state[key] = st
            save(STATE, state)
            why = "額度用完，等重置" if "額度用完" in out else "服務抽風"
            log(f"  Veo 失敗（第 {fails} 次，{why}），{wait_h * 60:.0f} 分鐘後再試。不改用本機。")
            return
    st.update({"video": str(video), "source": "veo", "veo_fails": 0})
    log(f"  影片 OK（Veo）：{video.name}")

    # 4) 送待審，等賢賢看過才發
    st["awaiting_review"] = True
    state[key] = st
    save(STATE, state)
    to_review(key, item, video, "Veo")


def cmd_review():
    """列出等著給賢賢看的片子。"""
    state = load(STATE, {})
    waiting = [(k, v) for k, v in state.items()
               if v.get("awaiting_review") and not v.get("published")]
    if not waiting:
        print("沒有待審的片子")
        return
    for k, v in waiting:
        print(f"待審 {k.upper()}")
        print(f"  影片： {REVIEW / (k + '.mp4')}")
        print(f"  畫面： {REVIEW / (k + '-畫面.jpg')}")
        print(f"  核准： python pipeline.py ok {k}")


def cmd_ok():
    """賢賢看過說可以 → 標記核准，並且立刻發布。"""
    sched = load(SCHEDULE, {"schedule": []})
    state = load(STATE, {})
    key = sys.argv[2] if len(sys.argv) > 2 else None
    if not key:
        key = next((k for k, v in state.items()
                    if v.get("awaiting_review") and not v.get("published")), None)
    if not key or key not in state:
        print("找不到待審的片子")
        return
    st = state[key]
    st["approved"] = True
    st["awaiting_review"] = False
    state[key] = st
    save(STATE, state)
    item = next((i for i in sched["schedule"] if f"d{i['day']}s{i['slot']}" == key), None)
    if item and ensure_edge():
        log(f"賢賢核准 {key.upper()}，發布中")
        publish(key, item, st, state)


def cmd_no():
    """賢賢說不行 → 退回重做（砍掉影片，下次 tick 會重生）。"""
    state = load(STATE, {})
    key = sys.argv[2] if len(sys.argv) > 2 else None
    if not key:
        key = next((k for k, v in state.items()
                    if v.get("awaiting_review") and not v.get("published")), None)
    if not key or key not in state:
        print("找不到待審的片子")
        return
    v = state[key]
    for p in [Path(v.get("video", "")), CLIPS / f"{key}_scene.jpg", REVIEW / f"{key}.mp4"]:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
    state[key] = {}
    save(STATE, state)
    log(f"{key.upper()} 退回重做，場景圖和影片都砍了，下次 tick 重生")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tick"
    {"tick": cmd_tick, "status": cmd_status, "plan": cmd_plan,
     "review": cmd_review, "ok": cmd_ok, "no": cmd_no}.get(cmd, cmd_tick)()
