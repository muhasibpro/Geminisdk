#!/usr/bin/env python3
"""MUHASIB — POS REAL RASM + REAL QALAM QO'L + VEKTOR MULTIK.

Target:
- Qora qalam tutgan real qo'l rasmi (real hand holding black pen)
- POS kassa terminali real rasmi (real photorealistic POS system photo cutout)
- Qolgan barcha grafik, matn va belgilashlar vektor SVG animatsiya (vector doodles & strokes)

Ishga tushirish:
    .venv/bin/python video/make_pos_real_vector.py
"""
import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_pos_real_vector.mp4")

FFPROBE = "/opt/homebrew/bin/ffprobe"
if not os.path.exists(FFPROBE):
    FFPROBE = "ffprobe"

VOICE_WOMAN = "uz-UZ-MadinaNeural"
VOICE_MAN = "uz-UZ-SardorNeural"

LINES = [
    {
        "key": "prv_line1",
        "voice": VOICE_WOMAN,
        "rate": "+2%",
        "text": "Do'koningizda hisob-kitob qiyin va kassada tartibsizliklar bo'lyaptimi?"
    },
    {
        "key": "prv_line2",
        "voice": VOICE_MAN,
        "rate": "+4%",
        "text": "Endi tayyor yechim bor! MUHASIB — zamonaviy va ultra tezkor POS kassa tizimi!"
    },
    {
        "key": "prv_line3",
        "voice": VOICE_MAN,
        "rate": "+3%",
        "text": "Skanerlash, chek chiqarish, ombor qoldig'i va Telegram-bot orqali tahlillar har anitda kaftingizda!"
    },
    {
        "key": "prv_line4",
        "voice": VOICE_MAN,
        "rate": "+2%",
        "text": "MUHASIB bilan savdongizni 2 baravar oshiring va kassani to'liq tartibga soling!"
    }
]

FIRST_LINE_AT = 0.5
GAP_BETWEEN = 0.8
TAIL_TIME = 3.0


async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        path = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  Ovozlantiroq [{ln['voice']}]: {ln['text'][:55]}…")
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

    print("\n2) Vaqt jadvali (Timeline) hisoblanmoqda…")
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

    print(f"   Umumiy video vaqti: {total_duration:.2f}s")

    tl_path = os.path.join(HERE, "pos_real_vector_timeline.json")
    with open(tl_path, "w") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    # HTML dynamic duration update
    html_path = os.path.join(HERE, "multik_pos_real_vector.html")
    with open(html_path, "r") as f:
        html_code = f.read()

    # replace window.DURATION = ...
    import re
    html_code = re.sub(r'window\.DURATION\s*=\s*[\d\.]+;', f'window.DURATION = {total_duration:.2f};', html_code)
    with open(html_path, "w") as f:
        f.write(html_code)

    print("\n3) Kadrma-kadr video render (Real POS + Real Qora Qalam + Vektor)...")
    cmd = [
        sys.executable, os.path.join(HERE, "render_anim.py"),
        "--html", html_path,
        "--out", OUT,
        "--fps", "30",
        "--w", "1920",
        "--h", "1080",
        "--config", tl_path
    ]
    for i, ln in enumerate(LINES):
        cmd += ["--audio", f"{ln['file']}@{starts[i]:.3f}"]

    subprocess.run(cmd, check=True)
    print("\n✅ POS Real Rasm + Qora Qalam + Vektor Video tayyor bo'ldi:", OUT)


if __name__ == "__main__":
    main()
