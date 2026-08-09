#!/usr/bin/env python3
"""MUHASIB — Whiteboard / Doodle Hand-Drawing Animatsion reklama roligini tayyorlaydi.

1) edge-tts bilan o'zbekcha ovozlarni (Madina va Sardor) sintez qiladi
2) Har bir audio davomiyligini o'lchab timeline.json yaratadi
3) render_anim.py orqali multik_whiteboard.html ni kadrma-kadr MP4 ga aylantiradi

Ishga tushirish:
    .venv/bin/python video/make_whiteboard_multik.py
"""
import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_whiteboard_multik.mp4")

FFPROBE = "/opt/homebrew/bin/ffprobe"
if not os.path.exists(FFPROBE):
    FFPROBE = "ffprobe"

VOICE_WOMAN = "uz-UZ-MadinaNeural"
VOICE_MAN = "uz-UZ-SardorNeural"

LINES = [
    {
        "key": "wb_line1",
        "voice": VOICE_WOMAN,
        "rate": "+2%",
        "text": "Do'koningizda navbatlar ko'p va hisob-kitobda xatoliklar bo'lyaptimi?"
    },
    {
        "key": "wb_line2",
        "voice": VOICE_MAN,
        "rate": "+5%",
        "text": "Endi xavotirga o'rin yo'q! Salam POS va MUHASIB — bu super tezkor va zamonaviy POS kassa tizimi!"
    },
    {
        "key": "wb_line3",
        "voice": VOICE_MAN,
        "rate": "+3%",
        "text": "Bir soniyada skanerlash, ombor qoldig'i, foyda tahlili va masofaviy Telegram-bot nazorati!"
    },
    {
        "key": "wb_line4",
        "voice": VOICE_MAN,
        "rate": "+2%",
        "text": "Salam POS bilan savdongizni ikki baravar oshiring va kassani to'liq nazorat qiling!"
    }
]

FIRST_LINE_AT = 0.8
GAP_BETWEEN = 0.9
TAIL_TIME = 3.2


async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        path = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  ovoz [{ln['voice']}]: {ln['text'][:50]}…")
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

    print("\n2) Vaqt jadvali hisoblanmoqda…")
    starts = []
    curr = FIRST_LINE_AT
    for ln in LINES:
        starts.append(curr)
        curr += ln["dur"] + GAP_BETWEEN

    total_duration = curr - GAP_BETWEEN + TAIL_TIME

    timeline = {
        "duration": round(total_duration, 2),
        "lines": []
    }
    for i, ln in enumerate(LINES):
        timeline["lines"].append({
            "key": ln["key"],
            "start": round(starts[i], 2),
            "dur": round(ln["dur"], 2)
        })
        print(f"   gap {i+1} ({ln['key']}): {starts[i]:.2f}s → {starts[i] + ln['dur']:.2f}s")

    print(f"   Umumiy vaqt: {total_duration:.2f}s")

    tl_path = os.path.join(HERE, "whiteboard_timeline.json")
    with open(tl_path, "w") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    print("\n3) Whiteboard (Yozib-chizib ko'rsatuvchi) animatsion video render qilinmoqda…")
    cmd = [
        sys.executable, os.path.join(HERE, "render_anim.py"),
        "--html", os.path.join(HERE, "multik_whiteboard.html"),
        "--out", OUT,
        "--fps", "30",
        "--w", "1920",
        "--h", "1080",
        "--config", tl_path
    ]
    for i, ln in enumerate(LINES):
        cmd += ["--audio", f"{ln['file']}@{starts[i]:.3f}"]

    subprocess.run(cmd, check=True)
    print("\n✅ Whiteboard animation video muvaffaqiyatli tayyorlandi:", OUT)


if __name__ == "__main__":
    main()
