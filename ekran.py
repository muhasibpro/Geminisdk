#!/usr/bin/env python3
"""Ekran boshqaruvi — agent Mac ekranini ko'radi va sichqoncha/klaviatura bilan ishlaydi.

Muhim nuqta: skrinshot piksellarda (Retina'da 2x), sichqoncha esa nuqtalarda
ishlaydi. Shuning uchun rasm har doim ekranning MANTIQIY o'lchamiga
kichraytiriladi — model rasmda ko'rgan koordinata to'g'ridan-to'g'ri bosish
koordinatasi bo'ladi, hech qanday hisob-kitob kerak emas.
"""
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

CLICLICK = shutil.which("cliclick") or "/opt/homebrew/bin/cliclick"
SIPS = "/usr/bin/sips"
SCREENCAPTURE = "/usr/sbin/screencapture"
QULF = threading.Lock()
_OLCHAM = {"w": 0, "h": 0}


def bor():
    """Sichqoncha/klaviatura boshqaruvi mavjudmi."""
    return os.path.exists(CLICLICK)


def olcham():
    """Ekranning mantiqiy (nuqta) o'lchami."""
    if _OLCHAM["w"]:
        return _OLCHAM["w"], _OLCHAM["h"]
    try:
        import Quartz
        r = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        _OLCHAM["w"] = int(r.size.width)
        _OLCHAM["h"] = int(r.size.height)
    except Exception:
        try:
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "Finder" to get bounds of window of desktop'],
                capture_output=True, text=True, timeout=8).stdout
            son = [int(x) for x in re.findall(r"-?\d+", out)]
            if len(son) >= 4:
                _OLCHAM["w"], _OLCHAM["h"] = son[2], son[3]
        except Exception:
            pass
    if not _OLCHAM["w"]:
        _OLCHAM["w"], _OLCHAM["h"] = 1512, 982
    return _OLCHAM["w"], _OLCHAM["h"]


def skrin(papka=None, sifat=None):
    """Ekran rasmini oladi, mantiqiy o'lchamga keltiradi → (fayl_yoli, xato)."""
    with QULF:
        fd, xom = tempfile.mkstemp(prefix="agy_ekran_", suffix=".jpg")
        os.close(fd)
        try:
            r = subprocess.run([SCREENCAPTURE, "-x", "-t", "jpg", xom],
                               capture_output=True, timeout=15)
            if r.returncode != 0 or not os.path.isfile(xom) or os.path.getsize(xom) < 256:
                xabar = (r.stderr or b"").decode("utf-8", "ignore").strip()
                return "", (
                    "Ekranni ko'rib bo'lmadi. Sababi deyarli har doim ruxsat: Tizim sozlamalari → "
                    "Maxfiylik va xavfsizlik → Ekranni yozib olish bo'limida shu dasturni "
                    "ishga tushirgan ilovaga (Terminal yoki Python) ruxsat bering, so'ng "
                    "dasturni qayta ishga tushiring."
                    + (" Tizim xabari: " + xabar if xabar else ""))
            w, h = olcham()
            subprocess.run([SIPS, "-z", str(h), str(w), xom],
                           capture_output=True, timeout=20)
            if papka:
                os.makedirs(papka, exist_ok=True)
                yol = os.path.join(papka, "ekran_%d.jpg" % int(time.time() * 1000))
                shutil.move(xom, yol)
                return yol, ""
            return xom, ""
        except Exception as exc:
            try:
                os.unlink(xom)
            except OSError:
                pass
            return "", str(exc)[:220]


def _cliclick(*argv):
    if not bor():
        raise RuntimeError("cliclick o'rnatilmagan. Terminalda: brew install cliclick")
    r = subprocess.run([CLICLICK] + list(argv), capture_output=True, text=True, timeout=25)
    if r.returncode != 0:
        xato = (r.stderr or r.stdout or "").strip()
        if "not trusted" in xato.lower() or "accessibility" in xato.lower():
            raise RuntimeError("Kirish huquqi yo'q. Tizim sozlamalari → Maxfiylik va "
                               "xavfsizlik → Kirish imkoniyati'da terminalga ruxsat bering.")
        raise RuntimeError(xato or "cliclick xatosi")
    return (r.stdout or "").strip()


def _cheklov(x, y):
    w, h = olcham()
    return max(0, min(int(x), w - 1)), max(0, min(int(y), h - 1))


def bos(x, y, tur="chap", marta=1):
    x, y = _cheklov(x, y)
    kod = {"chap": "c", "ong": "rc", "orta": "c", "ikki": "dc"}.get(str(tur), "c")
    if int(marta) >= 2 and kod == "c":
        kod = "dc"
    _cliclick("%s:%d,%d" % (kod, x, y))
    time.sleep(0.35)
    return {"ok": True, "x": x, "y": y}


def kursor(x, y):
    x, y = _cheklov(x, y)
    _cliclick("m:%d,%d" % (x, y))
    return {"ok": True, "x": x, "y": y}


def sudra(x1, y1, x2, y2):
    x1, y1 = _cheklov(x1, y1)
    x2, y2 = _cheklov(x2, y2)
    _cliclick("dd:%d,%d" % (x1, y1), "du:%d,%d" % (x2, y2))
    time.sleep(0.3)
    return {"ok": True}


def yoz(matn):
    matn = str(matn or "")
    if not matn:
        return {"ok": False, "sabab": "matn bo'sh"}
    # cliclick uzun matnda ba'zan belgi tashlab ketadi — bo'laklab yozamiz.
    for i in range(0, len(matn), 180):
        _cliclick("t:" + matn[i:i + 180])
        time.sleep(0.12)
    return {"ok": True, "belgi": len(matn)}


_TUGMA = {
    "enter": "return", "return": "return", "tab": "tab", "escape": "esc", "esc": "esc",
    "space": "space", "delete": "delete", "backspace": "delete", "forwarddelete": "fwd-delete",
    "up": "arrow-up", "down": "arrow-down", "left": "arrow-left", "right": "arrow-right",
    "arrowup": "arrow-up", "arrowdown": "arrow-down", "arrowleft": "arrow-left",
    "arrowright": "arrow-right", "pageup": "page-up", "pagedown": "page-down",
    "home": "home", "end": "end", "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f11": "f11", "f12": "f12",
}
_MODIFIKATOR = {"cmd": "cmd", "command": "cmd", "ctrl": "ctrl", "control": "ctrl",
                "alt": "alt", "option": "alt", "shift": "shift", "fn": "fn"}


def tugma(nom):
    """'enter', 'cmd+t', 'cmd+shift+4' kabi tugma birikmalarini bosadi."""
    xom = str(nom or "").strip().lower().replace(" ", "")
    if not xom:
        return {"ok": False, "sabab": "tugma nomi bo'sh"}
    bolaklar = [b for b in re.split(r"\+", xom) if b]
    modlar = [_MODIFIKATOR[b] for b in bolaklar if b in _MODIFIKATOR]
    qolgan = [b for b in bolaklar if b not in _MODIFIKATOR]
    asosiy = qolgan[-1] if qolgan else ""
    if modlar:
        _cliclick("kd:" + ",".join(modlar))
        try:
            if asosiy in _TUGMA:
                _cliclick("kp:" + _TUGMA[asosiy])
            elif asosiy:
                _cliclick("t:" + asosiy)
        finally:
            _cliclick("ku:" + ",".join(modlar))
    else:
        if asosiy in _TUGMA:
            _cliclick("kp:" + _TUGMA[asosiy])
        elif asosiy:
            _cliclick("t:" + asosiy)
        else:
            return {"ok": False, "sabab": "tugma tanilmadi: " + xom}
    time.sleep(0.3)
    return {"ok": True, "tugma": xom}


def aylantir(yon="pastga", miqdor=3):
    """cliclick'da alohida scroll buyrug'i yo'q — sahifa tugmalari bilan aylantiramiz."""
    n = max(1, min(int(miqdor), 20))
    kalit = "page-up" if str(yon).startswith(("yuq", "up")) else "page-down"
    for _ in range(n):
        _cliclick("kp:" + kalit)
        time.sleep(0.12)
    return {"ok": True, "yon": kalit, "marta": n}


def ilova_ochish(nom):
    nom = str(nom or "").strip()
    if not nom:
        return {"ok": False, "sabab": "ilova nomi bo'sh"}
    r = subprocess.run(["open", "-a", nom], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        return {"ok": False, "sabab": (r.stderr or "").strip()[:180] or "ilova topilmadi"}
    time.sleep(1.8)
    return {"ok": True, "ilova": nom}


def ilovalar():
    """Hozir ochiq (ko'rinadigan) ilovalar ro'yxati."""
    try:
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of every application process '
             'whose background only is false'],
            capture_output=True, text=True, timeout=12).stdout
        return [s.strip() for s in out.split(",") if s.strip()]
    except Exception:
        return []


def oldingi_ilova():
    try:
        return subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process '
             'whose frontmost is true'],
            capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""
