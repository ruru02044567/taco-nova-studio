# -*- coding: utf-8 -*-
"""合併正確標題 → 重新分類 → 輸出最終資料"""
import json, re
from collections import Counter

shorts = json.load(open("shorts_final.json", encoding="utf-8"))
oe = json.load(open("oembed.json", encoding="utf-8"))

for s in shorts:
    d = oe.get(s["id"])
    if d:
        s["title"] = d["title"]
        s["channel"] = d["channel"]
        s["channel_url"] = d.get("channel_url", "")
        s["ok"] = True
    else:
        s["ok"] = False   # 標題可能仍是亂碼（影片已下架）

CAT = (r"\bcat\b|\bcats\b|kitten|kitty|\bmeow\b|catlover|猫|貓|喵|gato|gatto|katze|chaton|고양이|"
       r"ねこ|ニャン|ネコ|kucing|قطة|बिल्ली|mèo|кот|feline|pussycat|미유")
DOG = (r"\bdog\b|\bdogs\b|puppy|puppies|doggo|\bpup\b|husky|corgi|shiba|retriever|poodle|chihuahua|"
       r"dachshund|labrador|pitbull|bulldog|beagle|samoyed|pomeranian|malinois|狗|犬|汪|perro|perrito|"
       r"hund|chien|강아지|멍멍|anjing|كلب|कुत्ता|chó|собак|doggy|pooch")
ANIM = (r"tom and jerry|tom  jerry|tom & jerry|talking tom|cartoon|animation|animated|cocomelon|"
        r"nursery rhyme|kids song|kidssong|\bcgi\b|blender|3d animation|pixar|minecraft|roblox|"
        r"animasi|мультик|#anime|ai animation|aicat|ai cat story|drawing|how to draw|mascot costume")
OTHER = [
    ("猴子", r"monkey|\bape\b|chimp|gorilla|langur|bandar|猴|원숭이|\bmono\b|macaque"),
    ("鳥類", r"\bbird\b|parrot|owl\b|eagle|duck|chicken|\bhen\b|鳥|鸟|\b새\b|pájaro|papagai|budgie|"
              r"penguin|peacock|crow|pigeon|goose|swan|ostrich|鴨|雞"),
    ("馬", r"horse|pony|馬|\b말\b|caballo|stallion"),
    ("牛羊豬/農場", r"\bcow\b|buffalo|goat|sheep|\bpig\b|piglet|donkey|bull\b|calf|牛|羊|豬|猪|\b소\b|"
                r"vaca|cabra|cerdo|farm animal|farmer"),
    ("兔鼠倉鼠", r"hamster|rabbit|bunny|squirrel|guinea pig|\brat\b|mouse|chipmunk|sugar glider|"
              r"兔|鼠|토끼|conejo|栗鼠"),
    ("野生動物", r"lion|tiger|bear\b|elephant|panda|\bfox\b|wolf|deer|leopard|cheetah|giraffe|zebra|"
               r"hippo|rhino|kangaroo|koala|sloth|raccoon|獅|虎|熊|象|貓熊|사자|호랑이|wildlife"),
    ("爬蟲/海洋", r"snake|lizard|croc|turtle|tortoise|shark|\bfish\b|dolphin|whale|octopus|jellyfish|"
                r"seal\b|otter|frog|dinosaur|蛇|魚|龜|물고기|鯊"),
    ("昆蟲蜘蛛", r"spider|\bant\b|\bants\b|\bbee\b|butterfly|insect|\bbug\b|scorpion|蜘蛛|蟲|昆虫|螞蟻"),
]

def blob(r):
    return (r.get("title", "") + " " + r.get("channel", "")).lower()

def classify(r):
    t = blob(r)
    c = bool(re.search(CAT, t, re.I))
    d = bool(re.search(DOG, t, re.I))
    if re.search(ANIM, t, re.I) and not (c or d):
        return "動畫/非真動物"
    if re.search(ANIM, t, re.I) and (c or d):
        return "動畫/非真動物"
    if c and d:
        return "貓狗同框"
    if c:
        return "貓"
    if d:
        return "狗"
    for name, pat in OTHER:
        if re.search(pat, t, re.I):
            return f"其他-{name}"
    return "未分類"

for s in shorts:
    s["cls"] = classify(s)

shorts.sort(key=lambda r: -r["views"])
json.dump(shorts, open("final.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

cnt = Counter(s["cls"] for s in shorts)
print(f"總計 {len(shorts)} 支真 Shorts (>=5000萬觀看)\n")
for k, v in cnt.most_common():
    print(f"  {k:18} {v:4}")

print("\n" + "=" * 70)
for cls in ["貓", "狗", "貓狗同框"]:
    sub = [s for s in shorts if s["cls"] == cls]
    print(f"\n### {cls}（{len(sub)} 支）TOP 20")
    for s in sub[:20]:
        print(f'{s["views"]/1e6:8.1f}M {s["dur"]:>3}s | {s["channel"][:20]:20} | {s["title"][:56]}')

print(f"\n### 未分類（{cnt['未分類']} 支）全列")
for s in [s for s in shorts if s["cls"] == "未分類"]:
    print(f'{s["views"]/1e6:8.1f}M {s["dur"]:>3}s | {s["channel"][:20]:20} | {s["title"][:56]}')
