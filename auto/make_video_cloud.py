"""用 Gemini/Veo 生 10 秒直式影片（附場景圖鎖角色）。
用法：python make_video_cloud.py <scene.jpg> <prompt.txt> <out.mp4>
失敗（額度用完／服務不穩）回傳非 0，讓上層改走本機。
"""
import sys
import time

from playwright.sync_api import sync_playwright

from browser_lock import acquire

sys.stdout.reconfigure(encoding="utf-8")

acquire("make_video_cloud")      # 排程器和手動操作會搶同一個 Edge，先卡位再說

scene, prompt_file, out = sys.argv[1], sys.argv[2], sys.argv[3]
# 「|||」之後是本機分段用的，雲端只吃前半段
prompt = open(prompt_file, encoding="utf-8").read().split("|||")[0].strip()

# 額度用完：硬催沒用，要等台北 15:00 重置
# （Gemini 只會用英文講這幾句，之前沒收進來，一路被誤判成「逾時」）
QUOTA_MARKS = ["out of videos", "Upgrade to keep creating", "Videos are only free"]
# 服務端暫時抽風：8/10 實測隔幾分鐘重送就會過，不需要等一小時
BUSY_MARKS = ["發生錯誤", "getting a lot of requests", "請檢查你的網際網路連線",
              "something went wrong", "try again later"]
FAIL_MARKS = QUOTA_MARKS + BUSY_MARKS


def click_text(page, *texts):
    return page.evaluate(
        """(texts) => {
            const sel = 'button, [role=button], span, div, tp-yt-paper-item';
            for (const t of texts) {
                for (const el of document.querySelectorAll(sel)) {
                    const s = (el.innerText || '').trim();
                    if (s === t) {
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

    def real_click_text(text):
        """算出元素中心座標，用真實滑鼠點下去。
        Gemini 的選單項目和「提交」按鈕都不吃 JS 的 el.click()，一定要走這條。"""
        pos = page.evaluate("""(t) => {
            const hits = [];
            for (const el of document.querySelectorAll('*')) {
                if ((el.innerText || '').trim() !== t) continue;
                if (el.querySelector('*')) continue;          // 只要最內層那個節點
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) hits.push({x: r.x + r.width / 2, y: r.y + r.height / 2});
            }
            return hits.length ? hits[hits.length - 1] : null;
        }""", text)
        if not pos:
            return False
        page.mouse.click(pos["x"], pos["y"])
        return True

    # 開全新對話（殘留的舊對話會讓工具選單點不開）
    page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
    time.sleep(6)

    def video_mode_on():
        """影片模式真的啟用時，輸入框旁會出現「影片」這個 chip（它的按鈕是「取消選取『影片』」）。
        只看有沒有點到「建立影片」不準 —— 可能只是點到範本卡片，模式根本沒開，
        接著就會在切比例那關掛掉（找不到顯示比例按鈕）。"""
        return page.evaluate(
            """() => !!document.querySelector("[aria-label*='取消選取'][aria-label*='影片']")
                  || !!document.querySelector("[aria-label*='顯示比例']")""")

    def menu_has_item(text="建立影片"):
        """選單目前是不是開著（看得到那個項目）"""
        return page.evaluate("""(t) => {
            for (const el of document.querySelectorAll('*')) {
                if (el.querySelector('*')) continue;
                if ((el.innerText || '').trim() !== t) continue;
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) return true;
            }
            return false;
        }""", text)

    entered = False
    for attempt in range(4):
        if video_mode_on():
            entered = True
            print(f"video mode on (attempt {attempt + 1})")
            break

        # 正解：左側工具列那顆「影片」。實測只有它會真的啟用影片模式
        # （點下去「顯示比例」按鈕就出現了）。
        # 走「上傳與工具 → 建立影片」那條路點得到、也點得下去，但模式根本不會開，
        # 接著就會在切比例那關掛掉。而且「上傳與工具」是開關鍵，重試時多點一次反而把選單關掉。
        try:
            page.locator("[aria-label='影片']").first.click(timeout=8000)
            time.sleep(5)
        except Exception as e:
            print(f"  side rail attempt {attempt + 1}: {str(e)[:60]}")

        if video_mode_on():
            entered = True
            print(f"video mode entered via side rail (attempt {attempt + 1})")
            break

        # 備援：舊路線
        if not menu_has_item():
            try:
                page.locator("[aria-label*='上傳與工具']").first.click(timeout=10000)
                time.sleep(3)
            except Exception:
                page.reload(wait_until="domcontentloaded")
                time.sleep(8)
                continue
        if menu_has_item():
            real_click_text("建立影片")
        time.sleep(4)
        if video_mode_on():
            entered = True
            print(f"video mode entered (attempt {attempt + 1})")
            break
        print(f"  menu attempt {attempt + 1}: 模式沒開起來，重試")
        page.keyboard.press("Escape")
        time.sleep(2)
    if not entered:
        print("FAILED: 進不去建立影片模式")
        sys.exit(1)
    time.sleep(3)

    # 比例：每個新對話都會重設回橫向，一定要切。
    # 注意選單開合有延遲，且第一次點不一定生效 → 重試到 aria-label 真的變成直向為止
    def aspect():
        return page.evaluate(
            """() => {
                const el = document.querySelector("[aria-label*='顯示比例']");
                return el ? el.getAttribute('aria-label') : '';
            }"""
        ) or ""

    for attempt in range(4):
        if "直向" in aspect():
            break
        page.evaluate(
            """() => {
                const el = document.querySelector("[aria-label*='顯示比例']");
                if (el) el.click();
            }"""
        )
        time.sleep(2.5)
        click_text(page, "直向 (9:16)", "直向")
        time.sleep(2.5)
        print(f"  aspect attempt {attempt + 1}: {aspect()}")

    if "直向" not in aspect():
        print("FAILED: 比例切不到直向")
        sys.exit(1)
    print("aspect OK:", aspect())

    # 掛場景圖（注意：要抓「可見的」那顆上傳鈕，選單裡有同名隱藏鈕）
    cands = [c for c in page.locator("[aria-label^='上傳檔案']").all() if c.is_visible()]
    if not cands:
        print("FAILED: 找不到上傳按鈕")
        sys.exit(1)
    with page.expect_file_chooser(timeout=15000) as fc:
        cands[-1].click()
    fc.value.set_files(scene)

    # 參考圖一定要等它「真的」傳完才能送出。圖還在傳就送，整包會被靜靜吃掉：
    # 畫面退回範本頁、prompt 還原到輸入框、影片模式也掉，然後空等到逾時。
    #
    # 8/10 又踩一次：舊版寫死 sleep(10)，但那天的場景圖 226KB（以前成功的只有 122KB），
    # 10 秒不夠傳完 → 靜默還原。固定秒數是在賭網速，改成真的去確認附件掛上去了。
    # 判斷依據是實際傾印 DOM 找出來的（8/10）：附件掛上去之後，
    # 會出現一顆 aria-label='關閉附件' 的按鈕，外加一張 blob: 開頭的縮圖。
    # 注意不要拿 [role=progressbar] 當「還在傳」的依據 —— 這頁上永遠有一個，
    # 跟上傳無關，用它判斷會永遠回報「沒傳完」。
    def attached():
        return page.evaluate("""() => {
            if (document.querySelector("[aria-label='關閉附件']")) return true;
            return [...document.querySelectorAll('img')]
                   .some(i => (i.src || '').startsWith('blob:') && i.naturalWidth > 200);
        }""")

    for _ in range(30):                  # 最多等 60 秒
        time.sleep(2)
        if attached():
            break
    if not attached():
        print("FAILED: 場景圖沒掛上去（上傳沒完成，送出會被靜默吃掉）")
        sys.exit(3)
    time.sleep(3)                        # 掛上了再讓它喘一下
    print("scene attached")

    # 長 prompt：逐字打會逾時、塞 DOM 會被 TrustedHTML 擋且不觸發送出。
    # keyboard.insert_text 才會讓 Gemini 認得內容（跟 gbot send 同一套做法）
    box = page.locator("div.ql-editor").first
    box.wait_for(state="visible", timeout=15000)
    box.click()
    page.keyboard.insert_text(prompt[:5000])
    time.sleep(1.5)

    # 影片模式的 Enter 只是換行，不會送出 —— 要點右下角那顆「傳送訊息」。
    # 這裡踩過坑：腳本以為送出了，其實 prompt 一直躺在輸入框裡，然後等 8 分鐘逾時，
    # 上層就誤判成「Veo 額度掛掉」去退本機。
    def still_in_box():
        return len(page.evaluate(
            "() => document.querySelector('div.ql-editor')?.innerText || ''").strip()) > 50

    def page_error():
        """左下角那條錯誤 snackbar（例如「發生錯誤 (1155)」）。
        8/10 傍晚踩到：送出被服務端擋掉時，畫面表現跟「圖沒傳完被靜默還原」一模一樣
        ——都是退回歡迎頁、prompt 還原、影片模式掉。差別只有這條 snackbar。
        沒先問它就重送，等於對著壞掉的服務連撞三次。"""
        body = page.evaluate("() => document.body.innerText") or ""
        for m in FAIL_MARKS:
            if m in body:
                for line in body.splitlines():   # 整行撈出來才看得到錯誤碼
                    if m in line:
                        return line.strip()
                return m
        return ""

    def submit_visible():
        """純檢查，不可以有點擊副作用"""
        return page.evaluate("""() => {
            for (const el of document.querySelectorAll('button, [role=button]')) {
                const s = (el.innerText || '').trim();
                const r = el.getBoundingClientRect();
                if ((s === '提交' || s === 'Submit') && r.width > 0) return true;
            }
            return false;
        }""")

    # 影片模式真正的送出鍵是那顆黑色的「提交」，不是旁邊藍色的傳送箭頭。
    # 而且一定要用 Playwright 的真實滑鼠點擊 —— 用 JS 的 el.click() 這顆按鈕不吃，
    # 表面上沒事，實際上根本沒開始生成，然後等到 8 分鐘逾時被誤判成「額度用完」。
    def real_click_text(text):
        """算出元素中心座標，用真實滑鼠點下去。
        那顆「提交」不是 <button>、也沒有 aria-label，CSS 選擇器和 JS 的 el.click() 都抓不動它。"""
        pos = page.evaluate("""(t) => {
            const hits = [];
            for (const el of document.querySelectorAll('*')) {
                if ((el.innerText || '').trim() !== t) continue;
                if (el.querySelector('*')) continue;          // 只要最內層那個節點
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) hits.push({x: r.x + r.width / 2, y: r.y + r.height / 2});
            }
            return hits.length ? hits[hits.length - 1] : null;
        }""", text)
        if not pos:
            return False
        page.mouse.click(pos["x"], pos["y"])
        return True

    # 這裡是兩段式的：先按傳送，Gemini 才會冒出黑色的「提交」要你再確認一次，
    # 點了那顆才真的開始算圖。只按傳送的話畫面會安靜地退回範本頁，prompt 還原到輸入框，
    # 然後腳本就在那邊等 8 分鐘等到逾時 —— 被誤判成「Veo 額度掛掉」。
    # 送出順序：先 Enter（凌晨唯一成功那次就是這樣送的），再退而求其次點傳送鈕。
    # 之前以為 Enter 沒用，其實是那時候影片模式根本沒開，怎麼送都不會動。
    sent = False
    for attempt in range(3):
        if attempt == 0:
            page.keyboard.press("Enter")
        else:
            for sel in ["[aria-label='傳送訊息']", "[aria-label*='傳送']"]:
                try:
                    page.locator(sel).last.click(timeout=5000)
                    break
                except Exception:
                    continue
            else:
                page.keyboard.press("Enter")

        # 有些版面送出後會冒一顆「提交」要再確認一次；沒有就別空等，最多找 9 秒
        for _ in range(3):
            time.sleep(3)
            if submit_visible():
                real_click_text("提交") or real_click_text("Submit")
                print("  已按下「提交」")
                time.sleep(5)
                break
            if not still_in_box():      # 輸入框空了＝已經送出去了，不用再等
                break

        if not still_in_box() and not submit_visible():
            # 這裡不能就當作送出成功。8/10 實測：輸入框確實空了一瞬間，
            # 接著整頁靜靜退回歡迎畫面、prompt 被還原回框裡、影片模式也掉了，
            # 腳本毫無察覺，對著永遠不會出現的下載鈕等滿 20 分鐘。
            # 所以再等 20 秒回頭複驗一次：框還是空的、而且影片模式還在。
            time.sleep(20)
            # 8/10 傍晚逐秒錄下來的實測（veo_diag.py）：
            #   真的送出去 → box=0, 影片模式=1, 附件=1（圖跟著訊息留在對話裡）
            #   被靜默還原 → box 有字, 影片模式=1, 附件=0（模式還在！只有附件會掉）
            # 所以「影片模式還在」根本不能當成功判準，一路誤報成功。
            # 附件還在不在才是那個分得開的訊號。
            if still_in_box() or not video_mode_on() or not attached():
                err = page_error()
                if err:
                    # 服務端沒收單，重送幾次都一樣，直接收工讓上層去等或走備案
                    quota = any(m in err for m in QUOTA_MARKS)
                    print(f"FAILED: {'Veo 額度用完' if quota else 'Gemini 服務錯誤'} → {err}")
                    sys.exit(6 if quota else 5)
                print(f"  send attempt {attempt + 1}: 靜默還原了"
                      f"（框內有字={still_in_box()}, 影片模式={video_mode_on()}, "
                      f"附件={attached()}）")
                time.sleep(3)
                continue
            sent = True
            print(f"prompt sent (attempt {attempt + 1})")
            # 把對話網址留下來：等待期一斷線，veo_resume.py 才知道要接回哪一則。
            # 沒有它就只能翻歷史用猜的（8/10 傍晚就這樣弄丟過一輪）。
            print(f"conversation: {page.url}")
            try:
                open(out + ".conv", "w", encoding="utf-8").write(page.url)
            except Exception:
                pass
            break
        print(f"  send attempt {attempt + 1}: 還沒真的送出（框內有字={still_in_box()}, 提交鍵={submit_visible()}）")
        time.sleep(3)
    if not sent:
        # 三次都送不出去時，回頭再問一次服務端。額度用完那句英文提示是
        # 「最後一次送出之後」才浮出來的，前面每一輪檢查都還沒看到它，
        # 於是三次全被記成「靜默還原」，真正的原因（額度用完）被蓋掉。
        # 8/10 晚上就是這樣，產線對著已經沒額度的 Veo 空轉了一整晚。
        err = page_error()
        if err:
            quota = any(m in err for m in QUOTA_MARKS)
            print(f"FAILED: {'Veo 額度用完' if quota else 'Gemini 服務錯誤'} → {err}")
            sys.exit(6 if quota else 5)
        # 送出這關失敗時，場景圖和影片模式通常都已經掉了，光重送沒有用，
        # 要整條流程從新對話重來。用 exit 4 跟其他失敗區分開，讓上層知道可以直接重跑。
        print("FAILED: prompt 送不出去（場景圖／影片模式已掉，需要整條重跑）")
        sys.exit(4)
    time.sleep(3)

    # 8/10 實測：Veo 尖峰時段一支要跑超過 8 分鐘，舊的 8 分鐘上限會在它還在生的時候
    # 就判定失敗，然後重試又排一次隊 → 越重試越塞。改成 20 分鐘。
    for _ in range(120):             # 最多等 20 分鐘
        time.sleep(10)
        # 等待期間 Gemini 可能自己把頁面導走（8/10 傍晚實測：整頁被重設回 /app 首頁）。
        # 一導走 Playwright 的執行環境就沒了，evaluate 直接丟例外把腳本炸掉，
        # 連「失敗」都來不及印。包起來，當成一次失敗處理就好。
        try:
            body = page.evaluate("() => document.body.innerText")
        except Exception as e:
            print(f"FAILED: 頁面被導走／執行環境沒了 → {str(e)[:60]}")
            sys.exit(7)
        # 「額度用完」跟「服務抽風」以前混成同一句話印出來，上層只好一律等 1 小時。
        # 分開報，上層才能對症退避：抽風等幾分鐘，額度用完等重置。
        hit = next((m for m in QUOTA_MARKS if m in body), None)
        if hit:
            print(f"FAILED: Veo 額度用完 → {hit}")
            sys.exit(6)
        hit = next((m for m in BUSY_MARKS if m in body), None)
        if hit:
            print(f"FAILED: Veo 服務錯誤 → {hit}")
            sys.exit(5)
        try:
            has_dl = page.evaluate(
                """() => !!document.querySelector("[aria-label*='下載影片'], button[aria-label*='下載']")"""
            )
        except Exception as e:
            print(f"FAILED: 頁面被導走／執行環境沒了 → {str(e)[:60]}")
            sys.exit(7)
        if has_dl:
            break
    else:
        print("FAILED: 逾時")
        sys.exit(1)

    btn = page.locator("[aria-label*='下載影片']").last
    with page.expect_download(timeout=90000) as dl:
        btn.click()
    dl.value.save_as(out)
    print("saved", out)
