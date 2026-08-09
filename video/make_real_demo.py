#!/usr/bin/env python3
"""Real rasmdan reklama roligi yasaydi (rasm → qatlamlar → animatsiya → MP4).

Ishga tushirish:
    .venv/bin/python video/make_real_demo.py [rasm.jpg]

Standart rasm: images/scene_1.jpg
"""
import asyncio
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
FFPROBE = "/opt/homebrew/bin/ffprobe"

BOY = "uz-UZ-SardorNeural"
LADY = "uz-UZ-MadinaNeural"

LINES = [
    {"key": "r0", "voice": LADY, "at": 1.0,
     "text": "Do'koningizda hisob-kitob hali ham qo'lda ketyaptimi?"},
    {"key": "r1", "voice": BOY, "at": 5.6,
     "text": "MUHASIB bilan har bir sotuv bir soniyada rasmiylashadi."},
    {"key": "r2", "voice": BOY, "at": 10.0,
     "text": "MUHASIB — zamonaviy POS kassa dasturi."},
]


async def synth():
    import edge_tts
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        ln["file"] = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  ovoz [{ln['voice']}]: {ln['text'][:46]}…")
        await edge_tts.Communicate(ln["text"], ln["voice"]).save(ln["file"])


def duration(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "images", "scene_1.jpg")
    base = os.path.splitext(os.path.basename(src))[0]
    rig_path = os.path.join(HERE, "layers", base + "_rig.json")

    if not os.path.exists(rig_path):
        print("1) Rasm qatlamlarga ajratilmoqda…")
        sys.path.insert(0, HERE)
        from prepare_scene import prepare
        rig_path = prepare(src)
    else:
        print("1) Tayyor qatlamlar topildi:", rig_path)

    with open(rig_path) as f:
        rig = json.load(f)

    print("2) O'zbek ovozlari…")
    asyncio.run(synth())
    for ln in LINES:
        ln["dur"] = duration(ln["file"])
        print(f"   {ln['key']}: {ln['dur']:.2f}s  ({ln['at']:.1f} → {ln['at']+ln['dur']:.1f})")

    total = round(max(l["at"] + l["dur"] for l in LINES) + 0.9, 2)

    cfg = {
        "w": rig["w"], "h": rig["h"],
        "bg": rig["bg"], "subject": rig["subject"],
        "bbox": rig["bbox"], "hipY": rig["hipY"],
        "splitX": 700,                      # oyoqlar ajraladigan joy (qo'lda aniqlangan)
        "legBackPivot": rig["legBackPivot"],
        "legFrontPivot": rig["legFrontPivot"],
        "walkFrom": -470,
        "walkIn": [0.5, 4.3],
        "glow": [962, 345, 210],
        "glowAt": [4.1, 5.3],
        "cardAt": [5.4, total - 1.6],
        "scanAt": [5.9, 7.1],
        "endAt": [LINES[2]["at"] - 0.5, total],
        "duration": total,
        "item": "Turbo Spark energetik",
        "price": "25 000",
        "total": "25 000 so'm",
    }
    cfg_path = os.path.join(HERE, "real_config.json")
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"   umumiy: {total}s")

    out = os.path.join(ROOT, "muhasib_real_reklama.mp4")
    print("3) Render…")
    cmd = [sys.executable, os.path.join(HERE, "render_anim.py"),
           "--html", os.path.join(HERE, "multik_real.html"),
           "--out", out, "--fps", "30", "--w", "1920", "--h", "1080",
           "--config", cfg_path]
    for ln in LINES:
        cmd += ["--audio", f"{ln['file']}@{ln['at']:.3f}"]
    subprocess.run(cmd, check=True)
    print("\nTayyor:", out)


if __name__ == "__main__":
    main()
