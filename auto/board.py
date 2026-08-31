# -*- coding: utf-8 -*-
r"""TOCO 素材看板（2026-08-31 建立，賢賢要求「開在旁邊隨時看得到」）。

掃 character\ 與 待審核\ 與 auto\clips\ 底下的圖與影片，做成一頁網頁。
每 5 秒自動重新整理，所以新生成的東西會自己冒出來，不用手動重開。

用法：python auto\board.py        （開伺服器並自動開瀏覽器）
      python auto\board.py 8790   （指定埠號）
"""
import http.server, socketserver, os, sys, html, urllib.parse, threading, webbrowser, time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parent.parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8790

WATCH = [
    ('⭐ 吉娃娃素材庫（桌面）', Path.home() / 'Desktop' / '吉娃娃素材庫'),
    ('剛生成的素材', ROOT / 'character' / 'ref-batch'),
    ('角色定裝庫',   ROOT / 'character'),
    ('待審核影片',   ROOT / '待審核'),
    ('工作中',       ROOT / 'auto' / 'clips'),
]
IMG = {'.png', '.jpg', '.jpeg', '.webp'}
VID = {'.mp4', '.webm', '.mov'}


def collect():
    out = []
    for title, d in WATCH:
        if not d.exists():
            continue
        files = []
        for f in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime if x.is_file() else 0, reverse=True):
            if not f.is_file():
                continue
            e = f.suffix.lower()
            if e in IMG or e in VID:
                files.append((f, e in VID))
        if files:
            out.append((title, d, files[:24]))
    return out


class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == '/f':
            q = urllib.parse.parse_qs(p.query).get('p', [''])[0]
            fp = Path(urllib.parse.unquote(q))
            ok = False
            for _, d in WATCH:
                try:
                    fp.resolve().relative_to(d.resolve())
                    ok = True; break
                except Exception:
                    pass
            if not ok:
                self.send_error(403); return
            if not fp.is_file():
                self.send_error(404); return
            ct = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                  '.webp': 'image/webp', '.mp4': 'video/mp4', '.webm': 'video/webm',
                  '.mov': 'video/quicktime'}.get(fp.suffix.lower(), 'application/octet-stream')
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(page().encode('utf-8'))


def page():
    secs = []
    for title, d, files in collect():
        cards = []
        for f, isvid in files:
            src = '/f?p=' + urllib.parse.quote(str(f))
            age = time.time() - f.stat().st_mtime
            fresh = ' fresh' if age < 300 else ''
            when = ('%d 分前' % (age // 60)) if age < 3600 else time.strftime('%m-%d %H:%M', time.localtime(f.stat().st_mtime))
            media = ('<video src="%s" controls preload="metadata"></video>' % src) if isvid \
                else ('<img src="%s" loading="lazy">' % src)
            cards.append('<figure class="card%s">%s<figcaption><span class="n">%s</span>'
                         '<span class="t">%s</span></figcaption></figure>'
                         % (fresh, media, html.escape(f.name), when))
        try:
            shown = str(d.relative_to(ROOT))
        except Exception:
            shown = str(d)
        secs.append('<section><h2>%s <span class="path">%s</span></h2><div class="grid">%s</div></section>'
                    % (html.escape(title), html.escape(shown), ''.join(cards)))
    body = ''.join(secs) or '<p class="empty">還沒有素材。生成之後會自動出現在這裡。</p>'
    return TPL.replace('{{BODY}}', body).replace('{{TS}}', time.strftime('%H:%M:%S'))


TPL = '''<!doctype html><html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TOCO 素材看板</title>
<meta http-equiv="refresh" content="5">
<style>
:root{color-scheme:dark;--bg:#12151a;--sf:#191d24;--ln:#2b3039;--tx:#ece8e2;--mu:#948b82;--ac:#f5834b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
 font:14px/1.6 "IBM Plex Sans",-apple-system,"Noto Sans TC",sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--ln);
 padding:12px 18px;display:flex;align-items:baseline;gap:14px;z-index:9}
h1{font-size:16px;margin:0;font-weight:600}
.ts{font:11px "IBM Plex Mono",monospace;color:var(--mu)}
.wrap{padding:18px}
section{margin-bottom:30px}
h2{font-size:14px;margin:0 0 10px;font-weight:600;display:flex;align-items:baseline;gap:9px}
.path{font:10.5px "IBM Plex Mono",monospace;color:var(--mu);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
.card{margin:0;background:var(--sf);border:1px solid var(--ln);border-radius:4px;overflow:hidden}
.card.fresh{border-color:var(--ac);box-shadow:0 0 0 1px var(--ac)}
.card img,.card video{display:block;width:100%;height:250px;object-fit:contain;background:#0c0e12}
figcaption{padding:7px 9px;display:flex;flex-direction:column;gap:2px}
.n{font:10.5px "IBM Plex Mono",monospace;word-break:break-all;line-height:1.4}
.t{font-size:10.5px;color:var(--mu)}
.empty{color:var(--mu);padding:40px;text-align:center}
</style></head><body>
<header><h1>TOCO 素材看板</h1><span class="ts">每 5 秒自動更新 · {{TS}}</span></header>
<div class="wrap">{{BODY}}</div></body></html>'''


if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', PORT), H) as s:
        url = 'http://127.0.0.1:%d' % PORT
        print('[ok] 素材看板：%s' % url)
        print('     監看：' + '、'.join(t for t, _ in WATCH))
        print('     每 5 秒自動重新整理，新生成的圖／片會自己出現。Ctrl+C 結束。')
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            print('\n[ok] 看板已關閉')
