#!/usr/bin/env python3
"""MUHASIB — "Qarz daftari" vektor multfilmi.

Do'kondor ota qog'oz daftarda adashib qoladi, qizi Madina telefonda MUHASIB ni
ko'rsatadi. Ota oddiy gap aytadi ("Alisherga ikki yuz ming qarz berdim"),
dastur qarzni yozib, kassa va qarzdorlarni o'zi hisoblaydi. Ota eski
daftarni chelakka otadi.

1) edge-tts bilan o'zbekcha ovozlar (uz-UZ-SardorNeural — ota, uz-UZ-MadinaNeural — qiz)
2) ovoz uzunligidan vaqt jadvali → video/qarz_daftar_timeline.json
3) render_anim.py orqali video/multik_qarz_daftar.html → MP4

    .venv/bin/python video/make_qarz_daftar.py            # 1920x1080, 30 fps
    .venv/bin/python video/make_qarz_daftar.py --tez      # 960x540, 12 fps — tez ko'rish
    .venv/bin/python video/make_qarz_daftar.py --ovozsiz  # internetsiz: faqat harakatni tekshirish
"""
import argparse
import asyncio
import json
import os
import shutil
import ssl
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD = os.path.join(HERE, "audio")
OUT = os.path.join(ROOT, "muhasib_qarz_daftar_multik.mp4")
TL_PATH = os.path.join(HERE, "qarz_daftar_timeline.json")
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

DAD = "uz-UZ-SardorNeural"
MAD = "uz-UZ-MadinaNeural"

# Ssenariy. Tartib muhim: sahna 6 ta gapni shu ketma-ketlikda kutadi
# (0-ota, 1-qiz, 2-ota telefonga, 3-qiz, 4-ota, 5-yakuniy ovoz).
LINES = [
    {"key": "qd_ota1", "who": "dad", "voice": DAD, "rate": "+4%",
     "text": "Voy-bo'y! Alisher qancha qarz edi o'zi? Daftarning o'sha beti qayoqqa ketdi?!"},
    {"key": "qd_qiz1", "who": "mad", "voice": MAD, "rate": "+2%",
     "text": "Dadajon, daftarni qo'ying! Muhasibga oddiy gapirsangiz bo'ldi, qolganini o'zi hisoblaydi."},
    {"key": "qd_ota2", "who": "dad", "voice": DAD, "rate": "+0%",
     "text": "Alisherga ikki yuz ming qarz berdim."},
    {"key": "qd_qiz2", "who": "mad", "voice": MAD, "rate": "+2%",
     "text": "Mana, yozib qo'ydi! Kassa, qarzdorlar, foyda — hammasi tepada turibdi."},
    {"key": "qd_ota3", "who": "dad", "voice": DAD, "rate": "+6%",
     "text": "Zo'r-ku! Endi bitta so'm ham yo'qolmaydi!"},
    {"key": "qd_yakun", "who": "mad", "voice": MAD, "rate": "-4%",
     "text": "Muhasib. Siz gapiring, u hisoblaydi."},
]

# Gap puffaklari (har biri 2 qator). None — puffak yo'q: 2-gap telefonda
# matn bo'lib chiqadi, 5-gap yakuniy ekranda.
BUBBLES = [
    ["Alisher qancha qarz edi?!", "Daftarning beti qani?"],
    ["Dadajon, daftarni qo'ying!", "MUHASIBga gapiring."],
    None,
    ["Kassa, qarzdorlar, foyda —", "hammasi tepada!"],
    ["Zo'r-ku! Endi bitta so'm", "ham yo'qolmaydi!"],
    None,
]

# Gaplar orasidagi pauza — shu paytda sahnada harakat bo'ladi
# (qiz eshikdan kiradi, telefon chiqadi, javob yoziladi, daftar otiladi).
GAP_AFTER = [2.8, 1.6, 2.9, 3.0, 1.4]
FIRST_START = 1.2
TAIL = 2.0
CHARS_PER_SEC = 14.0      # --ovozsiz da gap uzunligini taxminlash uchun


def _ssl_tuzat():
    """edge-tts o'z certifi to'plamini ishlatadi. Proksi ortida (SSL_CERT_FILE
    berilgan bo'lsa) o'sha sertifikatni ham tan olsin."""
    ca = os.environ.get("SSL_CERT_FILE")
    if not ca or not os.path.exists(ca):
        return
    from edge_tts import communicate
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=ca)
    communicate._SSL_CTX = ctx


async def synth():
    import edge_tts
    _ssl_tuzat()
    os.makedirs(AUD, exist_ok=True)
    for ln in LINES:
        ln["file"] = os.path.join(AUD, ln["key"] + ".mp3")
        print(f"  [{ln['voice']}] {ln['text'][:50]}…")
        await edge_tts.Communicate(ln["text"], ln["voice"], rate=ln["rate"]).save(ln["file"])


def duration(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tez", action="store_true", help="960x540, 12 fps — tez ko'rish")
    ap.add_argument("--ovozsiz", action="store_true",
                    help="ovoz sintez qilinmaydi, vaqt matn uzunligidan taxminlanadi")
    a = ap.parse_args()

    if a.ovozsiz:
        print("1) Ovozsiz rejim — gap uzunligi taxminiy.")
    else:
        print("1) O'zbekcha ovozlar (edge-tts)…")
        try:
            asyncio.run(synth())
        except Exception as e:
            sys.exit(f"Ovoz sintezi ishlamadi: {e}\n"
                     "Internetni tekshiring yoki harakatni ko'rish uchun --ovozsiz bilan ishga tushiring.")

    print("\n2) Vaqt jadvali…")
    start = FIRST_START
    for i, ln in enumerate(LINES):
        ln["dur"] = len(ln["text"]) / CHARS_PER_SEC if a.ovozsiz else duration(ln["file"])
        ln["start"] = start
        print(f"   {ln['key']:9s} {start:6.2f}s  +{ln['dur']:.2f}s")
        if i < len(GAP_AFTER):
            start += ln["dur"] + GAP_AFTER[i]
    total = LINES[-1]["start"] + LINES[-1]["dur"] + TAIL

    timeline = {
        "duration": round(total, 2),
        "lines": [{"who": ln["who"], "start": round(ln["start"], 3), "dur": round(ln["dur"], 3)}
                  for ln in LINES],
        "bubbles": BUBBLES,
        "transcript": LINES[2]["text"],
        "userMsg": ["Alisherga ikki yuz ming", "qarz berdim."],
        "who": "Alisher",
        "amount": 200000,
    }
    with open(TL_PATH, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    print(f"   Jami: {total:.2f}s")

    out = OUT
    if a.tez:
        out = out.replace(".mp4", "_tez.mp4")
    if a.ovozsiz:
        out = out.replace(".mp4", "_ovozsiz.mp4")
    fps, w, h = ("12", "960", "540") if a.tez else ("30", "1920", "1080")
    print("\n3) Kadrma-kadr render…")
    cmd = [sys.executable, os.path.join(HERE, "render_anim.py"),
           "--html", os.path.join(HERE, "multik_qarz_daftar.html"),
           "--out", out, "--fps", fps, "--w", w, "--h", h, "--config", TL_PATH]
    for ln in ([] if a.ovozsiz else LINES):
        cmd += ["--audio", f"{ln['file']}@{ln['start']:.3f}"]
    subprocess.run(cmd, check=True)
    print("\nTayyor:", out)


if __name__ == "__main__":
    main()
