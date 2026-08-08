"""Open the aspect-ratio dropdown in Gemini video mode and dump the options."""
import sys
import time
from playwright.sync_api import sync_playwright

SHOT = r"C:/Users/TUF Gaming/Desktop/我的專案/財富密碼/hand-test/ratio_state.png"
pick = sys.argv[1] if len(sys.argv) > 1 else None

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = [p for p in ctx.pages if "gemini.google.com" in p.url][0]
    page.bring_to_front()

    btn = page.locator("button[aria-label*='顯示比例'], [role=button][aria-label*='顯示比例']").first
    btn.evaluate("el => el.click()")
    time.sleep(2)

    for sel in ["[role=menuitem]", "[role=option]", "[role=menuitemradio]", "mat-option"]:
        for el in page.locator(sel).all():
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip().replace("\n", " ")[:40]
                lab = el.get_attribute("aria-label") or ""
                box = el.bounding_box() or {}
                print(f"{sel} ({int(box.get('x',0))},{int(box.get('y',0))}) label={lab!r} text={txt!r}")
            except Exception:
                pass

    if pick:
        target = page.get_by_text(pick, exact=False).last
        target.evaluate("el => el.click()")
        time.sleep(2)
        cur = page.locator("button[aria-label*='顯示比例'], [role=button][aria-label*='顯示比例']").first
        print("NOW:", cur.get_attribute("aria-label"))

    page.screenshot(path=SHOT)
    print("url:", page.url)
