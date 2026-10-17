#!/bin/zsh
# สร้างปก TikTok แบบ A จากเฟรมในคลิป
#   make_cover.sh <video> <seconds> "<บรรทัดบน>" "<บรรทัดล่าง>" "<ประโยคไทย>" <out.png>
# ตัวอย่าง:
#   make_cover.sh IMG_7204.mov 0.8 "FIREMAPLE" "TROPIC 2" "เต็นท์ 2 คน ไม่เกิน 2 กก." 1017_cover_A.png
# ต้องมี ffmpeg และ Google Chrome (ใช้ headless เรนเดอร์ฟอนต์ไทยได้ถูกต้อง)
set -e
video=$1; sec=$2; l1=$3; l2=$4; sub=$5; out=$6
here=${0:A:h}
tmp=$(mktemp -d)
ffmpeg -v error -y -ss "$sec" -i "$video" -frames:v 1 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" -q:v 2 "$tmp/bg.jpg"
cp "$here/cover_A.html" "$tmp/cover.html"
enc() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"; }
url="file://$tmp/cover.html?bg=bg.jpg&l1=$(enc "$l1")&l2=$(enc "$l2")&sub=$(enc "$sub")"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --allow-file-access-from-files --virtual-time-budget=6000 \
  --window-size=1080,1920 --screenshot="$out" "$url" >/dev/null 2>&1
rm -rf "$tmp"
echo "cover -> $out"
