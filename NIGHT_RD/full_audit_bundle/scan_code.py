# -*- coding: utf-8 -*-
"""全域程式碼掃描（只讀）—— 產出 code_search_summary.json

原始版本用 Bash here-doc 內嵌在 PowerShell 裡，在 Windows PowerShell 5.1 無法執行，
改成獨立檔案並用參數傳入路徑。

另外排除 _trainlib（第三方 peft 套件原始碼，1300+ 個 .py），
否則它的 json.load / encoding='utf-8' 會淹沒專案本身的命中。

用法：python scan_code.py <root> <bundle>
"""
import json
import os
import pathlib
import re
import sys

PATTERNS = [
    r"PUBLISH_GATE",
    r"publish_video",
    r"pipeline\.py",
    r"state\.json",
    r"encoding\s*=\s*['\"]utf-8",
    r"utf-8-sig",
    r"json\.load",
    r"json\.dump",
    r"ConvertTo-Json",
    r"approved",
    r"published",
    r"awaiting_review",
    r"awaiting",
]

# 不掃的路徑片段：第三方套件、快取、版本控制，以及本工具自己的產出
# （不排除 full_audit_bundle 的話，複製進包裡的 .md 會被重複計入，
#   scan_code.py 本身也會因為內含這些 pattern 字串而命中每一項）
EXCLUDE = ("\\_trainlib\\", "\\node_modules\\", "\\.git\\", "\\__pycache__\\",
           "\\venv\\", "\\site-packages\\", "\\full_audit_bundle\\")

MAX_BYTES = 2_000_000   # 單檔超過 2 MB 不掃（避免大型 log 拖慢）


def scan_text(path):
    try:
        txt = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    return sorted({p for p in PATTERNS if re.search(p, txt, flags=re.IGNORECASE)})


def main():
    if len(sys.argv) < 3:
        print("用法：python scan_code.py <root> <bundle>")
        return 1
    root, bundle = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

    hits, skipped_big, scanned = [], [], 0
    for ext in (".py", ".md", ".txt"):
        for p in root.rglob("*" + ext):
            if not p.is_file():
                continue
            full = str(p)
            if any(x in full for x in EXCLUDE):
                continue
            if p.stat().st_size > MAX_BYTES:
                skipped_big.append(str(p.relative_to(root)))
                continue
            scanned += 1
            h = scan_text(p)
            if h:
                hits.append({"file": str(p.relative_to(root)), "hits": h})

    # 依命中數排序，最相關的排前面
    hits.sort(key=lambda d: (-len(d["hits"]), d["file"]))

    # 每個 pattern 命中了哪些檔，反向索引比較好查
    by_pattern = {}
    for h in hits:
        for pat in h["hits"]:
            by_pattern.setdefault(pat, []).append(h["file"])

    summary = {
        "root": str(root),
        "scanned_files": scanned,
        "files_with_hits": len(hits),
        "skipped_oversize": skipped_big,
        "excluded_path_fragments": list(EXCLUDE),
        "by_pattern_counts": {k: len(v) for k, v in sorted(by_pattern.items())},
        "by_pattern": by_pattern,
        "py_md_hits": hits,
    }

    out = bundle / "code_search_summary.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"掃描 {scanned} 個文字檔，{len(hits)} 個有命中")
    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
