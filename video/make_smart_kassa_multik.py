#!/usr/bin/env python3
"""MUHASIB Smart Kassa yangi animatsion reklama roligini ishlab chiqish scripti.

1) edge-tts yordamida o'zbekcha haqiqiy ovozlarni yaratadi (uz-UZ-SardorNeural, uz-UZ-MadinaNeural)
2) Audio vaqtlarini aniqlab timeline.json ga kiritadi
3) render_anim.py orqali multik HTML animatsiyasini yuqori sifatli MP4 ga render qiladi
"""

import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_smart_kassa_animatsiya.mp4")

FFPROBE_BIN = subprocess.run(["which", "ffprobe"], capture_output=True, text=True).stdout.strip() or "/opt/homebrew/bin/ffprobe"

BOY = "uz-UZ-SardorNeural"
CASH = "uz-UZ-MadinaNeural"

LINES = [
    {
        "key": "smart_cash",
        "voice": CASH,
        "rate": "+0%",
        "text": "Eskicha daftar va kalkulyatordan charchadingizmi? Do'koningizda hisob-kitob chalkashib ketyaptimi?"
    },
    {
        "key": "smart_boy1",
        "voice": BOY,
        "rate": "+5%",
        "text": "Ha, albatta! Zamonaviy va juda tez ishlaydigan kassa dasturi kerak!"
    },
    {
        "key": "smart_cash2",
        "voice": CASH,
        "rate": "+0%",
        "text": "Unda Muhasib POS siz uchun eng to'g'ri tanlov! Barkod skanerlash, qarzlar nazorati va mobil hisob-kitob bir joyda!"
    }
]

GAP_BETWEEN = 1.0
TAIL_OUTRO = 3.0

async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        path = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  Ovoz sintezi [{ln['voice']}]: {ln['text'][:45]}…")
        await edge_tts.Communicate(ln["text"], ln["voice"], rate=ln["rate"]).save(path)
        ln["file"] = path

def get_duration(path):
    r = subprocess.run([FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    print("1) O'zbekcha ovoz sintezi tayyorlanmoqda (edge-tts)...")
    asyncio.run(synth())
    
    for ln in LINES:
        ln["dur"] = get_duration(ln["file"])
        print(f"   audio {ln['key']}: {ln['dur']:.2f} soniya")

    print("\n2) Vaqt va animatsiya ssenariysi hisoblanmoqda...")
    starts = [10.0]  # kassa sahna boshlanishi
    starts.append(starts[0] + LINES[0]["dur"] + GAP_BETWEEN)
    starts.append(starts[1] + LINES[1]["dur"] + GAP_BETWEEN)
    
    total_dur = starts[2] + LINES[2]["dur"] + TAIL_OUTRO

    timeline = {
        "duration": round(total_dur, 2),
        "lines": [
            {"who": "cash", "start": round(starts[0], 2), "dur": round(LINES[0]["dur"], 2)},
            {"who": "boy", "start": round(starts[1], 2), "dur": round(LINES[1]["dur"], 2)},
            {"who": "cash", "start": round(starts[2], 2), "dur": round(LINES[2]["dur"], 2)},
        ],
        "cashText": ["Eskicha daftardan charchadingizmi?", "Muhasib POS sizga yordam beradi!"],
        "boyText": ["Bizga tez va ancha zamonaviy", "kassa dasturi zarur!"]
    }
    
    tl_path = os.path.join(HERE, "timeline.json")
    with open(tl_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    print(f"   Jami davomiylik: {total_dur:.2f} soniya")

    print("\n3) Frame-by-frame HTML render va MP4 video yaratish boshlandi...")
    cmd = [
        sys.executable, os.path.join(HERE, "render_anim.py"),
        "--html", os.path.join(HERE, "multik_pos_yangi.html"),
        "--out", OUT,
        "--fps", "30",
        "--w", "1920",
        "--h", "1080",
        "--config", tl_path
    ]
    
    for i, ln in enumerate(LINES):
        cmd += ["--audio", f"{ln['file']}@{starts[i]:.3f}"]

    subprocess.run(cmd, check=True)
    print("\n🎉 Muvaffaqiyatli yakunlandi! Yangi animated reklama video fayli:")
    print(OUT)

if __name__ == "__main__":
    main()
