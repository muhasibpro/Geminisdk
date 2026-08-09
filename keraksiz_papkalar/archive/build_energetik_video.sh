#!/bin/bash
set -e

DIR="/Users/muhasibpro/Desktop/Geminisdk"
IMG_DIR="$DIR/images"
OUT_MP4="$DIR/muhasib_energetik_real_video.mp4"

echo "Building High Quality Animated Energetik Video for MUHASIB..."

# Convert WAV sound FX to AAC audio mixes with speech (duration=first keeps full speech length)
/opt/homebrew/bin/ffmpeg -y -i "$DIR/real_s1.mp3" -i "$DIR/audio/bell.wav" -filter_complex "[0:a][1:a]amix=inputs=2:duration=first[aout]" -map "[aout]" -c:a aac "$DIR/audio_mix1.m4a"
/opt/homebrew/bin/ffmpeg -y -i "$DIR/real_s2.mp3" -i "$DIR/audio/cash.wav" -filter_complex "[0:a][1:a]amix=inputs=2:duration=first[aout]" -map "[aout]" -c:a aac "$DIR/audio_mix2.m4a"
/opt/homebrew/bin/ffmpeg -y -i "$DIR/real_s3.mp3" -i "$DIR/audio/shock.wav" -filter_complex "[0:a][1:a]amix=inputs=2:duration=first[aout]" -map "[aout]" -c:a aac "$DIR/audio_mix3.m4a"
/opt/homebrew/bin/ffmpeg -y -i "$DIR/real_s4.mp3" -i "$DIR/audio/beep.wav" -filter_complex "[0:a][1:a]amix=inputs=2:duration=first[aout]" -map "[aout]" -c:a aac "$DIR/audio_mix4.m4a"

# Render Scene 1: Walking into supermarket, picking Energetik drink (Panning motion)
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_1.jpg" -i "$DIR/audio_mix1.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.0025,1.18)':x='iw/2-(iw/zoom/2)+sin(time*2.5)*25':y='ih/2-(ih/zoom/2)':d=200:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc1_energetik.mp4"

# Render Scene 2: At Cashier Counter with energy drink
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_2.jpg" -i "$DIR/audio_mix2.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.002,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+cos(time*3)*15':d=200:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc2_energetik.mp4"

# Render Scene 3: Boy surprised asking "Vay! Nega silarda MUHASIB dasturi yo'q?!"
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_3.jpg" -i "$DIR/audio_mix3.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.004,1.3)':x='iw/2-(iw/zoom/2)+sin(time*5)*10':y='ih/3':d=200:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc3_energetik.mp4"

# Render Scene 4: MUHASIB POS Scanner Beam Animation
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG_DIR/scene_4.jpg" -i "$DIR/audio_mix4.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=220:s=1920x1080,drawbox=x=0:y='ih/2+sin(t*4)*200':w=1920:h=8:color=red@0.8:t=fill" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc4_energetik.mp4"

echo "Stitching final scenes into $OUT_MP4..."
cat << EOF > "$DIR/energetik_filelist.txt"
file 'sc1_energetik.mp4'
file 'sc2_energetik.mp4'
file 'sc3_energetik.mp4'
file 'sc4_energetik.mp4'
EOF

/opt/homebrew/bin/ffmpeg -y -f concat -safe 0 -i "$DIR/energetik_filelist.txt" -c copy "$OUT_MP4"

echo "MUHASIB Energetik Real Video successfully generated: $OUT_MP4"
