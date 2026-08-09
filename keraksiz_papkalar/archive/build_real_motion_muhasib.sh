#!/bin/bash
set -e

DIR="/Users/muhasibpro/Desktop/Geminisdk"
BRAIN_DIR="/Users/muhasibpro/.gemini/antigravity-cli/brain/ffc9d81c-210a-487f-a8b3-58cbaa94f45f"
OUT_MP4="$DIR/dokon_energetik_muhasib_v2.mp4"

echo "Building BRAND NEW Real Motion Animated Video..."

IMG1="$BRAIN_DIR/store_boy_energy_1785523842625.jpg"
IMG2="$BRAIN_DIR/cashier_checkout_counter_1785523856682.jpg"
IMG3="$BRAIN_DIR/boy_surprised_muhasib_1785523872823.jpg"
IMG4="$BRAIN_DIR/muhasib_pos_system_1785523886158.jpg"

# Scene 1: Boy walking into store holding energy drink (Cinematic walking pan)
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG1" -i "$DIR/audio_mix1.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.0035,1.25)':x='iw/2-(iw/zoom/2)+sin(time*3)*35':y='ih/2-(ih/zoom/2)+cos(time*2)*15':d=200:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc1_real_motion.mp4"

# Scene 2: Cashier checkout & energy drink (Smooth counter panning)
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG2" -i "$DIR/audio_mix2.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.0025,1.18)':x='iw/2-(iw/zoom/2)-sin(time*2.5)*25':y='ih/2-(ih/zoom/2)':d=200:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc2_real_motion.mp4"

# Scene 3: Boy surprised asking "Vay! Nega silarda MUHASIB dasturi yo'q?!" (Dynamic shock zoom)
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG3" -i "$DIR/audio_mix3.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(zoom+0.0075,1.35)':x='iw/2-(iw/zoom/2)+sin(time*5)*15':y='ih/3-(ih/zoom/3)':d=200:s=1920x1080" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc3_real_motion.mp4"

# Scene 4: MUHASIB POS Scanner Laser Beam & Futuristic Automation
/opt/homebrew/bin/ffmpeg -y -loop 1 -i "$IMG4" -i "$DIR/audio_mix4.m4a" \
  -vf "scale=1920:1080,zoompan=z='min(1.15,zoom+0.002)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=220:s=1920x1080,drawbox=x=0:y='ih/2+sin(t*5)*220':w=1920:h=10:color=red@0.9:t=fill" \
  -c:v libx264 -tune stillimage -c:a aac -shortest -pix_fmt yuv420p "$DIR/sc4_real_motion.mp4"

echo "Stitching video clips..."
cat << EOF > "$DIR/new_video_filelist.txt"
file 'sc1_real_motion.mp4'
file 'sc2_real_motion.mp4'
file 'sc3_real_motion.mp4'
file 'sc4_real_motion.mp4'
EOF

/opt/homebrew/bin/ffmpeg -y -f concat -safe 0 -i "$DIR/new_video_filelist.txt" -c copy "$OUT_MP4"

# Copy to artifact folder for web UI previewing
cp "$OUT_MP4" "$BRAIN_DIR/dokon_energetik_muhasib_v2.mp4"

echo "SUCCESS! Real motion animated video generated at: $OUT_MP4"
