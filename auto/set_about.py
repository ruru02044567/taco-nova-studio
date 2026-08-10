# -*- coding: utf-8 -*-
"""填寫 YouTube 頻道自介（Studio → 自訂 → 個人資料 → 說明）"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
CH = "UC4Bf0lB05GrYF8Q4l6NnjEA"

# emoji 刻意避開對標 Tim and Jeffy 用過的 🐾 ✅ 👬 😈 🐕
ABOUT = """💥 Daily shorts starring Taco & Nova

😏 Taco — a 2kg white chihuahua with two black dot eyebrows, zero shame and a plan
🥱 Nova — the husky who stopped trying to stop him

📅 New episode every single day
🎨 Original characters, original stories

Business enquiries: tacoandnova@gmail.com"""


def real_click(page, text, nth=0):
    pos = page.evaluate("""(t) => {
        const hits = [];
        for (const el of document.querySelectorAll('*')) {
            if (el.querySelector('*')) continue;
            if ((el.innerText || '').trim() !== t) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) hits.push({x: r.x + r.width/2, y: r.y + r.height/2});
        }
        return hits;
    }""", text)
    if not pos:
        return False
    page.mouse.click(pos[nth]["x"], pos[nth]["y"])
    return True


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = b.contexts[0].new_page()
    page.goto(f"https://studio.youtube.com/channel/{CH}/editing/images", wait_until="domcontentloaded")
    time.sleep(18)

    # 說明欄在名稱、帳號代碼下面，要捲下去
    for _ in range(5):
        page.mouse.wheel(0, 500)
        time.sleep(1.5)

    boxes = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('textarea, [contenteditable=true]').forEach((el, i) => {
            const r = el.getBoundingClientRect();
            out.push({i, tag: el.tagName, ph: el.getAttribute('aria-label') || el.getAttribute('placeholder') || '',
                      val: (el.value || el.innerText || '').slice(0, 60), w: Math.round(r.width), h: Math.round(r.height)});
        });
        return out;
    }""")
    print("找到的輸入框：")
    for x in boxes:
        print("  ", x)

    # 說明欄是最大的那個多行輸入框
    target = max([x for x in boxes if x["h"] > 40], key=lambda x: x["h"] * x["w"], default=None)
    if not target:
        print("找不到說明欄")
        page.screenshot(path="studio-about-fail.png", full_page=True)
        sys.exit(1)
    print(f"\n選定第 {target['i']} 個（{target['tag']}, {target['w']}x{target['h']}）")

    el = page.locator("textarea, [contenteditable=true]").nth(target["i"])
    el.click()
    time.sleep(1)
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    time.sleep(0.5)
    page.keyboard.insert_text(ABOUT)
    time.sleep(2)
    page.screenshot(path="studio-about-1.png", full_page=True)

    if real_click(page, "發布", 0):
        print("按了「發布」")
    time.sleep(8)
    page.screenshot(path="studio-about-2.png", full_page=True)
    print("完成，看截圖確認")
