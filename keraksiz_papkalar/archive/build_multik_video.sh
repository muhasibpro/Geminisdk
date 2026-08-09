#!/bin/bash
set -e

DIR="/Users/muhasibpro/Desktop/Geminisdk"
IMG_DIR="$DIR/images"
OUT_MP4="$DIR/muhasib_multik_video.mp4"

echo "Rendering individual video scenes..."
# Scene 1
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_1.jpg" -i "$DIR/a1.m4a" \
  -vf "scale=1920:1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/v1.mp4"

# Scene 2
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_2.jpg" -i "$DIR/a2.m4a" \
  -vf "scale=1920:1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/v2.mp4"

# Scene 3
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_3.jpg" -i "$DIR/a3.m4a" \
  -vf "scale=1920:1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/v3.mp4"

# Scene 4
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_4.jpg" -i "$DIR/a4.m4a" \
  -vf "scale=1920:1080" \
  -c:v libx264 -tune stillimage -c:a copy -shortest -pix_fmt yuv420p "$DIR/v4.mp4"

echo "Concatenating scenes into final MP4 video..."
cat << EOF > "$DIR/filelist.txt"
file 'v1.mp4'
file 'v2.mp4'
file 'v3.mp4'
file 'v4.mp4'
EOF

/opt/homebrew/bin/ffmpeg -y -f concat -safe 0 -i "$DIR/filelist.txt" -c copy "$OUT_MP4"

echo "Video successfully rendered: $OUT_MP4"
