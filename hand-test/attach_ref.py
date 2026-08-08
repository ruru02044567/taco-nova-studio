"""Attach a reference image in Gemini video mode.

The composer's image button is a wrapper: a JS el.click() does not reach the hidden
input, so drive it with a real mouse click on the button centre and catch the
file chooser. Usage: python attach_ref.py <image path>
"""
import sys
import time
from playwright.sync_api import sync_playwright

IMG = sys.argv[1]
SHOT = r"C:/Users/TUF Gaming/Desktop/我的專案/財富密碼/hand-test/attach_state.png"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = [p for p in browser.contexts[0].pages if "gemini.google.com" in p.url][0]
    page.bring_to_front()

    btn = page.locator("button[aria-label*='上傳檔案'], [role=button][aria-label*='上傳檔案']").first
    box = btn.bounding_box()
    print("button box:", box)
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2

    with page.expect_file_chooser(timeout=15000) as fc:
        page.mouse.click(cx, cy)
    fc.value.set_files(IMG)
    print("set_files done")

    time.sleep(8)
    page.screenshot(path=SHOT)
    print("attached:", IMG)
