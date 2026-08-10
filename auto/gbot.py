"""Gemini 遙控小工具：連上專用 Edge 視窗（CDP 9222），依子命令操作。"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRATCH = Path(__file__).parent
SHOT = SCRATCH / "gemini_state.png"


def get_page(pw):
    import os
    site = os.environ.get("GBOT_SITE", "gemini.google.com")
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    for p in ctx.pages:
        if site in p.url:
            return p
    p = ctx.new_page()
    p.goto(f"https://{site}", wait_until="domcontentloaded")
    return p


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    with sync_playwright() as pw:
        page = get_page(pw)
        page.bring_to_front()

        if cmd == "shot":
            time.sleep(2)

        elif cmd == "send":
            text = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
            box = page.locator("div.ql-editor").first
            box.wait_for(state="visible", timeout=15000)
            box.click()
            page.keyboard.insert_text(text)
            time.sleep(1)
            page.keyboard.press("Enter")
            time.sleep(3)

        elif cmd == "wait":
            secs = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            time.sleep(secs)

        elif cmd == "imgs":
            imgs = page.locator("img").all()
            for i, im in enumerate(imgs):
                src = (im.get_attribute("src") or "")[:120]
                box = im.bounding_box()
                if box and box["width"] > 150:
                    print(i, int(box["width"]), "x", int(box["height"]), src)

        elif cmd == "saveimg":
            idx = int(sys.argv[2])
            out = Path(sys.argv[3])
            imgs = page.locator("img").all()
            im = imgs[idx]
            im.scroll_into_view_if_needed()
            time.sleep(1)
            im.screenshot(path=str(out))
            print("saved", out)

        elif cmd == "dismiss":
            btn = page.get_by_role("button", name="我知道了")
            if btn.count() > 0:
                btn.first.click(timeout=5000)
                print("dismissed")
            time.sleep(1)

        elif cmd == "grab":
            out = Path(sys.argv[2])
            cands = []
            for im in page.locator("img").all():
                src = im.get_attribute("src") or ""
                box = im.bounding_box()
                if box and box["width"] > 250 and ("googleusercontent" in src or src.startswith("blob:")):
                    cands.append(im)
            if not cands:
                print("NO IMAGE FOUND")
            else:
                im = cands[-1]
                im.scroll_into_view_if_needed()
                time.sleep(1)
                im.screenshot(path=str(out))
                print("saved", out, len(cands), "candidates on page")

        elif cmd == "buttons":
            for b in page.locator("button, [role=button]").all():
                try:
                    if not b.is_visible():
                        continue
                    label = b.get_attribute("aria-label") or ""
                    text = (b.inner_text() or "").strip().replace("\n", " ")[:40]
                    box = b.bounding_box() or {}
                    print(f"({int(box.get('x',0))},{int(box.get('y',0))}) label={label!r} text={text!r}")
                except Exception:
                    pass

        elif cmd == "clicklabel":
            target = sys.argv[2]
            page.locator(f"button[aria-label*='{target}'], [role=button][aria-label*='{target}']").first.click(timeout=8000)
            time.sleep(2)

        elif cmd == "clickjs":
            target = sys.argv[2]
            found = page.evaluate(
                """(t) => {
                    const all = document.querySelectorAll('button, a, [role=button], tp-yt-paper-button, ytd-button-renderer, yt-button-shape');
                    for (const el of all) {
                        const txt = (el.innerText || el.textContent || '').trim();
                        if (txt.includes(t)) { el.click(); return txt.slice(0, 60); }
                    }
                    return null;
                }""",
                target,
            )
            print("clicked:", found)
            time.sleep(3)

        elif cmd == "ytdetails":
            title = open(sys.argv[2], encoding="utf-8").read().strip()
            desc = open(sys.argv[3], encoding="utf-8").read().strip()
            tbox = page.get_by_role("textbox", name="新增可描述影片內容的標題").first
            dbox = page.get_by_role("textbox", name="向觀眾介紹你的影片").first
            tbox.fill(title)
            dbox.fill(desc)
            time.sleep(1)
            page.get_by_text("否，這不是兒童專屬的影片", exact=False).first.click()
            time.sleep(1)
            print("details filled:", title[:40])

        elif cmd == "ytupload":
            fpath = sys.argv[2]
            page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded")
            time.sleep(5)
            with page.expect_file_chooser(timeout=15000) as fc:
                page.get_by_text("選取檔案").first.click()
            fc.value.set_files(fpath)
            time.sleep(8)
            print("file selected")

        elif cmd == "fixchname":
            new_name = sys.argv[2]
            try:
                page.get_by_role("button", name="繼續").click(timeout=4000)
                time.sleep(2)
            except Exception:
                pass
            boxes = page.get_by_role("textbox").all()
            done = False
            for b in boxes:
                try:
                    val = b.input_value(timeout=2000)
                except Exception:
                    val = b.inner_text()
                if "mochiandboss" in (val or ""):
                    b.fill(new_name)
                    done = True
                    break
            print("name filled:", done)
            time.sleep(1)
            page.get_by_role("button", name="發布").click(timeout=8000)
            time.sleep(4)

        elif cmd == "createchannel":
            name, handle = sys.argv[2], sys.argv[3]
            inputs = [i for i in page.locator("input:visible").all()]
            print("visible inputs:", len(inputs))
            inputs[1].fill(name)
            inputs[2].fill(handle)
            time.sleep(1)
            for v in [i.input_value() for i in page.locator("input:visible").all()]:
                print("value:", v)
            page.get_by_role("button", name="建立頻道").click()
            time.sleep(6)

        elif cmd == "clickdeep":
            target = sys.argv[2]
            found = page.evaluate(
                """(t) => {
                    let best = null;
                    for (const el of document.querySelectorAll('*')) {
                        const txt = (el.textContent || '').trim();
                        if (txt.includes(t) && txt.length < t.length + 5) best = el;
                    }
                    if (best) { best.click(); return best.tagName + ': ' + best.textContent.trim().slice(0, 60); }
                    return null;
                }""",
                target,
            )
            print("clicked:", found)
            time.sleep(3)

        elif cmd == "getvideo":
            import base64
            out = Path(sys.argv[2])
            vids = page.locator("video").all()
            print("video elements:", len(vids))
            src = None
            for v in vids:
                src = v.get_attribute("src") or v.evaluate("el => el.currentSrc")
                if src:
                    break
            print("src:", (src or "NONE")[:150])
            if src and not src.startswith("blob:"):
                data_url = page.evaluate(
                    """async (src) => {
                        const r = await fetch(src);
                        const blob = await r.blob();
                        return await new Promise(res => {
                            const fr = new FileReader();
                            fr.onload = () => res(fr.result);
                            fr.readAsDataURL(blob);
                        });
                    }""",
                    src,
                )
                b64 = data_url.split(",", 1)[1]
                out.write_bytes(base64.b64decode(b64))
                print("saved", out, out.stat().st_size // 1024, "KB")
            elif src:
                print("BLOB SRC - need different approach")

        elif cmd == "goto":
            page.goto(sys.argv[2], wait_until="domcontentloaded")
            time.sleep(4)

        elif cmd == "new":
            page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
            time.sleep(3)

        elif cmd == "clicktext":
            page.get_by_text(sys.argv[2], exact=False).first.click(timeout=8000)
            time.sleep(2)

        elif cmd == "upload":
            fpath = sys.argv[2]
            # 注意：Google 會在 aria-label 後面加說明文字（如「上傳檔案. 文件、資料…」），
            # 所以用前綴比對，不能用完全相等
            btn = page.locator("[aria-label^='上傳檔案']").first
            with page.expect_file_chooser(timeout=10000) as fc:
                btn.evaluate("el => el.click()")
            fc.value.set_files(fpath)
            time.sleep(4)
            print("uploaded", fpath)

        elif cmd == "retry":
            btn = page.locator("button[aria-label='重做']").last
            btn.evaluate("el => el.click()")
            time.sleep(3)
            print("retried")

        elif cmd == "download":
            out = Path(sys.argv[2])
            btn = page.locator("button[aria-label='下載影片'], [role=button][aria-label='下載影片']").last
            with page.expect_download(timeout=60000) as dl:
                btn.evaluate("el => el.click()")
            dl.value.save_as(str(out))
            print("downloaded", out, out.stat().st_size // 1024, "KB")

        elif cmd == "grabcanvas":
            import base64
            out = Path(sys.argv[2])
            big = [im for im in page.locator("img").all()
                   if (im.bounding_box() or {"width": 0})["width"] > 250]
            if not big:
                print("NO BIG IMAGE")
            else:
                handle = big[-1].element_handle()
                data_url = page.evaluate(
                    """(img) => {
                        const c = document.createElement('canvas');
                        c.width = img.naturalWidth;
                        c.height = img.naturalHeight;
                        c.getContext('2d').drawImage(img, 0, 0);
                        return c.toDataURL('image/png');
                    }""",
                    handle,
                )
                b64 = data_url.split(",", 1)[1]
                out.write_bytes(base64.b64decode(b64))
                print("saved", out, len(b64) // 1024, "KB(base64)")

        elif cmd == "grabblob":
            import base64
            out = Path(sys.argv[2])
            srcs = [im.get_attribute("src") or "" for im in page.locator("img").all()]
            blobs = [s for s in srcs if s.startswith("blob:")]
            if not blobs:
                print("NO BLOB IMAGE")
            else:
                data_url = page.evaluate(
                    """async (src) => {
                        const r = await fetch(src);
                        const blob = await r.blob();
                        return await new Promise(res => {
                            const fr = new FileReader();
                            fr.onload = () => res(fr.result);
                            fr.readAsDataURL(blob);
                        });
                    }""",
                    blobs[-1],
                )
                b64 = data_url.split(",", 1)[1]
                out.write_bytes(base64.b64decode(b64))
                print("saved", out, len(b64) // 1024, "KB(base64)", len(blobs), "blobs")

        elif cmd == "click":
            x, y = int(sys.argv[2]), int(sys.argv[3])
            page.mouse.click(x, y)
            time.sleep(2)

        elif cmd == "key":
            page.keyboard.press(sys.argv[2])
            time.sleep(1)

        page.screenshot(path=str(SHOT))
        print("url:", page.url)


if __name__ == "__main__":
    main()
