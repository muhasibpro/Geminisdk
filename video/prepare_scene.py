#!/usr/bin/env python3
"""Real rasmni animatsiya uchun qatlamlarga ajratadi.

Bittа rasmdan uchta narsa tayyorlaydi:
  <nom>_subject.png  — fonsiz personaj (asl rasm bilan bir xil o'lchamda, ustma-ust tushadi)
  <nom>_bg.jpg       — personaj olib tashlangan fon (yonidagi kontent bilan to'ldiriladi)
  <nom>_rig.json     — personaj chegarasi va bo'g'in nuqtalari (son chizig'i va h.k.)

Foydalanish:
    .venv/bin/python video/prepare_scene.py images/scene_1.jpg
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAYERS = os.path.join(HERE, "layers")
MAGICK = "/opt/homebrew/bin/magick"


def sh(*args):
    subprocess.run(list(args), check=True)


def identify(path, fmt):
    return subprocess.run([MAGICK, "identify", "-format", fmt, path],
                          capture_output=True, text=True, check=True).stdout.strip()


def prepare(src):
    os.makedirs(LAYERS, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]

    sys.path.insert(0, HERE)
    from cutout import cutout
    subj, mask = cutout(src, LAYERS)

    w, h = (int(x) for x in identify(src, "%w %h").split())
    bw, bh, bx, by = (int(x) for x in identify(subj, "%[fx:page.width] %[fx:page.height] 0 0").split()[:2] + ["0", "0"])
    trim = identify(subj, "%@")                       # WxH+X+Y
    tw, rest = trim.split("x")
    th, tx, ty = rest.replace("+", " ").split()
    tw, th, tx, ty = int(tw), int(th), int(tx), int(ty)

    # fon: teshikni yonidagi kontent bilan to'ldiramiz (blur emas — blur soya qoldiradi)
    shift = max(220, min(tw + 40, w // 2))
    fill = os.path.join(LAYERS, base + "_fill.png")
    maskd = os.path.join(LAYERS, base + "_maskd.png")
    bg = os.path.join(LAYERS, base + "_bg.jpg")
    sh(MAGICK, src, "-roll", f"+{shift}+0", "-blur", "0x3", fill)
    sh(MAGICK, mask, "-colorspace", "gray", "-morphology", "Dilate", "Disk:16", "-blur", "0x10", maskd)
    sh(MAGICK, src, fill, maskd, "-composite", bg)
    os.remove(fill)
    os.remove(maskd)

    rig = {
        "w": w, "h": h,
        "bg": os.path.relpath(bg, HERE),
        "subject": os.path.relpath(subj, HERE),
        "bbox": [tx, ty, tw, th],
        # son chizig'i — gavdaning taxminan 56% balandligida; kerak bo'lsa qo'lda to'g'rilang
        "hipY": ty + int(th * 0.56),
        "splitX": tx + tw // 2,
        "legBackPivot": [tx + int(tw * 0.29), ty + int(th * 0.56)],
        "legFrontPivot": [tx + int(tw * 0.43), ty + int(th * 0.56)],
        "groundY": ty + th,
    }
    rig_path = os.path.join(LAYERS, base + "_rig.json")
    with open(rig_path, "w") as f:
        json.dump(rig, f, indent=2)
    print(f"  fon:  {bg}")
    print(f"  rig:  {rig_path}  (hipY={rig['hipY']}, bbox={rig['bbox']})")
    return rig_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for s in sys.argv[1:]:
        print(s)
        prepare(s)
