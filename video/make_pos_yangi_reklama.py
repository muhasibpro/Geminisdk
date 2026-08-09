#!/usr/bin/env python3
"""MUHASIB POS yangi video reklama roligini tayyorlovchi script.

1) edge-tts bilan haqiqiy o'zbek ovozlarini sintez qiladi (uz-UZ-MadinaNeural, uz-UZ-SardorNeural)
2) Har bir gap davomiyligini o'lchaydi va timeline.json ga yozadi
3) render_anim.py orqali HTML animatsiyani yuqori sifatli MP4 ga aylantiradi
"""

import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_yangi_kassa_reklama.mp4")
FFPROBE = shutil_ffprobe = subprocess.run(["which", "ffprobe"], capture_output=True, text=True).stdout.strip() or "/opt/homebrew/bin/ffprobe"

CASHIER_VOICE = "uz-UZ-MadinaNeural"
OWNER_VOICE = "uz-UZ-SardorNeural"

LINES = [
    {
        "key": "cashier1",
        "voice": CASHIER_VOICE,
        "rate": "+0%",
        "text": "Assalomu alaykum! MUHASIB POS kassa dasturi bilan savdongiz uch baravar tezlashadi va barcha hisob-kitoblar aniq yuritiladi."
    },
    {
        "key": "owner1",
        "voice": OWNER_VOICE,
        "rate": "+5%",
        "text": "Ajoyib-ku! Barkod skanerlash, tushum nazorati va ombor qoldig'ini telefondan ham kuzatsa bo'ladimi?"
    },
    {
        "key": "cashier2",
        "voice": CASHIER_VOICE,
        "rate": "+0%",
        "text": "Albatta! MUHASIB POS — do'koningizga zamonaviy qulaylik va to'liq nazorat olib keladi!"
    }
]

GAP_BETWEEN = 0.8
TAIL_OUTRO = 3.5

async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        path = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  Ovoz sintezi [{ln['voice']}]: {ln['text'][:50]}…")
        await edge_tts.Communicate(ln["text"], ln["voice"], rate=ln["rate"]).save(path)
        ln["file"] = path

def get_duration(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    print("1) O'zbek Neural ovozlari sintez qilinmoqda…")
    asyncio.run(synth())

    for ln in LINES:
        ln["dur"] = get_duration(ln["file"])
        print(f"   {ln['key']}: {ln['dur']:.2f}s")

    print("\n2) Vaqt va timeline jadvali tuzilmoqda…")
    curr = 1.0
    starts = []
    for ln in LINES:
        starts.append(curr)
        curr += ln["dur"] + GAP_BETWEEN

    total_duration = curr + TAIL_OUTRO

    timeline = {
        "duration": round(total_duration, 2),
        "lines": [
            {"who": "cashier", "start": round(starts[0], 2), "dur": round(LINES[0]["dur"], 2)},
            {"who": "owner",   "start": round(starts[1], 2), "dur": round(LINES[1]["dur"], 2)},
            {"who": "cashier", "start": round(starts[2], 2), "dur": round(LINES[2]["dur"], 2)}
        ]
    }

    tl_path = os.path.join(HERE, "pos_yangi_timeline.json")
    with open(tl_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    print(f"   Umumiy reklama rolik vaqti: {total_duration:.2f} soniya")

    print("\n3) Kadrma-kadr MP4 render qilinmoqda (headless Chrome -> ffmpeg)…")
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

    print("   Buyruq:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"\n✅ YANGI REKLAMA ROLIK TAYYOR BO'LDI: {OUT}")

if __name__ == "__main__":
    main()
