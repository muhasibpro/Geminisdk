#!/usr/bin/env python3
"""MUHASIB — Kung Fu Panda animatsion reklama multfilmini yasaydi.

1) edge-tts bilan haqiqiy o'zbek ovozlarini sintez qiladi (Sardor / Madina)
2) Har bir gapning uzunligini o'lchab, vaqt jadvalini tuzadi
3) render_anim.py orqali multik_panda.html ni kadrma-kadr MP4 ga aylantiradi

Ishga tushirish:
    .venv/bin/python video/make_panda_multik.py
"""
import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_panda_multik.mp4")
FFPROBE = "/opt/homebrew/bin/ffprobe"

BOY = "uz-UZ-SardorNeural"
CASH = "uz-UZ-MadinaNeural"

LINES = [
    {"key": "cash_panda", "voice": CASH, "rate": "+0%",
     "text": "Uka, energetik ichimligingiz yigirma besh ming so'm bo'ldi."},
    {"key": "boy_panda1", "voice": BOY, "rate": "+8%",
     "text": "Vay! Nega sizlarda Muhasib dasturi yo'q?!"},
    {"key": "boy_panda2", "voice": BOY, "rate": "+0%",
     "text": "Muhasib bilan bir soniyada skaner, aniq hisob-kitob va zamonaviy kassa!"},
]

BUBBLE_CASH = ["Uka, energetik ichimligingiz", "25 000 so'm bo'ldi."]
BUBBLE_BOY = ["VAY!", "Nega sizlarda MUHASIB", "dasturi yo'q?!"]
PRICE = "25 000 so'm"

FIRST_LINE_AT = 12.2
GAP_AFTER_CASH = 1.3
GAP_AFTER_BOY = 1.5
TAIL = 3.4


async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        path = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  ovoz [{ln['voice']}]: {ln['text'][:48]}…")
        await edge_tts.Communicate(ln["text"], ln["voice"], rate=ln["rate"]).save(path)
        ln["file"] = path


def duration(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    print("1) O'zbek ovozlari sintez qilinmoqda…")
    asyncio.run(synth())
    for ln in LINES:
        ln["dur"] = duration(ln["file"])
        print(f"   {ln['key']}: {ln['dur']:.2f}s")

    print("2) Vaqt jadvali hisoblanmoqda…")
    starts = [FIRST_LINE_AT]
    starts.append(starts[0] + LINES[0]["dur"] + GAP_AFTER_CASH)
    starts.append(starts[1] + LINES[1]["dur"] + GAP_AFTER_BOY)
    total = starts[2] + LINES[2]["dur"] + TAIL

    timeline = {
        "duration": round(total, 2),
        "lines": [
            {"who": "cash", "start": round(starts[0], 2), "dur": round(LINES[0]["dur"], 2)},
            {"who": "boy",  "start": round(starts[1], 2), "dur": round(LINES[1]["dur"], 2)},
            {"who": "boy",  "start": round(starts[2], 2), "dur": round(LINES[2]["dur"], 2)},
        ],
        "price": PRICE,
        "cashText": BUBBLE_CASH,
        "boyText": BUBBLE_BOY,
    }
    tl_path = os.path.join(HERE, "panda_timeline.json")
    with open(tl_path, "w") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    for i, s in enumerate(starts):
        print(f"   gap {i+1}: {s:.2f}s → {s + LINES[i]['dur']:.2f}s")
    print(f"   umumiy vaqt: {total:.2f}s")

    print("3) Kung Fu Panda multik video render qilinmoqda…")
    cmd = [sys.executable, os.path.join(HERE, "render_anim.py"),
           "--html", os.path.join(HERE, "multik_panda.html"),
           "--out", OUT, "--fps", "30", "--w", "1920", "--h", "1080",
           "--config", tl_path]
    for i, ln in enumerate(LINES):
        cmd += ["--audio", f"{ln['file']}@{starts[i]:.3f}"]
    subprocess.run(cmd, check=True)
    print("\nTayyor video:", OUT)


if __name__ == "__main__":
    main()
