# -*- coding: utf-8 -*-
"""把做好的頻道頭像與 banner 上傳到 YouTube（Studio → 自訂 → 個人資料）

用法：python upload_branding.py avatar   # 只傳頭像
      python upload_branding.py banner   # 只傳橫幅
"""
import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
CH = "UC4Bf0lB05GrYF8Q4l6NnjEA"
BASE = r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼"
FILES = {"avatar": BASE + r"\channel-avatar.png", "banner": BASE + r"\channel-banner.png"}
# 沒圖的時候按鈕寫「上傳」，已經有圖就變成「變更」—— 兩個都試
BTN = {"avatar": ["變更", "上傳"], "banner": ["變更", "上傳"]}
# 頭像是頁面上第 2 組按鈕（第 1 組是橫幅），banner 是第 1 組
NTH = {"avatar": 1, "banner": 0}

what = sys.argv[1] if len(sys.argv) > 1 else "avatar"


def real_click(page, text, nth=-1):
    """真實滑鼠點擊指定文字的元素（Studio 也是 JS click 不吃）"""
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
    p = pos[nth]
    page.mouse.click(p["x"], p["y"])
    return True


with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = b.contexts[0].new_page()
    page.goto(f"https://studio.youtube.com/channel/{CH}/editing/images",
              wait_until="domcontentloaded")
    time.sleep(18)

    with page.expect_file_chooser(timeout=25000) as fc:
        hit = False
        for word in BTN[what]:
            if real_click(page, word, NTH[what]):
                print(f"點了第 {NTH[what]+1} 顆「{word}」")
                hit = True
                break
        if not hit:
            print("找不到上傳/變更按鈕")
            sys.exit(1)
    fc.value.set_files(FILES[what])
    print(f"已選擇檔案：{FILES[what]}")
    time.sleep(8)

    page.screenshot(path=f"studio-{what}-1.png", full_page=True)
    # 裁切對話框通常有「完成」或「儲存」
    for word in ["完成", "儲存", "Done", "Save"]:
        if real_click(page, word, 0):
            print(f"按了「{word}」")
            break
    time.sleep(6)
    page.screenshot(path=f"studio-{what}-2.png", full_page=True)

    # 右上角「發布」才會真的套用
    if real_click(page, "發布", 0):
        print("按了「發布」")
    time.sleep(8)
    page.screenshot(path=f"studio-{what}-3.png", full_page=True)
    print("完成，看截圖確認")
