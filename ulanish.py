#!/usr/bin/env python3
"""Ulanishlar — printer, TV, telefon va Telegram.

Tamoyil: faqat haqiqatan ishlaydigan yo'l qo'shiladi. Parol so'raydigan yoki
saytning qoidasini buzadigan avtomatlashtirish bu yerda yo'q — bunday joyda
brauzer paneli ishlatiladi, foydalanuvchi o'zi kiradi.

Tasdiqlash usullari:
  · Android TV  — ekranda chiqadigan 6 xonali kod
  · Android tel — telefonda chiqadigan USB debug so'rovi
  · iPhone      — Mac bilan bir Apple ID (Messages/FaceTime orqali)
  · Telegram    — @BotFather bergan bot tokeni
"""
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request

LOYIHA = os.path.dirname(os.path.abspath(__file__))
SERTIFIKAT_PAPKA = os.path.join(LOYIHA, ".agy_tv")
QULF = threading.Lock()


def _yugur(argv, kutish=20):
    try:
        d = subprocess.run(argv, capture_output=True, text=True, timeout=kutish)
        return (d.stdout or "").strip(), (d.stderr or "").strip(), d.returncode
    except FileNotFoundError:
        return "", "buyruq topilmadi: " + argv[0], 127
    except subprocess.TimeoutExpired:
        return "", "vaqt tugadi", 124


# ─────────────────────────────────── Printer ─────────────────────────────────
def printerlar():
    """Mac'ga ulangan printerlar. macOS CUPS ni ishlatadi — sozlash kerak emas."""
    chiqish, _, kod = _yugur(["lpstat", "-p", "-d"])
    if kod != 0:
        return []
    standart = ""
    royxat = []
    for qator in chiqish.splitlines():
        if qator.startswith("printer "):
            bolaklar = qator.split()
            nom = bolaklar[1]
            band = "printing" in qator
            oflayn = "disabled" in qator
            royxat.append({"nom": nom, "holat": "chop etyapti" if band else
                           ("o'chiq" if oflayn else "tayyor"), "standart": False})
        elif "system default destination:" in qator:
            standart = qator.split(":", 1)[1].strip()
    for p in royxat:
        p["standart"] = (p["nom"] == standart)
        # Chek printerlari odatda nomida POS/receipt/58/80 bo'ladi.
        p["chek"] = bool(re.search(r"pos|receipt|chek|58|80", p["nom"], re.I))
    return royxat


def chop_et(matn="", fayl="", printer="", nusxa=1):
    """Matn yoki faylni chop etadi."""
    argv = ["lp"]
    if printer:
        argv += ["-d", printer]
    if int(nusxa) > 1:
        argv += ["-n", str(int(nusxa))]
    if fayl:
        yol = os.path.expanduser(fayl)
        if not os.path.isfile(yol):
            return {"ok": False, "sabab": "fayl topilmadi: " + yol}
        chiqish, xato, kod = _yugur(argv + [yol], 60)
    else:
        if not str(matn).strip():
            return {"ok": False, "sabab": "chop etiladigan narsa yo'q"}
        try:
            d = subprocess.run(argv, input=str(matn), capture_output=True,
                               text=True, timeout=60)
            chiqish, xato, kod = (d.stdout or "").strip(), (d.stderr or "").strip(), d.returncode
        except Exception as exc:
            return {"ok": False, "sabab": str(exc)[:200]}
    if kod != 0:
        return {"ok": False, "sabab": xato or "chop etilmadi"}
    return {"ok": True, "javob": chiqish or "yuborildi"}


# ────────────────────────────── Tarmoqdagi qurilmalar ────────────────────────
XIZMATLAR = {
    "_androidtvremote2._tcp.local.": "Android TV",
    "_googlecast._tcp.local.": "Chromecast / Google TV",
    "_airplay._tcp.local.": "AirPlay (Apple TV)",
    "_ipp._tcp.local.": "Tarmoq printeri",
}


def qurilmalar(soniya=6):
    """Wi-Fi dagi qurilmalarni Bonjour orqali topadi."""
    try:
        from zeroconf import Zeroconf, ServiceBrowser
    except ImportError:
        return []
    topildi = {}

    class Kuzatuvchi:
        def add_service(self, zc, tur, nom):
            try:
                info = zc.get_service_info(tur, nom, timeout=2500)
            except Exception:
                return
            ip = ""
            if info and info.addresses:
                try:
                    ip = socket.inet_ntoa(info.addresses[0])
                except Exception:
                    pass
            sof = nom.replace(tur, "").rstrip(".")
            topildi[(sof, tur)] = {
                "nom": sof, "tur": XIZMATLAR.get(tur, tur),
                "ip": ip, "port": info.port if info else 0,
                "boshqariladi": tur == "_androidtvremote2._tcp.local.",
            }

        def update_service(self, *a):
            pass

        def remove_service(self, *a):
            pass

    zc = Zeroconf()
    try:
        for tur in XIZMATLAR:
            ServiceBrowser(zc, tur, Kuzatuvchi())
        time.sleep(max(3, min(int(soniya), 15)))
    finally:
        try:
            zc.close()
        except Exception:
            pass
    return sorted(topildi.values(), key=lambda d: (d["tur"], d["nom"]))


# ───────────────────────────────── Android TV ────────────────────────────────
def _tv_sertifikat():
    os.makedirs(SERTIFIKAT_PAPKA, exist_ok=True)
    return (os.path.join(SERTIFIKAT_PAPKA, "cert.pem"),
            os.path.join(SERTIFIKAT_PAPKA, "key.pem"))


_TV_HOLAT = {"remote": None, "host": "", "loop": None, "thread": None}


def _tv_loop():
    """Kutubxona asyncio da ishlaydi — unga alohida doim yuruvchi loop beramiz."""
    import asyncio
    if _TV_HOLAT["loop"] and _TV_HOLAT["loop"].is_running():
        return _TV_HOLAT["loop"]
    loop = asyncio.new_event_loop()

    def yur():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    t = threading.Thread(target=yur, daemon=True)
    t.start()
    _TV_HOLAT["loop"], _TV_HOLAT["thread"] = loop, t
    time.sleep(0.2)
    return loop


def _tv_kut(coro, kutish=45):
    import asyncio
    loop = _tv_loop()
    kel = asyncio.run_coroutine_threadsafe(coro, loop)
    return kel.result(timeout=kutish)


def _tv_yasa(host):
    from androidtvremote2 import AndroidTVRemote
    cert, key = _tv_sertifikat()
    return AndroidTVRemote("MuhasibPro", cert, key, host)


def tv_ulanish_boshla(host):
    """1-qadam: TV ekranida 6 xonali kod chiqadi."""
    with QULF:
        try:
            remote = _tv_yasa(host)
            _tv_kut(remote.async_generate_cert_if_missing())
            try:
                _tv_kut(remote.async_connect(), 20)
                _TV_HOLAT.update({"remote": remote, "host": host})
                return {"ok": True, "kod_kerak": False,
                        "xabar": "TV allaqachon ulangan — kod kerak emas."}
            except Exception:
                pass
            _tv_kut(remote.async_start_pairing(), 30)
            _TV_HOLAT.update({"remote": remote, "host": host})
            return {"ok": True, "kod_kerak": True,
                    "xabar": "TV ekranida 6 xonali kod chiqdi. Shu kodni kiriting."}
        except Exception as exc:
            return {"ok": False, "sabab": str(exc)[:220]}


def tv_ulanish_tugat(kod):
    """2-qadam: TV ekranidagi kodni tasdiqlaydi."""
    with QULF:
        remote = _TV_HOLAT.get("remote")
        if remote is None:
            return {"ok": False, "sabab": "Avval ulanishni boshlang."}
        try:
            _tv_kut(remote.async_finish_pairing(str(kod).strip()), 30)
            _tv_kut(remote.async_connect(), 25)
            return {"ok": True, "xabar": "TV ulandi. Endi boshqarsa bo'ladi."}
        except Exception as exc:
            return {"ok": False, "sabab": str(exc)[:220]}


TV_TUGMALAR = {
    "yoqish": "POWER", "power": "POWER", "uy": "HOME", "home": "HOME",
    "orqaga": "BACK", "back": "BACK", "ok": "DPAD_CENTER", "tanlash": "DPAD_CENTER",
    "yuqoriga": "DPAD_UP", "pastga": "DPAD_DOWN", "chapga": "DPAD_LEFT",
    "ongga": "DPAD_RIGHT", "ovoz+": "VOLUME_UP", "ovoz-": "VOLUME_DOWN",
    "ovozsiz": "MUTE", "play": "MEDIA_PLAY_PAUSE", "toxtat": "MEDIA_PAUSE",
    "keyingi": "MEDIA_NEXT", "oldingi": "MEDIA_PREVIOUS",
}


def tv_buyruq(nom="", matn="", ilova="", url=""):
    """Ulangan TV ga buyruq yuboradi."""
    remote = _TV_HOLAT.get("remote")
    if remote is None:
        return {"ok": False, "sabab": "TV ulanmagan. Avval sozlamalardan ulang."}
    try:
        if url:
            _tv_kut(remote.async_connect(), 15) if not remote.is_on else None
            remote.send_launch_app_command(url)
            return {"ok": True, "xabar": "TV da ochildi: " + url}
        if ilova:
            remote.send_launch_app_command(ilova)
            return {"ok": True, "xabar": "Ilova ochildi: " + ilova}
        if matn:
            remote.send_text(matn)
            return {"ok": True, "xabar": "Matn yuborildi."}
        kalit = TV_TUGMALAR.get(str(nom).strip().lower(), str(nom).strip().upper())
        remote.send_key_command(kalit)
        return {"ok": True, "xabar": "Bosildi: " + kalit}
    except Exception as exc:
        return {"ok": False, "sabab": str(exc)[:220]}


def tv_holat():
    remote = _TV_HOLAT.get("remote")
    if remote is None:
        return {"ulangan": False}
    try:
        return {"ulangan": True, "host": _TV_HOLAT.get("host", ""),
                "yoqiq": bool(remote.is_on), "ilova": remote.current_app or ""}
    except Exception:
        return {"ulangan": True, "host": _TV_HOLAT.get("host", "")}


# ─────────────────────────────────── Telefon ─────────────────────────────────
def _applescript(kod, kutish=30):
    try:
        d = subprocess.run(["osascript", "-e", kod], capture_output=True,
                           text=True, timeout=kutish)
        return (d.stdout or "").strip(), (d.stderr or "").strip(), d.returncode
    except Exception as exc:
        return "", str(exc)[:200], 1


def iphone_holat():
    """Messages orqali xabar yuborish mumkinmi."""
    chiqish, _, kod = _applescript(
        'tell application "System Events" to return (exists application process "Messages")')
    ochiq = chiqish.lower() == "true"
    bor = os.path.isdir("/System/Applications/Messages.app")
    return {"messages_bor": bor, "ochiq": ochiq}


def sms_yuborish(raqam, matn):
    """Messages orqali SMS/iMessage yuboradi.

    Mac bilan iPhone bir Apple ID da bo'lishi va iPhone'da
    "Sozlamalar → Xabarlar → SMS uzatish" yoqilgan bo'lishi kerak.
    """
    raqam = str(raqam or "").strip()
    matn = str(matn or "")
    if not raqam or not matn:
        return {"ok": False, "sabab": "raqam yoki matn bo'sh"}
    xavfsiz = matn.replace("\\", "\\\\").replace('"', '\\"')
    kod = ('tell application "Messages"\n'
           '  set maqsad to a reference to (1st account whose service type = iMessage)\n'
           '  try\n'
           '    send "%s" to participant "%s" of maqsad\n'
           '  on error\n'
           '    set sms to 1st account whose service type = SMS\n'
           '    send "%s" to participant "%s" of sms\n'
           '  end try\n'
           'end tell' % (xavfsiz, raqam, xavfsiz, raqam))
    _, xato, kod_qaytdi = _applescript(kod, 40)
    if kod_qaytdi != 0:
        return {"ok": False, "sabab": (xato or "yuborilmadi")[:250]}
    return {"ok": True, "kimga": raqam}


def qongiroq_qilish(raqam):
    """FaceTime orqali qo'ng'iroq boshlaydi — iPhone orqali ketadi."""
    raqam = re.sub(r"[^\d+]", "", str(raqam or ""))
    if not raqam:
        return {"ok": False, "sabab": "raqam bo'sh"}
    chiqish, xato, kod = _yugur(["open", "tel://" + raqam], 15)
    if kod != 0:
        return {"ok": False, "sabab": xato or "qo'ng'iroq boshlanmadi"}
    return {"ok": True, "raqam": raqam,
            "xabar": "FaceTime ochildi. Qo'ng'iroqni tasdiqlash oynada bo'ladi."}


# ─────────────────────────────── Android telefon ─────────────────────────────
def android_holat():
    adb = shutil.which("adb")
    if not adb:
        return {"adb": False, "qurilmalar": []}
    chiqish, _, _ = _yugur([adb, "devices", "-l"], 15)
    qurilma = []
    for qator in chiqish.splitlines()[1:]:
        if not qator.strip():
            continue
        bolaklar = qator.split()
        holat = bolaklar[1] if len(bolaklar) > 1 else "?"
        model = ""
        mos = re.search(r"model:(\S+)", qator)
        if mos:
            model = mos.group(1)
        qurilma.append({"id": bolaklar[0], "holat": holat, "model": model})
    return {"adb": True, "qurilmalar": qurilma}


def android_sms(raqam, matn, qurilma=""):
    """Android telefondan SMS yuboradi (USB debug yoqilgan bo'lishi kerak)."""
    adb = shutil.which("adb")
    if not adb:
        return {"ok": False, "sabab": "adb o'rnatilmagan. Terminalda: brew install android-platform-tools"}
    argv = [adb]
    if qurilma:
        argv += ["-s", qurilma]
    argv += ["shell", "am", "start", "-a", "android.intent.action.SENDTO",
             "-d", "sms:" + str(raqam), "--es", "sms_body", str(matn),
             "--ez", "exit_on_sent", "true"]
    _, xato, kod = _yugur(argv, 25)
    if kod != 0:
        return {"ok": False, "sabab": xato[:220] or "yuborilmadi"}
    return {"ok": True, "xabar": "SMS oynasi telefonda ochildi — yuborishni tasdiqlang."}


# ─────────────────────────────────── Telegram ────────────────────────────────
def telegram_token():
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def telegram_holat():
    token = telegram_token()
    if not token:
        return {"ulangan": False}
    try:
        with urllib.request.urlopen(
                "https://api.telegram.org/bot%s/getMe" % token, timeout=15) as javob:
            d = json.loads(javob.read())
        if d.get("ok"):
            bot = d.get("result") or {}
            return {"ulangan": True, "bot": bot.get("username", ""),
                    "nom": bot.get("first_name", "")}
    except Exception as exc:
        return {"ulangan": False, "xato": str(exc)[:150]}
    return {"ulangan": False}


def telegram_suhbatlar():
    """Botga yozgan odamlar va guruhlar. Bot faqat o'ziga yozilganini ko'radi."""
    token = telegram_token()
    if not token:
        return []
    try:
        with urllib.request.urlopen(
                "https://api.telegram.org/bot%s/getUpdates?limit=100" % token,
                timeout=20) as javob:
            d = json.loads(javob.read())
    except Exception:
        return []
    korilgan, royxat = set(), []
    for yangilanish in (d.get("result") or []):
        xabar = yangilanish.get("message") or yangilanish.get("channel_post") or {}
        suhbat = xabar.get("chat") or {}
        cid = suhbat.get("id")
        if not cid or cid in korilgan:
            continue
        korilgan.add(cid)
        nom = (suhbat.get("title") or
               " ".join(x for x in (suhbat.get("first_name"), suhbat.get("last_name")) if x) or
               suhbat.get("username") or str(cid))
        royxat.append({"id": cid, "nom": nom, "tur": suhbat.get("type", "")})
    return royxat


def telegram_yuborish(kimga, matn):
    """Telegram orqali xabar yuboradi. `kimga` — chat id yoki @username."""
    token = telegram_token()
    if not token:
        return {"ok": False, "sabab": "Telegram boti ulanmagan. Sozlamalardan token qo'shing."}
    kimga = str(kimga or "").strip()
    if not kimga or not str(matn or "").strip():
        return {"ok": False, "sabab": "qabul qiluvchi yoki matn bo'sh"}
    tana = urllib.parse.urlencode({"chat_id": kimga, "text": str(matn)}).encode()
    try:
        so_rov = urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % token, data=tana, method="POST")
        with urllib.request.urlopen(so_rov, timeout=25) as javob:
            d = json.loads(javob.read())
    except urllib.error.HTTPError as xato:
        xabar = xato.read().decode("utf-8", "replace")[:250]
        if "chat not found" in xabar.lower():
            return {"ok": False, "sabab": "Suhbat topilmadi. Bu odam avval botingizga "
                                          "bir marta yozishi kerak — Telegram shunday ishlaydi."}
        return {"ok": False, "sabab": xabar}
    except Exception as exc:
        return {"ok": False, "sabab": str(exc)[:220]}
    if not d.get("ok"):
        return {"ok": False, "sabab": str(d.get("description"))[:220]}
    return {"ok": True, "kimga": kimga}


# ─────────────────────────── Kalendar va eslatmalar ──────────────────────────
def _as_xavfsiz(matn):
    return str(matn or "").replace("\\", "\\\\").replace('"', '\\"')


def kalendar_yozish(sarlavha, sana, soat="", davomiylik=60, izoh="", kalendar=""):
    """macOS Kalendariga voqea qo'shadi (iCloud bilan telefonga ham o'tadi).

    `sana` — YYYY-MM-DD, `soat` — HH:MM. Soat berilmasa kun bo'yi voqea.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(sana or "").strip()):
        return {"ok": False, "sabab": "sana YYYY-MM-DD ko'rinishida bo'lsin"}
    yil, oy, kun = str(sana).split("-")
    s, d = (soat.split(":") + ["0"])[:2] if re.match(r"^\d{1,2}:\d{2}$", str(soat or "")) else ("9", "0")
    kod = (
        'set boshlanish to (current date)\n'
        'set year of boshlanish to %s\n'
        'set month of boshlanish to %s\n'
        'set day of boshlanish to %s\n'
        'set hours of boshlanish to %s\n'
        'set minutes of boshlanish to %s\n'
        'set seconds of boshlanish to 0\n'
        'tell application "Calendar"\n'
        '  set kal to (first calendar whose name is "%s")\n'
        '  tell kal to make new event with properties '
        '{summary:"%s", start date:boshlanish, end date:(boshlanish + %d * minutes), description:"%s"}\n'
        'end tell'
        % (int(yil), int(oy), int(kun), int(s), int(d),
           _as_xavfsiz(kalendar) if kalendar else "Calendar",
           _as_xavfsiz(sarlavha), max(5, int(davomiylik)), _as_xavfsiz(izoh))
    )
    _, xato, kod_q = _applescript(kod, 30)
    if kod_q != 0:
        # Standart kalendar nomi boshqacha bo'lishi mumkin — birinchisiga yozamiz.
        kod2 = kod.replace('(first calendar whose name is "%s")'
                           % (_as_xavfsiz(kalendar) if kalendar else "Calendar"),
                           'first calendar')
        _, xato2, kod_q2 = _applescript(kod2, 30)
        if kod_q2 != 0:
            return {"ok": False, "sabab": (xato2 or xato)[:220]}
    return {"ok": True, "sarlavha": sarlavha, "sana": sana, "soat": soat or "09:00"}


def eslatma_yozish(matn, sana="", soat=""):
    """macOS Eslatmalar (Reminders) ga qo'shadi."""
    if not str(matn or "").strip():
        return {"ok": False, "sabab": "matn bo'sh"}
    if sana and re.match(r"^\d{4}-\d{2}-\d{2}$", sana):
        yil, oy, kun = sana.split("-")
        s, d = (soat.split(":") + ["0"])[:2] if re.match(r"^\d{1,2}:\d{2}$", str(soat or "")) else ("9", "0")
        kod = ('set muddat to (current date)\n'
               'set year of muddat to %s\nset month of muddat to %s\nset day of muddat to %s\n'
               'set hours of muddat to %s\nset minutes of muddat to %s\nset seconds of muddat to 0\n'
               'tell application "Reminders" to make new reminder with properties '
               '{name:"%s", due date:muddat}'
               % (int(yil), int(oy), int(kun), int(s), int(d), _as_xavfsiz(matn)))
    else:
        kod = ('tell application "Reminders" to make new reminder with properties {name:"%s"}'
               % _as_xavfsiz(matn))
    _, xato, kod_q = _applescript(kod, 25)
    if kod_q != 0:
        return {"ok": False, "sabab": xato[:220]}
    return {"ok": True, "matn": matn, "muddat": (sana + " " + (soat or "")).strip() or "muddatsiz"}


def kalendar_kun(sana=""):
    """Berilgan kundagi voqealar."""
    kod = ('tell application "Calendar"\n'
           '  set bugun to (current date)\n'
           '  set time of bugun to 0\n'
           '  set ertaga to bugun + 1 * days\n'
           '  set natija to ""\n'
           '  repeat with k in calendars\n'
           '    repeat with v in (every event of k whose start date ≥ bugun and start date < ertaga)\n'
           '      set natija to natija & (summary of v) & " — " & (start date of v as string) & linefeed\n'
           '    end repeat\n'
           '  end repeat\n'
           '  return natija\n'
           'end tell')
    chiqish, xato, kod_q = _applescript(kod, 45)
    if kod_q != 0:
        return {"ok": False, "sabab": xato[:220]}
    qatorlar = [q.strip() for q in chiqish.splitlines() if q.strip()]
    return {"ok": True, "voqealar": qatorlar}


# ───────────────────────────────────── Pochta ────────────────────────────────
def pochta_yuborish(kimga, mavzu, matn, biriktirma=""):
    """macOS Mail orqali xat yuboradi — Mail'da sozlangan hisobdan ketadi."""
    if not str(kimga or "").strip() or not str(matn or "").strip():
        return {"ok": False, "sabab": "manzil yoki matn bo'sh"}
    qismlar = [
        'tell application "Mail"',
        '  set yangi to make new outgoing message with properties '
        '{subject:"%s", content:"%s", visible:false}' % (_as_xavfsiz(mavzu), _as_xavfsiz(matn)),
        '  tell yangi to make new to recipient at end of to recipients '
        'with properties {address:"%s"}' % _as_xavfsiz(kimga),
    ]
    if biriktirma:
        yol = os.path.expanduser(biriktirma)
        if not os.path.isfile(yol):
            return {"ok": False, "sabab": "biriktirma topilmadi: " + yol}
        qismlar.append('  tell yangi to make new attachment with properties '
                       '{file name:(POSIX file "%s")} at after last paragraph' % _as_xavfsiz(yol))
    qismlar += ['  send yangi', 'end tell']
    _, xato, kod = _applescript("\n".join(qismlar), 60)
    if kod != 0:
        return {"ok": False, "sabab": (xato or "yuborilmadi")[:250] +
                "\nMail ilovasida hech bo'lmasa bitta hisob sozlangan bo'lishi kerak."}
    return {"ok": True, "kimga": kimga}


def pochta_holat():
    chiqish, _, _ = _applescript('tell application "Mail" to return (count of accounts)', 20)
    try:
        soni = int(chiqish or "0")
    except ValueError:
        soni = 0
    return {"bor": os.path.isdir("/System/Applications/Mail.app"), "hisoblar": soni}


# ─────────────────────────────── Valyuta kurslari ────────────────────────────
_KURS = {"vaqt": 0.0, "malumot": []}


def kurslar(valyuta=""):
    """O'zbekiston Markaziy bankidan rasmiy kurs. Kassa valyutalari uchun."""
    if time.time() - _KURS["vaqt"] > 3600 or not _KURS["malumot"]:
        try:
            so_rov = urllib.request.Request(
                "https://cbu.uz/uz/arkhiv-kursov-valyut/json/",
                headers={"User-Agent": "MuhasibPro/1.0"})
            with urllib.request.urlopen(so_rov, timeout=20) as javob:
                _KURS["malumot"] = json.loads(javob.read().decode("utf-8"))
            _KURS["vaqt"] = time.time()
        except Exception as exc:
            return {"ok": False, "sabab": str(exc)[:200]}
    royxat = _KURS["malumot"]
    if valyuta:
        kod = str(valyuta).strip().upper()
        topildi = [v for v in royxat if v.get("Ccy") == kod]
        if not topildi:
            return {"ok": False, "sabab": "bunday valyuta yo'q: " + kod}
        v = topildi[0]
        return {"ok": True, "valyuta": kod, "nom": v.get("CcyNm_UZ", ""),
                "kurs": v.get("Rate", ""), "sana": v.get("Date", ""),
                "ozgarish": v.get("Diff", "")}
    asosiy = [v for v in royxat if v.get("Ccy") in ("USD", "EUR", "RUB", "KZT", "CNY")]
    return {"ok": True, "sana": (asosiy[0].get("Date") if asosiy else ""),
            "kurslar": [{"valyuta": v["Ccy"], "nom": v.get("CcyNm_UZ", ""),
                         "kurs": v.get("Rate"), "ozgarish": v.get("Diff")} for v in asosiy]}


# ───────────────────────────────────── Excel ─────────────────────────────────
def excel_oqish(yol, varaq="", chegara=300):
    """.xlsx faylni o'qiydi."""
    yol = os.path.expanduser(str(yol or ""))
    if not os.path.isfile(yol):
        return {"ok": False, "sabab": "fayl topilmadi: " + yol}
    try:
        import openpyxl
        kitob = openpyxl.load_workbook(yol, data_only=True, read_only=True)
        nomlar = kitob.sheetnames
        varaq_obj = kitob[varaq] if varaq and varaq in nomlar else kitob[nomlar[0]]
        qatorlar = []
        for i, qator in enumerate(varaq_obj.iter_rows(values_only=True)):
            if i >= chegara:
                break
            qatorlar.append(["" if h is None else h for h in qator])
        kitob.close()
        return {"ok": True, "varaqlar": nomlar, "varaq": varaq_obj.title, "qatorlar": qatorlar}
    except Exception as exc:
        return {"ok": False, "sabab": str(exc)[:220]}


def excel_yozish(yol, qatorlar, varaq="Varaq1"):
    """Yangi .xlsx yaratadi yoki mavjudiga varaq qo'shadi."""
    yol = os.path.expanduser(str(yol or ""))
    if not yol.endswith(".xlsx"):
        yol += ".xlsx"
    try:
        import openpyxl
        if os.path.isfile(yol):
            kitob = openpyxl.load_workbook(yol)
            varaq_obj = kitob.create_sheet(varaq) if varaq not in kitob.sheetnames else kitob[varaq]
        else:
            kitob = openpyxl.Workbook()
            varaq_obj = kitob.active
            varaq_obj.title = varaq
        for qator in qatorlar:
            varaq_obj.append(list(qator))
        os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
        kitob.save(yol)
        return {"ok": True, "yol": yol, "qator": len(qatorlar)}
    except Exception as exc:
        return {"ok": False, "sabab": str(exc)[:220]}


# ──────────────────────────────── Umumiy holat ───────────────────────────────
def holat():
    """Sozlamalar paneli shu bilan oziqlanadi."""
    p = printerlar()
    try:
        import jadval
        sheets = jadval.holat()
    except Exception:
        sheets = {"ulangan": False}
    return {
        "printer": {"soni": len(p), "royxat": p,
                    "chek": next((x["nom"] for x in p if x.get("chek")), "")},
        "tv": tv_holat(),
        "iphone": iphone_holat(),
        "android": android_holat(),
        "telegram": telegram_holat(),
        "sheets": sheets,
        "pochta": pochta_holat(),
        "kalendar": {"bor": os.path.isdir("/System/Applications/Calendar.app"),
                     "eslatma": os.path.isdir("/System/Applications/Reminders.app")},
    }
