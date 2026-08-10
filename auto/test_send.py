# -*- coding: utf-8 -*-
"""一步一步做完整流程，每一步截圖，看送出當下到底發生什麼"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
scene = "clips/d1s1_last.jpg"
prompt = open("clips/d1s1b_video.txt", encoding="utf-8").read().strip()


def shot(page, tag):
    page.screenshot(path=f"step-{tag}.png")
    st = page.evaluate("""() => ({
        box: (document.querySelector('div.ql-editor')||{}).innerText || '',
        aspect: !!document.querySelector("[aria-label*='顯示比例']"),
        vids: document.querySelectorAll('video').length,
        dl: !!document.querySelector("[aria-label*='下載']"),
        imgs: document.querySelectorAll('img').length
    })""")
    st["box"] = (st["box"] or "")[:40]
    print(f"  [{tag}] {st}", flush=True)


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = next((p for p in b.contexts[0].pages if "gemini.google.com" in p.url), None)
    page.bring_to_front()
    page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
    time.sleep(6)

    page.locator("[aria-label='影片']").first.click(timeout=8000)
    time.sleep(5)
    shot(page, "1-模式")

    # 切直向
    for _ in range(4):
        lbl = page.evaluate("""() => {const e=document.querySelector("[aria-label*='顯示比例']");return e?e.getAttribute('aria-label'):''}""") or ""
        if "直向" in lbl:
            break
        page.evaluate("""() => {const e=document.querySelector("[aria-label*='顯示比例']"); if(e) e.click();}""")
        time.sleep(2.5)
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('*')) {
                if (el.querySelector('*')) continue;
                const s=(el.innerText||'').trim();
                if (s==='直向 (9:16)'||s==='直向') { el.click(); return; }
            }
        }""")
        time.sleep(2.5)
    shot(page, "2-比例")

    # 掛圖
    cands = [c for c in page.locator("[aria-label^='上傳檔案']").all() if c.is_visible()]
    with page.expect_file_chooser(timeout=15000) as fc:
        cands[-1].click()
    fc.value.set_files(scene)
    time.sleep(8)
    shot(page, "3-掛圖")

    # 打字
    box = page.locator("div.ql-editor").first
    box.click()
    page.keyboard.insert_text(prompt[:5000])
    time.sleep(2)
    shot(page, "4-打字")

    # 送出
    page.keyboard.press("Enter")
    time.sleep(3)
    shot(page, "5-Enter後3秒")
    time.sleep(12)
    shot(page, "6-Enter後15秒")
    time.sleep(30)
    shot(page, "7-Enter後45秒")
