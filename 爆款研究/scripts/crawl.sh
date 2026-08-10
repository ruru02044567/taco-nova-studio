#!/bin/bash
# 爬 YouTube 按觀看數排序的短片，多語言多關鍵字
OUT="raw"
mkdir -p "$OUT"

KEYWORDS=(
# --- 貓 (優先) ---
"cat" "cats" "funny cat" "cute cat" "kitten" "cat shorts" "cat meme" "cat fail"
"talking cat" "orange cat" "cat vs dog" "angry cat" "cat asmr" "baby cat"
"猫" "貓" "고양이" "ねこ" "gato" "gatito" "chat drole" "katze" "बिल्ली" "قطة"
"cat funny video" "cat jump" "cat sleeping" "cat dance" "kucing"
# --- 狗 (優先) ---
"dog" "dogs" "funny dog" "cute dog" "puppy" "dog shorts" "dog meme" "dog fail"
"talking dog" "husky" "golden retriever" "corgi" "shiba inu" "german shepherd"
"犬" "狗" "강아지" "perro" "perrito" "hund" "chien" "कुत्ता" "كلب"
"dog funny video" "dog reaction" "smart dog" "anjing" "dog and baby"
# --- 其他動物 ---
"funny animals" "cute animals" "animal shorts" "monkey" "parrot" "bird funny"
"horse" "cow" "hamster" "rabbit" "bunny" "panda" "elephant" "lion" "tiger"
"snake" "duck" "goat" "pig" "squirrel" "fox" "owl" "penguin" "dolphin"
"animal rescue" "baby animals" "farm animals" "zoo animals" "動物" "동물"
)

i=0
total=${#KEYWORDS[@]}
for kw in "${KEYWORDS[@]}"; do
  i=$((i+1))
  safe=$(echo "$kw" | md5sum | cut -c1-10)
  f="$OUT/$safe.txt"
  [ -s "$f" ] && { echo "[$i/$total] skip $kw"; continue; }
  enc=$(python -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$kw")
  yt-dlp --flat-playlist --no-warnings --ignore-errors --playlist-end 120 \
    --print "%(view_count)s\t%(duration)s\t%(id)s\t%(channel)s\t%(title)s" \
    "https://www.youtube.com/results?search_query=${enc}&sp=CAMSAhgB" \
    > "$f" 2>/dev/null
  n=$(wc -l < "$f")
  echo "[$i/$total] $kw -> $n"
done
echo "DONE"
