# -*- coding: utf-8 -*-
"""說明文案的格式規格與檢查。

由來（2026-08-11 實測比對）：
兩支高流量片和兩支只有 50~60 觀看的片，說明文案結構差在這裡 ——

| 影片 | 第 2 條 | CTA |
|---|---|---|
| Big Dog Got The Tiny Bed（9,882） | 第三人稱劇情描述 ✅ | what would YOUR dog do? |
| Black Hole（5.1 萬）            | 第三人稱劇情描述 ✅ | what would YOUR dog do? |
| Day 2 巧克力（~50）              | 沒有 ❌            | 被改成別句 ❌ |
| Day 3 淹水（~60）                | 沒有 ❌（發布時被當成誤植刪掉） | what would YOUR dog do? |

那條第三人稱劇情描述**不是誤植，是設計**。Shorts 沒有旁白也沒有字幕，
那段文字是 YouTube 唯一讀得懂「這片在演什麼」的線索，拿掉等於讓演算法瞎著推。

所以把它變成發布前的硬性檢查，不要再靠人記得。

正確結構：

    official statement from Taco:
    1. <Taco 第一人稱耍賴> 💅
    2. <第三人稱劇情描述，說清楚畫面發生什麼事>
    3. <Taco 第一人稱耍賴>
    <關於 Nova 的一句話>
    what would YOUR dog do? 👇
    #Shorts #FunnyDogs #Chihuahua #Husky #DogComedy
"""

CTA = "what would YOUR dog do?"
TAGS = ["#Shorts", "#FunnyDogs", "#Chihuahua", "#Husky", "#DogComedy"]
# 第三人稱劇情描述會用到的主詞：講的是「畫面上發生什麼」而不是 Taco 在耍嘴皮
THIRD_PERSON = ["Taco ", "The chihuahua", "the chihuahua", "The husky", "the husky"]


def check(desc):
    """回傳 (是否合格, 問題清單)。"""
    problems = []
    lines = [ln.strip() for ln in desc.strip().splitlines() if ln.strip()]

    if not lines or not lines[0].lower().startswith("official statement from taco"):
        problems.append("第一行要是 `official statement from Taco:`")

    numbered = [ln for ln in lines if ln[:2] in ("1.", "2.", "3.")]
    if len(numbered) < 3:
        problems.append(f"要有 1./2./3. 三條，目前只有 {len(numbered)} 條")

    # 核心檢查：第 2 條必須是第三人稱劇情描述
    line2 = next((ln for ln in lines if ln.startswith("2.")), "")
    if line2:
        body = line2[2:].strip()
        if not any(body.startswith(p) for p in THIRD_PERSON):
            problems.append(
                "第 2 條必須是**第三人稱劇情描述**（用 Taco / The chihuahua / The husky 開頭，"
                "說清楚畫面發生什麼事）。這是兩支高流量片的共同特徵，"
                "也是演算法唯一讀得懂內容的線索 —— 不要換成 Taco 的第一人稱吐槽")
        elif len(body) < 60:
            problems.append(f"第 2 條的劇情描述太短（{len(body)} 字元），高流量版都在 90~130 字元")

    if CTA not in desc:
        problems.append(f"CTA 要用 `{CTA}`（低流量那支被改成別句了）")

    missing = [t for t in TAGS if t not in desc]
    if missing:
        problems.append(f"缺少標籤：{' '.join(missing)}")

    return (not problems), problems


if __name__ == "__main__":
    import sys
    ok, probs = check(open(sys.argv[1], encoding="utf-8").read())
    print("合格" if ok else "不合格：")
    for p in probs:
        print("  -", p)
    sys.exit(0 if ok else 1)
