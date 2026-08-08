"""Select 直向 (9:16) in the already-open aspect-ratio dropdown (reopens it if closed)."""
import time
from playwright.sync_api import sync_playwright

SHOT = r"C:/Users/TUF Gaming/Desktop/我的專案/財富密碼/hand-test/ratio_state.png"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = [p for p in browser.contexts[0].pages if "gemini.google.com" in p.url][0]
    page.bring_to_front()

    opt = page.locator("[role=menuitemradio][aria-label*='直向']")
    if opt.count() == 0 or not opt.first.is_visible():
        btn = page.locator("button[aria-label*='顯示比例'], [role=button][aria-label*='顯示比例']").first
        btn.evaluate("el => el.click()")
        time.sleep(2)
        opt = page.locator("[role=menuitemradio][aria-label*='直向']")

    opt.first.evaluate("el => el.click()")
    time.sleep(2)

    cur = page.locator("button[aria-label*='顯示比例'], [role=button][aria-label*='顯示比例']").first
    print("ASPECT NOW:", cur.get_attribute("aria-label"))
    page.screenshot(path=SHOT)
