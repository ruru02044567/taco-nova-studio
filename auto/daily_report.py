"""每天早上抓頻道數據 → 存成當天的原始檔 → 叫 claude.exe 寫成一份人看得懂的體檢報告。

由 Windows 工作排程器每天 07:00 叫起來（錯過會在開機後補跑）。
不依賴任何 Claude 對話視窗。

用法：
    python daily_report.py            # 抓數據 + 產報告
    python daily_report.py --raw      # 只抓數據不叫 claude
"""
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
PROJECT = HERE.parent
REPORTS = PROJECT / "每日體檢"
REPORTS.mkdir(parents=True, exist_ok=True)

CH = "UC4Bf0lB05GrYF8Q4l6NnjEA"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = r"C:\Users\TUF Gaming\.config\gemini-bot-profile"
CLAUDE = r"C:\Users\TUF Gaming\AppData\Roaming\npm\claude.cmd"

TABS = [
    ("總覽", f"https://studio.youtube.com/channel/{CH}/analytics/tab-overview/period-default"),
    ("觸及", f"https://studio.youtube.com/channel/{CH}/analytics/tab-reach_viewers/period-default"),
    ("觀眾", f"https://studio.youtube.com/channel/{CH}/analytics/tab-build_audience/period-default"),
]

JUNK = ["資訊主頁", "內容", "數據分析", "社群", "字幕", "內容偵測", "營利", "自訂",
        "音樂庫", "設定", "提供意見", "略過導覽", "建立", "你的頻道", "Taco & Nova",
        "進階模式", "觀眾如何找到我的內容？", "我觸及了多少新觀眾？", "總結我最新影片的成效"]


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)


def ensure_edge():
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=4)
        return True
    except Exception:
        pass
    log("啟動遙控 Edge")
    subprocess.Popen([EDGE, "--remote-debugging-port=9222", f"--user-data-dir={PROFILE}",
                      "--no-first-run", "--window-position=2000,2000", "--window-size=1500,1100",
                      "https://studio.youtube.com"])
    for _ in range(20):
        time.sleep(3)
        try:
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=4)
            return True
        except Exception:
            continue
    return False


def scrape():
    from playwright.sync_api import sync_playwright
    chunks = []
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = b.contexts[0]
        page = next((p for p in ctx.pages if "studio.youtube.com" in p.url), None) or ctx.new_page()
        page.bring_to_front()
        for name, url in TABS:
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(16)
            txt = page.evaluate("() => document.body.innerText")
            lines = [l for l in txt.splitlines() if l.strip() and l.strip() not in JUNK]
            chunks.append(f"### {name}\n" + "\n".join(lines)[:5000])
            log(f"{name} 抓完")
    return "\n\n".join(chunks)


def main():
    stamp = datetime.now().strftime("%Y-%m-%d")
    raw_path = REPORTS / f"{stamp}-原始數據.txt"

    if not ensure_edge():
        log("FATAL: CDP 起不來")
        sys.exit(1)
    raw = scrape()
    raw_path.write_text(f"抓取時間：{datetime.now():%Y-%m-%d %H:%M}\n\n{raw}",
                        encoding="utf-8")
    log(f"原始數據 → {raw_path.name}")

    if "--raw" in sys.argv:
        return

    prev = sorted(REPORTS.glob("*-原始數據.txt"))
    prev_raw = ""
    if len(prev) >= 2:
        prev_raw = prev[-2].read_text(encoding="utf-8")[:6000]

    prompt = f"""下面是 Taco & Nova 頻道（AI 生成的吉娃娃×哈士奇搞笑 Shorts，日更三支）的 YouTube 後台數據。

**輸出規則（很重要，違反等於報告作廢）：**
- 只輸出報告本文，**第一個字就是報告的第一句**。不要開場白、不要說「報告寫好了」、不要說明你做了什麼、不要用「順帶一提」「用法提示」這類對話語句。
- **不要使用任何工具、不要讀取或寫入任何檔案**，你需要的資料全部在下方文字裡。呼叫你的腳本會負責存檔。
- 全文用**繁體中文**，markdown 格式，中英文之間加半形空格。

**報告要包含這五節：**

1. `## 一句話總結` — 三行以內講完今天最重要的變化。
2. `## 數字` — 一個表格：觀看、訂閱、平均觀看比例、最強的片。有昨天的數據就標出增減。
3. `## 該加強的地方` — 具體可執行。重點看：訂閱轉換率（觀看數 ÷ 新增訂閱）、回流觀眾比例、哪支片的表現明顯偏離平均（特別是「留存很高但觀看很低」＝曝光被吃掉，這種片值得重發）。
4. `## 題材判讀` — 哪個題材家族在贏，下一支該拍什麼方向。
5. `## 發布時段` — 只根據「觀眾使用 YouTube 的時段」那份報表講。**如果後台寫「資料不足」就直接說資料不足、這題無解**，絕對不要用地區或常識推論代替。

**誠實要求：** 數字看不出因果就明說看不出來。跑得差的片先分辨是「沒被推」還是「題材差」，不要把低曝光當成題材失敗。

--- 今天的數據 ---
{raw[:11000]}

--- 前一次的數據（沒有就是空的，那就別做比較） ---
{prev_raw}
"""
    pf = REPORTS / f"_prompt_{stamp}.txt"
    pf.write_text(prompt, encoding="utf-8")
    out_path = REPORTS / f"{stamp}-體檢報告.md"

    log("呼叫 claude 產生報告…")
    try:
        p = subprocess.run(
            [CLAUDE, "-p", prompt],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=900, cwd=str(PROJECT))
        body = (p.stdout or "").strip()
        if not body:
            body = "（claude 沒有輸出內容）\n\n" + (p.stderr or "")[:2000]
        out_path.write_text(f"# {stamp} Taco & Nova 每日體檢\n\n{body}\n", encoding="utf-8")
        log(f"報告 → {out_path.name}")
    except Exception as e:
        log(f"claude 呼叫失敗：{e}")
        out_path.write_text(f"# {stamp} 體檢（自動分析失敗）\n\n原始數據見 {raw_path.name}\n\n{e}\n",
                            encoding="utf-8")
    finally:
        pf.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
