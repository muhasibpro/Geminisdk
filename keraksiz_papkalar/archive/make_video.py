#!/usr/bin/python3
"""
MUHASIB Video Creator Engine
Generates HD MP4 Animated Videos with Neural Uzbek Voiceovers & HD Visual Scenes.
"""

import sys
import os
import argparse
import asyncio
from PIL import Image, ImageDraw, ImageFont
import subprocess

DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG = "/opt/homebrew/bin/ffmpeg" if os.path.exists("/opt/homebrew/bin/ffmpeg") else "ffmpeg"

DEFAULT_SCENES = [
    {
        "title": "1. Do'konga tashrif",
        "text": "Quvnoq xaridor do'konga kirib, o'ziga kerakli sifatli mahsulotlarni tanlamoqda.",
        "voice": "uz-UZ-MadinaNeural",
        "bg_color": (30, 41, 59),       # Dark Slate
        "accent_color": (59, 130, 246)    # Blue
    },
    {
        "title": "2. Kassa va An'anaviy Hisob",
        "text": "Kassir barcha mahsulotlarni hisoblab, umumiy summani aytmoqda: 45000 so'm.",
        "voice": "uz-UZ-MadinaNeural",
        "bg_color": (15, 23, 42),       # Darker Slate
        "accent_color": (236, 72, 153)    # Pink
    },
    {
        "title": "3. Zamonaviy Tizim Savoli",
        "text": "Nega sizda hali ham aqlli Muhasib POS dasturi o'rnatilmagan?",
        "voice": "uz-UZ-SardorNeural",
        "bg_color": (24, 24, 27),       # Zinc Dark
        "accent_color": (234, 179, 8)     # Yellow
    },
    {
        "title": "4. MUHASIB bilan Tezkor Ish",
        "text": "Muhasib dasturi o'rnatildi! Endi 1 soniyada skanerlash, aniq hisob va tezkor kassa!",
        "voice": "uz-UZ-SardorNeural",
        "bg_color": (6, 78, 59),        # Emerald Green
        "accent_color": (34, 197, 94)     # Bright Green
    }
]

def create_scene_image(scene, out_img_path, width=1920, height=1080):
    img = Image.new("RGB", (width, height), scene.get("bg_color", (15, 23, 42)))
    draw = ImageDraw.Draw(img)

    # Decorative gradient circle / card
    accent = scene.get("accent_color", (59, 130, 246))
    draw.rounded_rectangle([100, 100, width-100, height-100], radius=40, outline=accent, width=4)
    draw.rounded_rectangle([120, 120, width-120, 260], radius=20, fill=accent)

    # Try loading default fonts
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        body_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        badge_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        badge_font = ImageFont.load_default()

    # Header title
    title_text = scene.get("title", "Video Sahna")
    draw.text((160, 160), title_text, fill=(255, 255, 255), font=title_font)

    # Subtitle / Voice Text
    body_text = scene.get("text", "")
    
    # Word wrap body text
    words = body_text.split()
    lines = []
    curr = ""
    for w in words:
        if len(curr + " " + w) > 42:
            lines.append(curr)
            curr = w
        else:
            curr = (curr + " " + w).strip()
    if curr:
        lines.append(curr)

    y_start = 360
    for line in lines:
        draw.text((160, y_start), line, fill=(241, 245, 249), font=body_font)
        y_start += 70

    # Speaker Badge at bottom
    speaker = "Madina (O'zbek Neural)" if "Madina" in scene.get("voice", "") else "Sardor (O'zbek Neural)"
    draw.rounded_rectangle([160, height-220, 650, height-150], radius=15, fill=(30, 41, 59))
    draw.text((190, height-205), f"🎙️ Ovoz: {speaker}", fill=accent, font=badge_font)

    # Logo / Branding
    draw.text((width-450, height-205), "🎬 MUHASIB VIDEO", fill=(148, 163, 184), font=badge_font)

    img.save(out_img_path, quality=95)
    print(f"Saved Scene Image: {out_img_path}")

async def generate_scene_audio(text, voice, out_audio_path):
    import edge_tts
    print(f"Synthesizing voice [{voice}]: {text}")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_audio_path)
    print(f"Saved Audio: {out_audio_path}")

def render_scene_video(img_path, audio_path, out_mp4_path):
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", img_path,
        "-i", audio_path,
        "-vf", "scale=1920:1080,zoompan=z='min(zoom+0.0015,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080",
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-shortest",
        "-pix_fmt", "yuv420p",
        out_mp4_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"Error rendering scene video: {res.stderr.decode('utf-8')}")
        sys.exit(1)
    print(f"Rendered Scene MP4: {out_mp4_path}")

def concat_videos(scene_files, out_final_mp4):
    list_file = os.path.join(DIR, "temp_playlist.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for sf in scene_files:
            f.write(f"file '{sf}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        out_final_mp4
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"Error concatenating videos: {res.stderr.decode('utf-8')}")
        sys.exit(1)
    if os.path.exists(list_file):
        os.remove(list_file)
    print(f"Final MP4 Video Ready: {out_final_mp4}")

async def build_full_video(scenes, output_mp4):
    scene_mp4s = []
    for i, sc in enumerate(scenes, 1):
        img_path = os.path.join(DIR, f"temp_scene_{i}.jpg")
        audio_path = os.path.join(DIR, f"temp_scene_{i}.mp3")
        mp4_path = os.path.join(DIR, f"temp_scene_{i}.mp4")

        # Use existing image if available in images/scene_i.jpg
        existing_img = os.path.join(DIR, "images", f"scene_{i}.jpg")
        if os.path.exists(existing_img):
            img_path = existing_img
        else:
            create_scene_image(sc, img_path)

        await generate_scene_audio(sc["text"], sc["voice"], audio_path)
        render_scene_video(img_path, audio_path, mp4_path)
        scene_mp4s.append(mp4_path)

    concat_videos(scene_mp4s, output_mp4)

    # Cleanup temp files
    for sf in scene_mp4s:
        if os.path.exists(sf):
            os.remove(sf)
        audio = sf.replace(".mp4", ".mp3")
        if os.path.exists(audio):
            os.remove(audio)
        tmp_img = sf.replace(".mp4", ".jpg")
        if os.path.exists(tmp_img) and not tmp_img.startswith(os.path.join(DIR, "images")):
            os.remove(tmp_img)

def main():
    parser = argparse.ArgumentParser(description="MUHASIB Real Uzbek Video Creator")
    parser.add_argument("--output", default=os.path.join(DIR, "real_working_video.mp4"), help="Output MP4 filepath")
    args = parser.parse_args()

    print("🚀 Starting Real Animated Video Generation...")
    asyncio.run(build_full_video(DEFAULT_SCENES, args.output))
    print(f"🎉 Success! Generated video available at: {args.output}")

if __name__ == "__main__":
    main()
