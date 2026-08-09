#!/usr/bin/env python3
"""Rasmdan personajni (asosiy obyektni) fonsiz PNG qilib ajratib oladi.

macOS'ning o'z Vision motoridan foydalanadi — internet ham, model yuklash ham
kerak emas. Natijada ikkita fayl chiqadi:

    <nom>_subject.png     — shaffof fonli personaj
    <nom>_mask.png        — niqob (kerak bo'lsa)

Foydalanish:
    .venv/bin/python video/cutout.py images/scene_1.jpg video/layers/
"""
import os
import sys

import Quartz
import Vision
from Foundation import NSURL, NSMutableDictionary


def ci_to_png(ci_image, path):
    ctx = Quartz.CIContext.contextWithOptions_(None)
    cs = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    data = ctx.PNGRepresentationOfImage_format_colorSpace_options_(
        ci_image, Quartz.kCIFormatRGBA8, cs, NSMutableDictionary.dictionary())
    if data is None:
        raise RuntimeError("PNG ga aylantirib bo'lmadi")
    data.writeToFile_atomically_(path, True)


def cutout(src, outdir):
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    url = NSURL.fileURLWithPath_(os.path.abspath(src))

    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
    req = Vision.VNGenerateForegroundInstanceMaskRequest.alloc().init()
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision xatosi: {err}")

    results = req.results()
    if not results:
        raise RuntimeError("Rasmda ajratiladigan obyekt topilmadi")
    obs = results[0]

    # 1) niqob
    mask_buf, err = obs.generateScaledMaskForImageForInstances_fromRequestHandler_error_(
        obs.allInstances(), handler, None)
    if mask_buf is None:
        raise RuntimeError(f"Niqob yaratilmadi: {err}")
    mask_ci = Quartz.CIImage.imageWithCVPixelBuffer_(mask_buf)
    mask_path = os.path.join(outdir, base + "_mask.png")
    ci_to_png(mask_ci, mask_path)

    # 2) fonsiz personaj
    cut_buf, err = obs.generateMaskedImageOfInstances_fromRequestHandler_croppedToInstancesExtent_error_(
        obs.allInstances(), handler, False, None)
    if cut_buf is None:
        raise RuntimeError(f"Kesib olinmadi: {err}")
    cut_ci = Quartz.CIImage.imageWithCVPixelBuffer_(cut_buf)
    cut_path = os.path.join(outdir, base + "_subject.png")
    ci_to_png(cut_ci, cut_path)

    ext = cut_ci.extent()
    print(f"  {base}: {int(ext.size.width)}x{int(ext.size.height)} → {cut_path}")
    return cut_path, mask_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    outdir = sys.argv[-1] if len(sys.argv) > 2 and os.path.isdir(sys.argv[-1]) \
        else os.path.join(os.path.dirname(os.path.abspath(__file__)), "layers")
    srcs = sys.argv[1:-1] if len(sys.argv) > 2 and outdir == sys.argv[-1] else sys.argv[1:]
    for s in srcs:
        cutout(s, outdir)
