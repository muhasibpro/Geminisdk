#!/usr/bin/env python3
"""MUHASIB — Yoqimtoy AI Robot bilan animatsion reklama multfilmini yasaydi.

1) edge-tts bilan o'zbek ovozlarini sintez qiladi (Madina / Sardor)
2) Har bir gapning uzunligini o'lchab, vaqt jadvalini tuzadi
3) render_anim.py orqali multik_robot.html ni kadrma-kadr MP4 ga aylantiradi

Ishga tushirish:
    .venv/bin/python video/make_robot_multik.py
"""
import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_robot_multik.mp4")

# FFprobe joylashuvini qidiramiz
FFPROBE = "/opt/homebrew/bin/ffprobe"
if not os.path.exists(FFPROBE):
    FFPROBE = "ffprobe"

DILNOZA_VOICE = "uz-UZ-MadinaNeural"
ROBOT_VOICE = "uz-UZ-SardorNeural"

LINES = [
    {
        "key": "robot_dilnoza1",
        "voice": DILNOZA_VOICE,
        "rate": "+0%",
        "text": "Vaqt judayam kam, navbat bo'lsa uzayib ketyapti! Kassadagi hisob-kitobni qanday tezlashtirsam bo'ladi-ya?"
    },
    {
        "key": "robot_ai1",
        "voice": ROBOT_VOICE,
        "rate": "+12%",
        "text": "Xavotir olmang, Dilnoza opa! Sizga Muhasib AI kassa tizimi yordamga keladi!"
    },
    {
        "key": "robot_ai2",
        "voice": ROBOT_VOICE,
        "rate": "+6%",
        "text": "Muhasib kassa dasturi bilan bir soniyada skanerlash, aniq hisob-kitob va yuz foizlik nazorat! Savdo ikki baravar tezlashadi!"
    }
]

BUBBLE_DILNOZA = ["Vaqt judayam kam, navbat ketyapti!", "Kassa hisobini qanday tezlashtirsam bo'ladi?"]
BUBBLE_ROBOT1 = ["Xavotir olmang, Dilnoza opa!", "Sizga MUHASIB AI kassa yordamga keladi!"]
BUBBLE_ROBOT2 = ["MUHASIB kassa dasturi bilan:", "⚡ 1 soniyada skanerlash", "📊 Aniq hisob va 100% nazorat!"]

FIRST_LINE_AT = 1.0
GAP_1 = 1.0
GAP_2 = 1.0
TAIL = 3.5


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
    starts.append(starts[0] + LINES[0]["dur"] + GAP_1)
    starts.append(starts[1] + LINES[1]["dur"] + GAP_2)
    total = starts[2] + LINES[2]["dur"] + TAIL

    timeline = {
        "duration": round(total, 2),
        "lines": [
            {"who": "dilnoza", "start": round(starts[0], 2), "dur": round(LINES[0]["dur"], 2)},
            {"who": "robot1",   "start": round(starts[1], 2), "dur": round(LINES[1]["dur"], 2)},
            {"who": "robot2",   "start": round(starts[2], 2), "dur": round(LINES[2]["dur"], 2)},
        ],
        "dilnozaText": BUBBLE_DILNOZA,
        "robotText1": BUBBLE_ROBOT1,
        "robotText2": BUBBLE_ROBOT2,
    }
    tl_path = os.path.join(HERE, "robot_timeline.json")
    with open(tl_path, "w") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    for i, s in enumerate(starts):
        print(f"   gap {i+1}: {s:.2f}s → {s + LINES[i]['dur']:.2f}s")
    print(f"   umumiy vaqt: {total:.2f}s")

    print("3) Yoqimtoy AI Robot multik video render qilinmoqda…")
    cmd = [sys.executable, os.path.join(HERE, "render_anim.py"),
           "--html", os.path.join(HERE, "multik_robot.html"),
           "--out", OUT, "--fps", "30", "--w", "1920", "--h", "1080",
           "--config", tl_path]
    for i, ln in enumerate(LINES):
        cmd += ["--audio", f"{ln['file']}@{starts[i]:.3f}"]
    subprocess.run(cmd, check=True)
    print("\nTayyor video:", OUT)


if __name__ == "__main__":
    main()
