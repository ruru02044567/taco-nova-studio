"""送出那一刻到底發生什麼事 —— 逐秒錄影版診斷。

背景（8/10 傍晚）：make_video_cloud.py 兩種死法長得一模一樣，
都是「退回範本頁 + prompt 還原」，但根因完全不同：
  A. Gemini 服務端錯誤（左下角 snackbar「發生錯誤 (1155)」）→ 重送無效，要等
  B. 額度用完（英文 snackbar，例如 out of videos）→ 今天別再試了
  C. 真的只是 UI 沒點到 → 重送有效
snackbar 只出現幾秒就消失，事後截圖永遠看不到，所以要在送出當下逐秒錄。

用法：python veo_diag.py <scene.jpg> <prompt.txt>
只跑到「送出後 60 秒」為止，不等生成、不下載。
"""
import sys
import time

from playwright.sync_api import sync_playwright

scene, prompt_file = sys.argv[1], sys.argv[2]
prompt = open(prompt_file, encoding="utf-8").read().split("|||")[0].strip()

# 出現這些字就是服務端在講話（不是我們點錯）
NOISE = ["發生錯誤", "getting a lot of requests", "請檢查你的網際網路連線",
         "something went wrong", "try again later", "out of videos",
         "Upgrade to keep creating", "Videos are only free", "額度", "上限",
         "限制", "稍後再試", "無法", "失敗"]


def click_text(page, *texts):
    return page.evaluate(
        """(texts) => {
            const sel = 'button, [role=button], span, div, tp-yt-paper-item';
            for (const t of texts) {
                for (const el of document.querySelectorAll(sel)) {
                    if ((el.innerText || '').trim() === t) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) { el.click(); return t; }
                    }
                }
            }
            return null;
        }""",
        list(texts),
    )


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    page = next((p for p in ctx.pages if "gemini.google.com" in p.url), None) or ctx.new_page()
    page.bring_to_front()

    page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
    time.sleep(6)

    def video_mode_on():
        return page.evaluate(
            """() => !!document.querySelector("[aria-label*='取消選取'][aria-label*='影片']")
                  || !!document.querySelector("[aria-label*='顯示比例']")""")

    def aspect():
        return page.evaluate(
            """() => {
                const el = document.querySelector("[aria-label*='顯示比例']");
                return el ? el.getAttribute('aria-label') : '';
            }""") or ""

    def attached():
        return page.evaluate("""() => {
            if (document.querySelector("[aria-label='關閉附件']")) return true;
            return [...document.querySelectorAll('img')]
                   .some(i => (i.src || '').startsWith('blob:') && i.naturalWidth > 200);
        }""")

    def box_len():
        return len(page.evaluate(
            "() => document.querySelector('div.ql-editor')?.innerText || ''").strip())

    def noise():
        """撈出服務端訊息那一整行（含錯誤碼）"""
        body = page.evaluate("() => document.body.innerText") or ""
        hits = []
        for line in body.splitlines():
            s = line.strip()
            if not s or len(s) > 120:
                continue
            if any(m in s for m in NOISE):
                hits.append(s)
        return hits

    # --- 進影片模式 ---
    for _ in range(4):
        if video_mode_on():
            break
        try:
            page.locator("[aria-label='影片']").first.click(timeout=8000)
            time.sleep(5)
        except Exception as e:
            print("side rail:", str(e)[:60])
    print("video mode:", video_mode_on())

    # --- 切直向 ---
    for _ in range(4):
        if "直向" in aspect():
            break
        page.evaluate("""() => {
            const el = document.querySelector("[aria-label*='顯示比例']");
            if (el) el.click();
        }""")
        time.sleep(2.5)
        click_text(page, "直向 (9:16)", "直向")
        time.sleep(2.5)
    print("aspect:", aspect())

    # --- 掛圖 ---
    cands = [c for c in page.locator("[aria-label^='上傳檔案']").all() if c.is_visible()]
    if not cands:
        print("FATAL: 找不到上傳鈕")
        sys.exit(1)
    with page.expect_file_chooser(timeout=15000) as fc:
        cands[-1].click()
    fc.value.set_files(scene)
    for _ in range(30):
        time.sleep(2)
        if attached():
            break
    print("attached:", attached())
    time.sleep(3)

    # --- 打字 ---
    box = page.locator("div.ql-editor").first
    box.wait_for(state="visible", timeout=15000)
    box.click()
    page.keyboard.insert_text(prompt[:5000])
    time.sleep(1.5)
    print("box_len before send:", box_len())

    # --- 送出，然後逐秒錄 60 秒 ---
    print(">>> Enter")
    page.keyboard.press("Enter")

    seen = set()
    for t in range(60):
        time.sleep(1)
        try:
            row = (f"t={t + 1:02d} box={box_len():4d} mode={int(video_mode_on())} "
                   f"att={int(attached())} url={page.url.split('/')[-1][:16]}")
            subm = page.evaluate("""() => {
                for (const el of document.querySelectorAll('button, [role=button]')) {
                    const s = (el.innerText || '').trim();
                    if ((s === '提交' || s === 'Submit') && el.getBoundingClientRect().width > 0) return true;
                }
                return false;
            }""")
            vids = page.evaluate("() => document.querySelectorAll('video').length")
            dl = page.evaluate(
                """() => !!document.querySelector("[aria-label*='下載影片'], button[aria-label*='下載']")""")
            row += f" submit={int(subm)} video={vids} dl={int(dl)}"
            for n in noise():
                if n not in seen:
                    seen.add(n)
                    row += f"  ⚠ {n}"
            print(row)
        except Exception as e:
            print(f"t={t + 1:02d} 讀取失敗 {str(e)[:50]}")

    print("--- 服務端講過的話 ---")
    for s in seen:
        print(" ", s)
    if not seen:
        print("  （沒有任何錯誤訊息）")
    page.screenshot(path="veo_diag_end.png")
    print("截圖 veo_diag_end.png")
