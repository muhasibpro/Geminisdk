#!/bin/bash
set -e

DIR="/Users/muhasibpro/Desktop/Geminisdk"
IMG_DIR="$DIR/images"
OUT_MP4="$DIR/muhasib_animated_multik.mp4"

echo "Generating Uzbek character voiceovers..."
# Uzbek speech text
say -v "Daniel" -o "$DIR/uz_s1.aiff" "Bir bola do'konga kiradi va o'ziga kerakli mahsulotlarni sotib oladi."
say -v "Grandma" -o "$DIR/uz_s2.aiff" "Kassaga kelganida, sotuvchi faqat narxini og'zaki aytadi."
say -v "Daniel" -o "$DIR/uz_s3.aiff" "Nega sizda Muhasib dasturi o'rnatilmagan?"
say -v "Daniel" -o "$DIR/uz_s4.aiff" "Muhasib dasturi bilan tezkor skanerlash va zamonaviy hisob-kitob!"

/opt/homebrew/bin/ffmpeg -y -i "$DIR/uz_s1.aiff" -acodec aac "$DIR/uz1.m4a"
/opt/homebrew/bin/ffmpeg -y -i "$DIR/uz_s2.aiff" -acodec aac "$DIR/uz2.m4a"
/opt/homebrew/bin/ffmpeg -y -i "$DIR/uz_s3.aiff" -acodec aac "$DIR/uz3.m4a"
/opt/homebrew/bin/ffmpeg -y -i "$DIR/uz_s4.aiff" -acodec aac "$DIR/uz4.m4a"

echo "Creating animated video scenes with motion filters..."

# Scene 1 Animation: Pan & zoom walking motion
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_1.jpg" -i "$DIR/uz1.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.002,1.12)':x='iw/2-(iw/zoom/2)+sin(time*2)*20':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/anim1.mp4"

# Scene 2 Animation: Pan & zoom typing motion
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_2.jpg" -i "$DIR/uz2.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.002,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+cos(time*3)*15':d=150:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/anim2.mp4"

# Scene 3 Animation: Close-up zoom with question focus
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_3.jpg" -i "$DIR/uz3.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.003,1.25)':x='iw/3':y='ih/3':d=150:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/anim3.mp4"

# Scene 4 Animation: Dynamic scanner beam glow motion
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_4.jpg" -i "$DIR/uz4.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(1.1,zoom+0.001)':x='iw/2-(iw/zoom/2)+sin(time*4)*10':y='ih/2-(ih/zoom/2)':d=180:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/anim4.mp4"

echo "Stitching full animated movie..."
cat << EOF > "$DIR/anim_filelist.txt"
file 'anim1.mp4'
file 'anim2.mp4'
file 'anim3.mp4'
file 'anim4.mp4'
EOF

/opt/homebrew/bin/ffmpeg -y -f concat -safe 0 -i "$DIR/anim_filelist.txt" -c copy "$OUT_MP4"

echo "Animated movie complete: $OUT_MP4"
