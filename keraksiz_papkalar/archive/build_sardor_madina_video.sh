#!/bin/bash
set -e

DIR="/Users/muhasibpro/Desktop/Geminisdk"
IMG_DIR="$DIR/images"
OUT_MP4="$DIR/muhasib_sardor_madina_multik.mp4"

echo "Rendering individual video scenes with Sardor and Madina Neural Uzbek voices..."

# Scene 1: Madina Voice
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_1.jpg" -i "$DIR/real_s1.mp3" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.002,1.15)':x='iw/2-(iw/zoom/2)+sin(time*2)*15':y='ih/2-(ih/zoom/2)':d=160:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/s1_sm.mp4"

# Scene 2: Madina Voice (Cashier)
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_2.jpg" -i "$DIR/real_s2.mp3" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.002,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+cos(time*2.5)*12':d=160:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/s2_sm.mp4"

# Scene 3: Sardor Voice (Boy's Question)
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_3.jpg" -i "$DIR/real_s3.mp3" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.003,1.25)':x='iw/3':y='ih/3':d=160:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/s3_sm.mp4"

# Scene 4: Sardor Voice (MUHASIB POS System)
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_4.jpg" -i "$DIR/real_s4.mp3" \
  -vf "scale=1920:1080,zoompan=z='min(1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)+sin(time*3)*12':y='ih/2-(ih/zoom/2)':d=180:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/s4_sm.mp4"

echo "Stitching final Sardor & Madina MP4 cartoon..."
cat << EOF > "$DIR/sm_filelist.txt"
file 's1_sm.mp4'
file 's2_sm.mp4'
file 's3_sm.mp4'
file 's4_sm.mp4'
EOF

/opt/homebrew/bin/ffmpeg -y -f concat -safe 0 -i "$DIR/sm_filelist.txt" -c copy "$OUT_MP4"

echo "Sardor & Madina MP4 Video successfully generated: $OUT_MP4"
