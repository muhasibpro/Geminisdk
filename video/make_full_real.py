#!/usr/bin/env python3
"""Real AI Robot rasmlaridan TO'LIQ rolik: Yoqimtoy AI Robot → Kassa → MUHASIB POS.

    .venv/bin/python video/make_full_real.py real
"""
import asyncio, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
FFPROBE = "/opt/homebrew/bin/ffprobe"
if not os.path.exists(FFPROBE):
    FFPROBE = "ffprobe"

BOY, LADY = "uz-UZ-SardorNeural", "uz-UZ-MadinaNeural"

LINES = [
    {"k": "f1", "v": LADY, "t": "Aqlli Yoqimtoy AI Robot do'kon boylab yurib, tartibni kuzatmoqda."},
    {"k": "f2", "v": LADY, "t": "Kassada navbat ko'payib ketdi, hisob-kitobni qanday tezlashtirsam bo'ladi?"},
    {"k": "f3", "v": BOY,  "t": "Xavotir olmang! Muhasib AI kassa dasturi yordamga keladi!"},
    {"k": "f4", "v": BOY,  "t": "Muhasib bilan bir soniyada skanerlash, aniq hisob va yuz foizlik nazorat!"},
]
GAP = 0.9          # gaplar orasidagi pauza
HEAD = 0.8         # birinchi gapgacha


async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for l in LINES:
        l["file"] = os.path.join(AUD, l["k"] + ".mp3")
        voice_rate = "+12%" if l["v"] == BOY else "+0%"
        await edge_tts.Communicate(l["t"], l["v"], rate=voice_rate).save(l["file"])
        print("   ovoz:", l["k"], l["t"][:44])


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip())


def rig(name):
    with open(os.path.join(HERE, "layers", name + "_rig.json")) as f:
        return json.load(f)


def main():
    pref = sys.argv[1] if len(sys.argv) > 1 else "real"
    names = [f"{pref}_{i}" for i in (1, 2, 3, 4)]
    out_name = "muhasib_dokon_real.mp4" if pref == "real" else "muhasib_dokon_multik.mp4"
    print("1) O'zbek ovozlari sintez qilinmoqda…")
    asyncio.run(synth())
    at = HEAD
    for l in LINES:
        l["dur"] = dur(l["file"])
        l["at"] = at
        at += l["dur"] + GAP
        print(f"   {l['k']}: {l['at']:.1f}s → {l['at']+l['dur']:.1f}s")

    cuts = []
    for i, l in enumerate(LINES):
        start = 0.0 if i == 0 else cuts[-1][1] - 0.55
        end = l["at"] + l["dur"] + (0.9 if i < 3 else 3.4)
        cuts.append((start, end))
    total = round(cuts[-1][1], 2)

    r1, r2, r3, r4 = (rig(n) for n in names)
    split1 = 855 if pref == "real" else 700
    cfg = {
        "w": r1["w"], "h": r1["h"], "duration": total,
        "scenes": [
            {"bg": r1["bg"], "subject": r1["subject"], "in": cuts[0][0], "out": cuts[0][1],
             "motion": "walk", "hipY": r1["hipY"], "splitX": split1, "bbox": r1["bbox"],
             "legB": r1["legBackPivot"], "legF": r1["legFrontPivot"],
             "from": -470, "walkDur": 3.6, "push": 0.07},
            {"bg": r2["bg"], "subject": r2["subject"], "in": cuts[1][0], "out": cuts[1][1],
             "motion": "lean", "bbox": r2["bbox"], "push": 0.08},
            {"bg": r3["bg"], "subject": r3["subject"], "in": cuts[2][0], "out": cuts[2][1],
             "motion": "punch", "bbox": r3["bbox"], "hit": LINES[2]["at"], "push": 0.05},
            {"bg": r4["bg"], "subject": r4["subject"], "in": cuts[3][0], "out": cuts[3][1],
             "motion": "idle", "bbox": r4["bbox"], "push": 0.10},
        ],
        "texts": {
            "price": "TEZKOR SKANER",
            "shout": "MUHASIB — bir soniyada!",
            "priceAt": [LINES[1]["at"] + 0.6, LINES[1]["at"] + LINES[1]["dur"] + 1.2],
            "shoutAt": [LINES[2]["at"], LINES[2]["at"] + LINES[2]["dur"] + 0.6],
            "cardAt": [LINES[3]["at"] + 0.2, total - 2.6],
            "scanAt": [LINES[3]["at"] + 0.8, LINES[3]["at"] + 2.2],
            "endAt": total - 2.4,
        },
    }
    cfg_path = os.path.join(HERE, "full_config.json")
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"   umumiy vaqt: {total}s")

    out = os.path.join(ROOT, out_name)
    print("2) Multfilm video render qilinmoqda…")
    cmd = [sys.executable, os.path.join(HERE, "render_anim.py"),
           "--html", os.path.join(HERE, "multik_real_full.html"),
           "--out", out, "--fps", "30", "--w", "1920", "--h", "1080", "--config", cfg_path]
    for l in LINES:
        cmd += ["--audio", f"{l['file']}@{l['at']:.3f}"]
    subprocess.run(cmd, check=True)
    print("\nTayyor video:", out)


if __name__ == "__main__":
    main()
