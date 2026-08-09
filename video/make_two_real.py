#!/usr/bin/env python3
"""Ikkita real rasmdan (Supermarketdagi bola real_1 + Kassa real_2) va MUHASIB /muhasib. logo bilan 2 sahnadan iborat real rolik.

   .venv/bin/python video/make_two_real.py
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
    {"k": "2s_1", "v": LADY, "t": "Do'koningizda hisob-kitob va xaridlar hali ham sekin ketyaptimi?"},
    {"k": "2s_2", "v": BOY,  "t": "MUHASIB POS bilan har bir sotuv bir soniyada rasmiylashtiriladi!"},
]
GAP = 0.8
HEAD = 0.6


async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for l in LINES:
        l["file"] = os.path.join(AUD, l["k"] + ".mp3")
        voice_rate = "+10%" if l["v"] == BOY else "+0%"
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
    names = ["real_1", "real_2"]
    out_name = "muhasib_2_sahna_real.mp4"
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
        start = 0.0 if i == 0 else cuts[-1][1] - 0.4
        end = l["at"] + l["dur"] + (0.8 if i == 0 else 3.0)
        cuts.append((start, end))
    total = round(cuts[-1][1], 2)

    r1, r2 = (rig(n) for n in names)
    cfg = {
        "w": r1["w"], "h": r1["h"], "duration": total,
        "scenes": [
            {"bg": r1["bg"], "subject": r1["subject"], "in": cuts[0][0], "out": cuts[0][1],
             "motion": "walk", "hipY": r1["hipY"], "splitX": 855, "bbox": r1["bbox"],
             "legB": r1["legBackPivot"], "legF": r1["legFrontPivot"],
             "from": -470, "walkDur": 3.6, "push": 0.07},
            {"bg": r2["bg"], "subject": r2["subject"], "in": cuts[1][0], "out": cuts[1][1],
             "motion": "lean", "bbox": r2["bbox"], "push": 0.08},
        ],
        "texts": {
            "price": "TEZKOR SKANER",
            "shout": "MUHASIB — bir soniyada!",
            "priceAt": [LINES[0]["at"] + 0.6, LINES[0]["at"] + LINES[0]["dur"] + 0.5],
            "shoutAt": [LINES[1]["at"], LINES[1]["at"] + LINES[1]["dur"] + 0.5],
            "cardAt": [LINES[1]["at"] + 0.2, total - 1.8],
            "scanAt": [LINES[1]["at"] + 0.8, LINES[1]["at"] + 2.2],
            "endAt": total - 2.0,
        },
    }
    cfg_path = os.path.join(HERE, "two_real_config.json")
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"   umumiy vaqt: {total}s")

    out = os.path.join(ROOT, out_name)
    print("2) Ikkita sahnadan iborat video render qilinmoqda…")
    cmd = [sys.executable, os.path.join(HERE, "render_anim.py"),
           "--html", os.path.join(HERE, "multik_real_full.html"),
           "--out", out, "--fps", "30", "--w", "1920", "--h", "1080", "--config", cfg_path]
    for l in LINES:
        cmd += ["--audio", f"{l['file']}@{l['at']:.3f}"]
    subprocess.run(cmd, check=True)
    print("\nTayyor 2-sahna video:", out)


if __name__ == "__main__":
    main()
