#!/usr/bin/env python3
"""MUHASIB Cyberpunk / Pop-Art Super Kreativ reklama roligini yasaydi.

1) edge-tts bilan o'zbekcha ovozlarni sintez qiladi
2) timeline.json hisoblaydi
3) render_anim.py orqali HTML animatsiyani MP4 ga o'giradi
"""
import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_cyberpunk_creative.mp4")

# macOS / System ffprobe path fallback
FFPROBE = "ffprobe"
if os.path.exists("/opt/homebrew/bin/ffprobe"):
    FFPROBE = "/opt/homebrew/bin/ffprobe"

VOICE_FEMALE = "uz-UZ-MadinaNeural"
VOICE_MALE = "uz-UZ-SardorNeural"

LINES = [
    {
        "key": "cyber_1",
        "voice": VOICE_FEMALE,
        "rate": "+5%",
        "text": "Eski kassada yana navbat va xatolar-a?! Yigirmanchi asrda qolib ketibsizku!"
    },
    {
        "key": "cyber_2",
        "voice": VOICE_MALE,
        "rate": "+2%",
        "text": "To'xtang! Muhasib POS bilan kassa ishi bir soniyada hal bo'ladi! Aniq hisob va tezkor kassa!"
    },
    {
        "key": "cyber_3",
        "voice": VOICE_FEMALE,
        "rate": "+5%",
        "text": "Vau! Savdo uch baravar tezlashdi, daromad va ombor esa doim to'liq nazoratda!"
    },
    {
        "key": "cyber_4",
        "voice": VOICE_MALE,
        "rate": "+0%",
        "text": "Muhasib POS — biznesingiz uchun eng aqlli va zamonaviy kassa tizimi!"
    }
]

GAP_DURS = [1.0, 1.2, 1.2]  # gaplar orasidagi pauzalar
TAIL_DUR = 3.5

async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        path = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  Ovoz [{ln['voice']}]: {ln['text'][:45]}…")
        await edge_tts.Communicate(ln["text"], ln["voice"], rate=ln["rate"]).save(path)
        ln["file"] = path

def get_duration(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    print("1) O'zbek ovozlari sintez qilinmoqda (edge-tts)…")
    asyncio.run(synth())
    
    for ln in LINES:
        ln["dur"] = get_duration(ln["file"])
        print(f"   {ln['key']}: {ln['dur']:.2f}s")

    starts = []
    curr = 1.0 # 1.0 soniyada boshlanadi
    for i, ln in enumerate(LINES):
        starts.append(curr)
        gap = GAP_DURS[i] if i < len(GAP_DURS) else 0
        curr += ln["dur"] + gap
    
    total = curr + TAIL_DUR

    timeline = {
        "duration": round(total, 2),
        "starts": [round(s, 2) for s in starts],
        "durs": [round(ln["dur"], 2) for ln in LINES]
    }

    tl_path = os.path.join(HERE, "cyberpunk_timeline.json")
    with open(tl_path, "w") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    print(f"2) Vaqt jadvali: Umumiy vaqt = {total:.2f}s")
    for i, s in enumerate(starts):
        print(f"   Gap {i+1}: {s:.2f}s - {s + LINES[i]['dur']:.2f}s")

    print("3) Canvas/SVG HTML animatsiyasi video faylga render qilinmoqda…")
    cmd = [
        sys.executable, os.path.join(HERE, "render_anim.py"),
        "--html", os.path.join(HERE, "multik_cyberpunk.html"),
        "--out", OUT,
        "--fps", "30",
        "--w", "1920",
        "--h", "1080",
        "--config", tl_path
    ]

    for i, ln in enumerate(LINES):
        cmd += ["--audio", f"{ln['file']}@{starts[i]:.3f}"]

    subprocess.run(cmd, check=True)
    print("\n✅ MUVAFFAQIYATLI YARATILDI:", OUT)

if __name__ == "__main__":
    main()
