# -*- coding: utf-8 -*-
"""抓 Sonniss GDC 音效包在 archive.org 的檔案清單，存成本機索引。

Sonniss 的授權：可商用、不用標註出處、永久。是這個專案音效的主力來源。
一次抓完索引，之後挑檔只查本機 JSON，不用一直打 API。
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
INDEX = HERE / "sonniss_index.json"

ITEMS = [
    "SonnissGameAudioGDC",
    "SonnissGameAudioGDCPart2",
    "SonnissGameAudioGDCPart3",
    "SonnissGameAudioGDCPart4",
    "SonnissGameAudioGDCPart6",
]


def fetch(item):
    url = f"https://archive.org/metadata/{item}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    server = data.get("server", "")
    d = data.get("dir", "")
    out = []
    for f in data.get("files", []):
        name = f.get("name", "")
        if not name.lower().endswith((".wav", ".flac", ".mp3")):
            continue
        out.append({
            "item": item,
            "name": name,
            "size": int(f.get("size", 0) or 0),
            "url": f"https://{server}{d}/{urllib.parse.quote(name)}",
        })
    return out


all_files = []
for it in ITEMS:
    try:
        got = fetch(it)
        all_files += got
        print(f"{it}: {len(got)} 個音檔")
    except Exception as e:
        print(f"{it}: 失敗 {str(e)[:80]}")

INDEX.write_text(json.dumps(all_files, ensure_ascii=False), encoding="utf-8")
print(f"\n總共 {len(all_files)} 個音檔，索引存到 {INDEX.name}")
