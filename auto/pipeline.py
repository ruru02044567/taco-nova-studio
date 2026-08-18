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

# 開拍前判斷「這鏡本機拍不拍得出來」。全本機之後這步不能省 ——
# 判錯的代價從「多花 15 點雲端額度」變成「白燒 6.5 分鐘算力再加一輪審片」。
import plan_model

sys.stdout.reconfigure(encoding="utf-8")

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
# ⚠️ 2026-08-16 起產線不再呼叫 Veo（賢賢定案：影片全本機生成）。
# 上面兩個常數和 veo_backoff_h() 留著沒刪，是因為 make_video_cloud.py／veo_quota.py
# 還在，手動要救急時可以直接叫。自動排程這條路上已經沒有任何地方會走到它們。
#
# 本機生片的失敗次數只**記錄**、不拿來停產線。
# 8/16 曾加過 LOCAL_MAX_FAILS = 3，同日撤回：那個 3 是拍腦袋定的，沒有任何實測依據，
# 而「幾次算撞牆」正是 LOCAL_VIDEO_ENGINE_BENCHMARK 要量出來的東西之一。
# 在有數據之前，寧可沒有閾值，也不要有一個假裝有根據的閾值。
# 擋掉「注定失敗」的片是 plan_model 的 BLOCKED 在做，不靠這個計數。

SCRATCH = Path(os.environ.get("GBOT_DIR", HERE))   # gbot.py 等工具放這
LOCAL_GEN = Path(r"C:\Users\TUF Gaming\ai-video-local")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = r"C:\Users\TUF Gaming\.config\gemini-bot-profile"

# 2026-08-13 加：這台機器有兩個 Python，套件裝在不同地方。
#   系統 Python  → playwright（所有瀏覽器自動化：發布、Gemini 生圖）
#   ComfyUI venv → torch / diffusers（生圖生片）
# run() 原本一律用 sys.executable，也就是「誰跑 pipeline.py 就用誰」——
# 8/13 10:37 用 venv 跑，publish_video.py 立刻 ModuleNotFoundError: playwright。
# 需要瀏覽器的腳本改成明確指定系統 Python，不要靠呼叫者記得。
SYS_PY = Path(r"C:\Users\TUF Gaming\AppData\Local\Programs\Python\Python313\python.exe")
BROWSER_SCRIPTS = {"publish_video.py", "gbot.py", "studio_stats.py",
                   "update_desc.py", "update_title.py", "video_stats.py", "video_reach.py"}

# G-Brain 的專案索引。2026-08-12 起 G-Brain 已停用搬離，這個檔不存在，
# 存在時才會去回寫（見 publish()）。復原 G-Brain 後不用改程式，自動恢復。
GBRAIN_INDEX = Path(r"C:\Users\TUF Gaming\.claude\G-Brain\01-專案\_索引.md")

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


def ensure_comfy():
    """確保本機 ComfyUI 活著（生圖／生片的 fallback 要用）。

    注意：comfy_api.py 刻意設計成「不會自己啟動也不會關閉」伺服器 ——
    因為這台機器踩過「兩支腳本各自開伺服器又關掉，後結束的把前一支
    排隊中的工作殺掉」。所以啟動這件事只由 pipeline 這個唯一的自動化主體做，
    而且只在沒開的時候開，開了就不關（卡通農場那邊也在共用同一個伺服器）。
    """
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=4)
        return True
    except Exception:
        pass
    log("  ComfyUI 沒開，啟動中")
    subprocess.Popen(
        [str(LOCAL_GEN / "venv/Scripts/python.exe"), "main.py",
         "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch"],
        cwd=str(LOCAL_GEN / "ComfyUI"),
        stdout=open(LOCAL_GEN / "comfyui.log", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT)
    for _ in range(24):
        time.sleep(5)
        try:
            urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=4)
            log("  ComfyUI 就緒")
            return True
        except Exception:
            continue
    log("  ComfyUI 起不來")
    return False


def run(script, *args, timeout=1800):
    """跑 scratchpad 裡的工具腳本。

    需要瀏覽器（playwright）的腳本一律用系統 Python，其餘沿用呼叫者的直譯器。
    """
    py = sys.executable
    if script in BROWSER_SCRIPTS and SYS_PY.exists():
        py = str(SYS_PY)
    cmd = [py, str(SCRATCH / script), *[str(a) for a in args]]
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
        # 把進度回寫到 G-Brain 的專案索引（2026-08-11 加）。
        # 起因：索引一直寫著「萬事俱備，只差開拍」，那時候其實已經發了 6 支 ——
        # 別的對話視窗會照著那句話做事。會過期的根因是「做完沒回寫」，靠人記得沒用。
        # ⚠️ 整段包在 try 裡：回寫失敗絕對不能影響「已經發布成功」這個事實，
        # 也不能讓 publish() 回傳 False（那會讓產線以為沒發出去而重試）。
        #
        # 2026-08-13：G-Brain 已停用搬離，索引檔不存在，這支每次都印一行 SKIP。
        # 無害，但那是每次發布都會出現的雜訊，會蓋掉真正該看的訊息。
        # 改成「索引檔在才呼叫」——腳本本身保留，G-Brain 復原後自動恢復回寫。
        if GBRAIN_INDEX.exists():
            try:
                run("sync_gbrain.py", timeout=60)
            except Exception as e:
                log(f"  （回寫 G-Brain 索引失敗，不影響發布）{type(e).__name__}: {e}")
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
                # 這裡以前是 return，等於「有一支在等發布時間」就讓整個 tick 收工。
                # 配上 LEAD_HOURS=16（提前 16 小時生好）之後就變成災難：
                # 核准完到發布之間那 16 小時，產線每 20 分鐘醒來、看到這支在等、直接收工，
                # 下一支永遠不會開始生。改成 continue —— 這支只是在等時鐘，不該擋住別人。
                continue
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

    # 這鏡本機拍不拍得出來？拍不出來就不要浪費算力，直接請賢賢改劇本。
    # 2026-08-16 全本機之後，plan_model 的輸出從「選模型」變成「能不能拍」。
    plan = plan_model.decide(item.get("videoPrompt") or item["title"])
    if plan["model"] == "BLOCKED":
        st["blocked"] = plan
        state[key] = st
        save(STATE, state)
        log(f"  ⛔ 本機做不到（瓶頸「{plan['bottleneck']}」{plan['local_min_score']} 分），這輪不生")
        log(f"     建議改寫：{plan.get('rewrite_hint') or '（無）'}")
        log("     改完 schedule.json 的 videoPrompt 再跑一次就會繼續")
        return
    st["model_selection"] = plan
    # 一律用 .get()：劇本比對不到任何已知任務時，decide() 回的 dict 沒有 bottleneck 這個鍵
    # （D11S1 就是這種），寫成 plan['bottleneck'] 會讓整條產線 KeyError 掛在這裡。
    log(f"  模型判斷：{plan['model']}"
        f"（{plan.get('motion_class') or '未分類'}，"
        f"瓶頸「{plan.get('bottleneck') or '比對不到已知任務，當沒測過處理'}」）")

    # Edge 起不來就這輪不做。2026-08-16 曾短暫改成「靜默改走本機生圖」，當天撤回：
    # 那是沒有測試依據的降級，而且本機生圖畫不出 Taco 的黑點眉 —— 片子照樣生、照樣送審，
    # 招牌卻不見了。停下來吵人，好過安靜地變爛。
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
        # 2026-08-18 賢賢裁示：生圖也全本機，雲端 Gemini 從自動流程移除
        # （make_scene.py 檔案保留當手動救急工具，比照 Veo 死碼慣例）。
        # 主路 FLUX schnell（可鎖 seed、約 45 秒/張）；黑點眉偏弱是已知代價：
        # gate 抽幀會抓，弱到不行就用 PIL 原地放大（作法見 _fix_d9_dots.py 的格線校準）。
        # 注意：gen_scene_flux 是直接複製 png bytes 到指定路徑，scene 副檔名是 .jpg
        # 也沒關係——下游 ffmpeg／PIL 都認內容不認副檔名。
        if not ensure_comfy():
            log("  本機 ComfyUI 起不來，下次再試")
            return
        ok, _ = run("gen_scene_flux.py",
                    "--prompt-file", prompt_file, "--out", scene,
                    "--width", "704", "--height", "1280", timeout=900)
        if ok and scene.exists():
            st["scene_source"] = "flux"
            log("  場景圖 OK（FLUX 本機）")
        else:
            log("  FLUX 生圖失敗 → 改用 SDXL 本機")
            ok2, _ = run("gen_scene_local.py",
                         "--prompt-file", prompt_file, "--out", scene,
                         "--ref", "taco_face.png", "--tag", key, timeout=900)
            if not ok2 or not scene.exists():
                log("  本機生圖也失敗，下次再試")
                return
            st["scene_source"] = "local"
            log("  場景圖 OK（SDXL 本機）")
    st["scene"] = str(scene)
    state[key] = st
    save(STATE, state)
    log(f"  場景圖 OK：{scene.name}")

    # 3) 影片 —— 全本機 Wan 2.2 單段 5 秒（賢賢 2026-08-16 定案，不再走 Veo）。
    #    為什麼單段：8/9 三次實測接龍第二段每次都崩（長人手／增生第二隻狗／換品種）。
    #    舊註解寫「本機畫面會歪掉不准發布」是 8/8 的鐵律，8/11 已經解除
    #    （9,882 觀看那支就是本機生的，198 觀看那支反而是純 Veo），只是程式碼一直沒跟上。
    video = CLIPS / f"{key}.mp4"
    if video.exists() and st.get("source") not in ("local", "veo"):
        log("  發現來路不明的同名影片，砍掉重生")
        video.unlink()
    if not video.exists():
        if not ensure_comfy():
            log("  本機 ComfyUI 起不來，下次再試（不算失敗次數）")
            return
        vp = CLIPS / f"{key}_video.txt"
        vp.write_text(item["videoPrompt"], encoding="utf-8")
        steps = plan_model.POLICY["local_best_config"]["steps"]
        # timeout 抓 30 分鐘：704×1280 單段實測 6.5–7.8 分鐘，冷載入模型再加幾分鐘。
        # 給得寬是因為 timeout 砍掉的是「還在跑的正常工作」，比失敗更難查。
        ok, out = run("make_video_local_5s.py", scene, vp, video,
                      "--steps", str(steps), timeout=1800)
        if not ok or not video.exists():
            # 只記錄，不擋。這個數字是 benchmark 的原始資料（失敗率要靠它算），
            # 但「幾次算撞牆」在量出來之前不設閾值。
            fails = st.get("local_fails", 0) + 1
            st["local_fails"] = fails
            st["local_last_error"] = out[-300:] if out else ""
            state[key] = st
            save(STATE, state)
            log(f"  本機生片失敗（這支累計第 {fails} 次），下次 tick 再試")
            return
    st.update({"video": str(video), "source": "local", "local_fails": 0})
    log(f"  影片 OK（本機 Wan 2.2，steps {plan_model.POLICY['local_best_config']['steps']}）：{video.name}")

    # 4) 送待審，等賢賢看過才發
    st["awaiting_review"] = True
    state[key] = st
    save(STATE, state)
    to_review(key, item, video, "本機 Wan 2.2")


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
    # 已發布的不准重打 ok：重發同支會靠 publish_video 的檔名比對兜底，但不該走到那層
    if st.get("published"):
        print(f"{key} 已在 {st.get('at', '?')} 發布過（{st.get('url', '')}），不重發")
        return
    # 發布前程式閘門（2026-08-18 加）：無聲原片、靜音軌、超時長、黑名單在這裡硬擋。
    # 起因：8/18 前的流程裡，state 的 video 若還指著無聲原片，會被原樣發上去。
    # preflight 未過就不標核准、不發布，片子留在待審狀態等修好再 ok 一次。
    ok_pf, out_pf = run("preflight.py", st.get("video", ""), "--key", key, timeout=600)
    print(out_pf.strip())
    if not ok_pf:
        log(f"  ✗ {key.upper()} preflight 未過，不發布。"
            f"通常是還沒做成片：python auto\\finish_video.py {key}")
        return
    st["approved"] = True
    st["awaiting_review"] = False
    state[key] = st
    save(STATE, state)
    item = next((i for i in sched["schedule"] if f"d{i['day']}s{i['slot']}" == key), None)
    if item is None:
        log(f"  ⚠ {key} 不在 schedule.json（archived？）——已標核准但無法自動發布，需人工處理")
        return
    if ensure_edge():
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
