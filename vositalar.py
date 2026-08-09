#!/usr/bin/env python3
"""Agentning qo'shimcha vositalari: brauzer, ekran, reja, web va rasm.

agy_app.py dagi asosiy vositalar (fayl, terminal, hisob-kitob) o'z joyida qoldi.
Bu yerda faqat yangi qobiliyatlar — shuning uchun asosiy fayl shishmaydi.

`ishlat()` vositani bajaradi va (yorliq, izoh, model_uchun_natija) qaytaradi.
Vosita bu modulga tegishli bo'lmasa None qaytaradi — chaqiruvchi o'zi davom etadi.

`sink` — chaqiruvchiga qaytadigan yon kanal:
    sink["image"]   → shu rasm modelga ko'rsatiladi (ekran/brauzer skrini)
    sink["reja"]    → interfeysdagi jonli reja paneli
    sink["brauzer"] → interfeysdagi brauzer paneli uchun holat
"""
import glob as _glob
import html as _html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import brauzer
import ekran
import ulanish

CHEGARA = 24000
# agy_app.py ishga tushganda to'ldiradi — aylanma importdan qochish uchun.
KALIT = None          # () -> OpenAI API kaliti
YORDAMCHI = None      # (vazifa, cwd) -> matn
KUTISH = None         # (soniya, izoh) -> bool: foydalanuvchi "davom et" bosdimi
TEKSHIR = None        # (yol) -> sintaksis xatosi matni yoki ""
QATOR_FARQI = None    # (eski, yangi) -> (qoshildi, ochirildi)
LOYIHA = os.path.dirname(os.path.abspath(__file__))


def _qirq(matn, chegara=CHEGARA):
    matn = matn or ""
    if len(matn) <= chegara:
        return matn
    return matn[:chegara] + "\n… (natija qisqartirildi, jami %d belgi)" % len(matn)


def _yol(cwd, path):
    t = os.path.expanduser(str(path or "").strip())
    if not t:
        return cwd
    return os.path.abspath(t if os.path.isabs(t) else os.path.join(cwd, t))


# ─────────────────────────────────── Brauzer ─────────────────────────────────
def _brauzer_holat(sink, qadam=""):
    b = brauzer.sessiya()
    holat = {"url": b.oxirgi_url, "sarlavha": b.oxirgi_sarlavha, "qadam": qadam}
    if sink is not None:
        sink["brauzer"] = holat
    return holat


def _brauzer(name, args, cwd, sink):
    b = brauzer.sessiya()

    if name == "brauzer_och":
        url = str(args.get("url") or "").strip()
        holat = b.och(url)
        matn, _ = b.oqi()
        _brauzer_holat(sink, "ochildi: " + holat.get("url", ""))
        return ("🌐 Sayt ochildi · " + (holat.get("sarlavha") or url)[:60],
                holat.get("url", "")[:70],
                "Sahifa ochildi.\n\n" + _qirq(matn))

    if name == "brauzer_oqish":
        matn, d = b.oqi(faqat_matn=bool(args.get("faqat_matn")))
        _brauzer_holat(sink, "sahifa o'qildi")
        return ("👁️ Sahifa o'qildi · " + (d.get("sarlavha") or "")[:55],
                "%d element" % len(d.get("elementlar") or []),
                _qirq(matn))

    if name == "brauzer_bosish":
        r = b.bos(ref=str(args.get("ref") or ""), matn=str(args.get("matn") or ""),
                  selector=str(args.get("selector") or ""))
        if not r.get("ok"):
            _brauzer_holat(sink, "bosish muvaffaqiyatsiz")
            return ("🖱️ Bosildi", "topilmadi",
                    "XATO: element topilmadi. Avval `brauzer_oqish` bilan ref larni ol.")
        matn, _ = b.oqi()
        _brauzer_holat(sink, "bosildi: " + r.get("nom", ""))
        return ("🖱️ Bosildi · " + (r.get("nom") or "element")[:55],
                r.get("url", "")[:60],
                "Bosildi. Bosgandan keyingi sahifa:\n\n" + _qirq(matn))

    if name == "brauzer_yozish":
        matn_yoz = str(args.get("matn") or "")
        past = matn_yoz.lower()
        r = b.yoz(matn_yoz, ref=str(args.get("ref") or ""),
                  selector=str(args.get("selector") or ""),
                  tozala=args.get("tozala") is not False,
                  enter=bool(args.get("enter")))
        if not r.get("ok"):
            return ("⌨️ Maydonga yozildi", "topilmadi",
                    "XATO: maydon topilmadi. Avval `brauzer_oqish` bilan ref ni ol.")
        sahifa, _ = b.oqi()
        _brauzer_holat(sink, "yozildi")
        return ("⌨️ Maydonga yozildi · " + matn_yoz[:40],
                "enter" if args.get("enter") else "%d belgi" % len(matn_yoz),
                "Yozildi. Hozirgi sahifa:\n\n" + _qirq(sahifa))

    if name == "brauzer_tugma":
        b.tugma(str(args.get("tugma") or "Enter"))
        time.sleep(0.6)
        sahifa, _ = b.oqi()
        _brauzer_holat(sink, "tugma: " + str(args.get("tugma")))
        return ("⌨️ Tugma · " + str(args.get("tugma")), "bosildi",
                "Tugma bosildi. Hozirgi sahifa:\n\n" + _qirq(sahifa))

    if name == "brauzer_aylantirish":
        r = b.aylantir(str(args.get("yon") or "pastga"), int(args.get("miqdor") or 600))
        sahifa, _ = b.oqi()
        _brauzer_holat(sink, "aylantirildi")
        return ("↕️ Sahifa aylantirildi", str(r.get("scroll", "")),
                _qirq(sahifa))

    if name == "brauzer_kutish":
        r = b.kut(matn=str(args.get("matn") or ""), selector=str(args.get("selector") or ""),
                  soniya=int(args.get("soniya") or 15))
        sahifa, _ = b.oqi()
        return ("⏳ Kutildi", "topildi" if r.get("ok") else "vaqt tugadi",
                ("Kutilgan narsa paydo bo'ldi.\n\n" if r.get("ok")
                 else "Kutish vaqti tugadi — sahifa hozircha shunday:\n\n") + _qirq(sahifa))

    if name == "brauzer_skrin":
        papka = os.path.join(LOYIHA, ".agy_uploads")
        yol = b.skrin_fayl(papka)
        if sink is not None:
            sink["image"] = yol
        _brauzer_holat(sink, "skrinshot olindi")
        return ("📸 Brauzer skrinshoti", os.path.basename(yol),
                "Skrinshot olindi va senga rasm sifatida ko'rsatildi: " + yol)

    if name == "brauzer_js":
        natija = b.js(str(args.get("kod") or ""))
        _brauzer_holat(sink, "JS bajarildi")
        return ("🧪 Sahifada JS bajarildi", "ok",
                _qirq(json.dumps(natija, ensure_ascii=False) if not isinstance(natija, str) else natija))

    if name == "brauzer_login_kutish":
        if KUTISH is None:
            return ("🔐 Kirish kutilmoqda", "mavjud emas",
                    "XATO: kutish mexanizmi ulanmagan. Foydalanuvchidan qo'lda kirishni so'ra.")
        izoh = str(args.get("izoh") or "").strip() or "Saytga kirishingiz kerak."
        soniya = max(30, min(int(args.get("soniya") or 300), 900))
        _brauzer_holat(sink, "kirish kutilmoqda")
        bosildi = KUTISH(soniya, izoh)
        matn, _ = b.oqi()
        if not bosildi:
            return ("🔐 Kirish kutildi", "javob kelmadi",
                    "Foydalanuvchi %d soniyada tasdiqlamadi. Sahifaning hozirgi holati:\n\n%s\n\n"
                    "Kirish bo'lmagan bo'lsa ishni to'xtat va foydalanuvchiga ayt."
                    % (soniya, _qirq(matn, 6000)))
        _brauzer_holat(sink, "kirish tasdiqlandi")
        return ("🔐 Kirish tasdiqlandi", "davom etamiz",
                "Foydalanuvchi kirdi va davom etishga ruxsat berdi. Hozirgi sahifa:\n\n" + _qirq(matn))

    if name == "brauzer_orqaga":
        h = b.orqaga()
        sahifa, _ = b.oqi()
        _brauzer_holat(sink, "orqaga qaytildi")
        return ("↩️ Orqaga qaytildi · " + (h.get("sarlavha") or "")[:50],
                h.get("url", "")[:60], _qirq(sahifa))

    return None


# ──────────────────────────────────── Ekran ──────────────────────────────────
def _ekran(name, args, cwd, sink):
    if name == "ekran_korish":
        papka = os.path.join(LOYIHA, ".agy_uploads")
        yol, xato = ekran.skrin(papka)
        if not yol:
            return ("🖥️ Ekran ko'rildi", "ruxsat yo'q", "XATO: " + xato)
        if sink is not None:
            sink["image"] = yol
        w, h = ekran.olcham()
        return ("🖥️ Ekran ko'rildi · " + (ekran.oldingi_ilova() or "?"),
                "%dx%d" % (w, h),
                ("Ekran rasmi senga ko'rsatildi. O'lcham: %d×%d nuqta — rasmda ko'rgan "
                 "koordinatani to'g'ridan-to'g'ri `ekran_bosish` ga bera olasan.\n"
                 "Oldingi ilova: %s\nOchiq ilovalar: %s"
                 % (w, h, ekran.oldingi_ilova() or "?", ", ".join(ekran.ilovalar()[:12]))))

    if name == "ekran_bosish":
        r = ekran.bos(args.get("x"), args.get("y"), str(args.get("tur") or "chap"),
                      int(args.get("marta") or 1))
        return ("🖱️ Ekranda bosildi · %d,%d" % (r["x"], r["y"]), str(args.get("tur") or "chap"),
                "Bosildi (%d,%d). Natijani ko'rish uchun `ekran_korish` chaqir." % (r["x"], r["y"]))

    if name == "ekran_yozish":
        r = ekran.yoz(args.get("matn"))
        if not r.get("ok"):
            return ("⌨️ Ekranga yozildi", "bo'sh", "XATO: matn bo'sh.")
        return ("⌨️ Ekranga yozildi · " + str(args.get("matn"))[:40],
                "%d belgi" % r["belgi"], "Yozildi.")

    if name == "ekran_tugma":
        r = ekran.tugma(args.get("tugma"))
        if not r.get("ok"):
            return ("⌨️ Tugma", "tanilmadi", "XATO: " + str(r.get("sabab")))
        return ("⌨️ Tugma · " + r["tugma"], "bosildi", "Bosildi: " + r["tugma"])

    if name == "ekran_aylantirish":
        r = ekran.aylantir(str(args.get("yon") or "pastga"), int(args.get("miqdor") or 3))
        return ("↕️ Ekran aylantirildi", r.get("yon", ""), "Aylantirildi.")

    if name == "ilova_ochish":
        r = ekran.ilova_ochish(args.get("nom"))
        if not r.get("ok"):
            return ("📱 Ilova ochildi", "topilmadi", "XATO: " + str(r.get("sabab")))
        return ("📱 Ilova ochildi · " + r["ilova"], "oldinga chiqdi",
                "Ochildi: %s. Endi `ekran_korish` bilan holatni ko'r." % r["ilova"])

    return None


# ───────────────────────────────────── Reja ──────────────────────────────────
def _reja(name, args, cwd, sink):
    if name != "reja_yozish":
        return None
    xom = args.get("qadamlar") or []
    qadamlar = []
    for q in xom:
        if isinstance(q, str):
            qadamlar.append({"matn": q, "holat": "kutmoqda"})
        elif isinstance(q, dict):
            holat = str(q.get("holat") or "kutmoqda").strip().lower()
            if holat not in ("kutmoqda", "ishlanmoqda", "tayyor"):
                holat = "kutmoqda"
            qadamlar.append({"matn": str(q.get("matn") or "").strip(), "holat": holat})
    qadamlar = [q for q in qadamlar if q["matn"]][:14]
    if not qadamlar:
        return ("🗒️ Reja", "bo'sh", "XATO: reja bo'sh — kamida bitta qadam yoz.")
    if sink is not None:
        sink["reja"] = qadamlar
    tayyor = sum(1 for q in qadamlar if q["holat"] == "tayyor")
    hozir = next((q["matn"] for q in qadamlar if q["holat"] == "ishlanmoqda"), "")
    return ("🗒️ Reja yangilandi" + (" · " + hozir[:48] if hozir else ""),
            "%d/%d tayyor" % (tayyor, len(qadamlar)),
            "Reja yozildi va foydalanuvchiga ko'rsatildi:\n" +
            "\n".join("%s %s" % ({"tayyor": "[x]", "ishlanmoqda": "[→]"}.get(q["holat"], "[ ]"),
                                 q["matn"]) for q in qadamlar))


# ────────────────────────────────────── Web ──────────────────────────────────
_TEG_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.S | re.I)
_HTML_RE = re.compile(r"<[^>]+>")


def _html_matn(xom):
    matn = _TEG_RE.sub(" ", xom)
    matn = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>|</h[1-6]>", "\n", matn, flags=re.I)
    matn = _HTML_RE.sub(" ", matn)
    matn = _html.unescape(matn)
    matn = re.sub(r"[ \t ]+", " ", matn)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", matn).strip()


def _web(name, args, cwd, sink):
    if name == "web_olish":
        url = str(args.get("url") or "").strip()
        if not re.match(r"^https?://", url):
            url = "https://" + url
        so_rov = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "uz,en;q=0.9,ru;q=0.8",
        })
        try:
            with urllib.request.urlopen(so_rov, timeout=30) as javob:
                tur = (javob.headers.get("Content-Type") or "").lower()
                xom = javob.read(4 * 1024 * 1024).decode("utf-8", "replace")
        except urllib.error.HTTPError as xato:
            return ("🌍 Sahifa olindi · " + url[:50], "HTTP %d" % xato.code,
                    "XATO: sayt %d qaytardi. Bu sahifa oddiy so'rovni rad etadi — "
                    "`brauzer_och` bilan haqiqiy brauzerda ochib ko'r." % xato.code)
        except Exception as xato:
            return ("🌍 Sahifa olindi · " + url[:50], "xato",
                    "XATO: " + str(xato)[:200] + "\nHaqiqiy brauzer kerak bo'lsa `brauzer_och` ishlat.")
        matn = xom if ("json" in tur or "text/plain" in tur) else _html_matn(xom)
        return ("🌍 Sahifa olindi · " + url[:55], "%d belgi" % len(matn), _qirq(matn))

    if name == "web_qidiruv":
        so_rov = str(args.get("sorov") or "").strip()
        if not so_rov:
            return ("🔍 Internetdan qidirildi", "bo'sh", "XATO: so'rov bo'sh.")
        royxat = _qidir(so_rov)
        if not royxat:
            # Server javobi bo'sh bo'lsa haqiqiy brauzerda ochamiz — u yerda
            # sahifa JavaScript bilan chiziladi va odatda natija chiqadi.
            b = brauzer.sessiya()
            b.och("https://duckduckgo.com/?q=" + urllib.parse.quote(so_rov))
            b.kut(matn="", soniya=6)
            matn, _ = b.oqi()
            _brauzer_holat(sink, "qidiruv: " + so_rov)
            return ("🔍 Internetdan qidirildi · " + so_rov[:45], "brauzerda ochildi",
                    "Tuzilgan natija ajratilmadi — qidiruv sahifasining o'zi:\n\n" + _qirq(matn))
        chiqish = "\n\n".join("%d. %s\n   %s\n   %s" % (i + 1, r["s"], r["u"], r["t"])
                              for i, r in enumerate(royxat))
        return ("🔍 Internetdan qidirildi · " + so_rov[:45], "%d natija" % len(royxat),
                chiqish + "\n\nKerakli sahifani `web_olish` yoki `brauzer_och` bilan to'liq o'qi.")

    if name == "youtube_qidiruv":
        so_rov = str(args.get("sorov") or "").strip()
        if not so_rov:
            return ("🎬 YouTube'dan qidirildi", "bo'sh", "XATO: so'rov bo'sh.")
        nechta = max(1, min(int(args.get("nechta") or 5), 12))
        try:
            royxat = _youtube_qidir(so_rov, nechta)
        except Exception as xato:
            return ("🎬 YouTube'dan qidirildi · " + so_rov[:40], "xato",
                    "XATO: " + str(xato)[:200])
        if not royxat:
            return ("🎬 YouTube'dan qidirildi · " + so_rov[:40], "topilmadi",
                    "Bu so'rov bo'yicha video topilmadi. So'rovni boshqacha yozib ko'r.")
        # Natijalar suhbatda tayyor kartalar bo'lib chiziladi — agent ularni
        # matn bilan qayta sanab chiqmasligi kerak.
        if sink is not None:
            sink["videolar"] = [{"id": v["id"], "sarlavha": v["sarlavha"],
                                 "kanal": v["kanal"], "davomiylik": v["davomiylik"],
                                 "korish": v["korish"]} for v in royxat]
        satrlar = ["%d. %s · %s · %s" % (i, v["sarlavha"], v["kanal"] or "?",
                                         v["davomiylik"] or "?")
                   for i, v in enumerate(royxat, 1)]
        return ("🎬 YouTube'dan qidirildi · " + so_rov[:40], "%d video" % len(royxat),
                "\n".join(satrlar) +
                "\n\nBu videolar foydalanuvchiga KARTA ko'rinishida allaqachon "
                "ko'rsatildi — ularni javobingda qayta sanab chiqma va havolalarni "
                "yozma. Faqat bir-ikki gapda qaysi biri nimaga mos kelishini ayt.")

    return None


def _yt_yur(tugun, chiqish):
    """ytInitialData ichidan videoRenderer bloklarini yig'adi."""
    if isinstance(tugun, dict):
        vr = tugun.get("videoRenderer")
        if isinstance(vr, dict) and vr.get("videoId"):
            sarlavha = "".join(x.get("text", "") for x in ((vr.get("title") or {}).get("runs") or []))
            kanal = "".join(x.get("text", "") for x in ((vr.get("ownerText") or {}).get("runs") or []))
            if sarlavha:
                chiqish.append({
                    "id": vr["videoId"],
                    "sarlavha": sarlavha[:150],
                    "kanal": kanal[:60],
                    "davomiylik": (vr.get("lengthText") or {}).get("simpleText", ""),
                    "korish": (vr.get("shortViewCountText") or {}).get("simpleText", ""),
                    "url": "https://www.youtube.com/watch?v=" + vr["videoId"],
                })
        for qiymat in tugun.values():
            _yt_yur(qiymat, chiqish)
    elif isinstance(tugun, list):
        for qiymat in tugun:
            _yt_yur(qiymat, chiqish)
    return chiqish


_YT_DATA_RE = re.compile(r"var ytInitialData\s*=\s*(\{.*?\});</script>", re.S)


def _youtube_qidir(so_rov, nechta=5):
    """YouTube qidiruv sahifasidan haqiqiy natijalarni oladi (API kalitsiz)."""
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(so_rov)
    so = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept-Language": "uz,en;q=0.9,ru;q=0.8",
    })
    with urllib.request.urlopen(so, timeout=30) as javob:
        sahifa = javob.read().decode("utf-8", "replace")
    mos = _YT_DATA_RE.search(sahifa)
    if not mos:
        return []
    natija, korilgan = [], set()
    for v in _yt_yur(json.loads(mos.group(1)), []):
        if v["id"] in korilgan:
            continue
        korilgan.add(v["id"])
        natija.append(v)
        if len(natija) >= nechta:
            break
    return natija


_NATIJA_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_IZOH_RE = re.compile(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', re.S | re.I)


def _ddg_url(xom):
    """DDG havolani o'z yo'naltirgichiga o'raydi — haqiqiy manzilni chiqaramiz."""
    xom = _html.unescape(xom or "")
    if "uddg=" in xom:
        try:
            return urllib.parse.unquote(xom.split("uddg=", 1)[1].split("&", 1)[0])
        except Exception:
            pass
    return ("https:" + xom) if xom.startswith("//") else xom


def _qidir(so_rov, nechta=8):
    """DuckDuckGo'ning serverda chiziladigan sahifasi — tez va ishonchli."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(so_rov)
    so = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept-Language": "uz,en;q=0.9,ru;q=0.8",
    })
    try:
        with urllib.request.urlopen(so, timeout=25) as javob:
            xom = javob.read().decode("utf-8", "replace")
    except Exception:
        return []
    sarlavhalar = _NATIJA_RE.findall(xom)
    izohlar = _IZOH_RE.findall(xom)
    natija = []
    for i, (havola, sarlavha) in enumerate(sarlavhalar[:nechta]):
        natija.append({
            "s": _html_matn(sarlavha)[:140],
            "u": _ddg_url(havola),
            "t": (_html_matn(izohlar[i])[:280] if i < len(izohlar) else ""),
        })
    return [n for n in natija if n["s"]]


# ───────────────────────────────── Fayl / rasm ───────────────────────────────
def _git(name, args, cwd, sink):
    if not name.startswith("git_"):
        return None
    import subprocess

    def yugur(argv, chegara=25):
        d = subprocess.run(["git"] + argv, cwd=cwd, capture_output=True,
                           text=True, timeout=chegara)
        return (d.stdout or "") + (("\n" + d.stderr) if d.returncode and d.stderr else ""), d.returncode

    ildiz, kod = yugur(["rev-parse", "--show-toplevel"])
    if kod != 0:
        return ("🔀 Git", "repozitoriy emas",
                "XATO: bu papka git repozitoriysi emas — " + cwd)

    if name == "git_holat":
        tarmoq, _ = yugur(["branch", "--show-current"])
        holat, _ = yugur(["status", "--short"])
        stat, _ = yugur(["diff", "--stat"])
        tarix, _ = yugur(["log", "--oneline", "-8"])
        ozgargan = len([q for q in holat.splitlines() if q.strip()])
        return ("🔀 Git holati · " + (tarmoq.strip() or "HEAD"),
                "%d fayl o'zgargan" % ozgargan,
                _qirq("Tarmoq: %s\n\nO'zgargan fayllar:\n%s\n\nHajmi:\n%s\n\nOxirgi commitlar:\n%s"
                      % (tarmoq.strip(), holat.strip() or "(yo'q)",
                         stat.strip() or "(yo'q)", tarix.strip())))

    if name == "git_farq":
        fayl = str(args.get("fayl") or "").strip()
        argv = ["diff"]
        if args.get("saqlangan"):
            argv.append("--staged")
        if fayl:
            argv += ["--", fayl]
        chiqish, _ = yugur(argv, 40)
        if not chiqish.strip():
            return ("🔀 Git farqi", "o'zgarish yo'q", "O'zgarish topilmadi.")
        return ("🔀 Git farqi · " + (fayl or "hammasi"),
                "%d qator" % len(chiqish.splitlines()), _qirq(chiqish))

    if name == "git_tarix":
        fayl = str(args.get("fayl") or "").strip()
        nechta = max(1, min(int(args.get("nechta") or 15), 60))
        argv = ["log", "--oneline", "--decorate", "-%d" % nechta]
        if fayl:
            argv += ["--", fayl]
        chiqish, _ = yugur(argv, 30)
        return ("🔀 Git tarixi · " + (fayl or "loyiha"),
                "%d commit" % len(chiqish.splitlines()), _qirq(chiqish) or "(bo'sh)")

    return None


def _fayl(name, args, cwd, sink):
    if name == "multi_edit":
        path = _yol(cwd, args.get("path"))
        if not os.path.isfile(path):
            return ("✏️ Ko'p tahrir", "topilmadi", "XATO: fayl topilmadi — " + path)
        tahrirlar = args.get("tahrirlar") or []
        if not tahrirlar:
            return ("✏️ Ko'p tahrir", "bo'sh", "XATO: tahrirlar ro'yxati bo'sh.")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            asl = f.read()
        matn = asl
        # Avval hammasini tekshiramiz: bittasi ham noaniq bo'lsa hech narsa
        # yozilmaydi — yarim tahrirlangan fayl qolib ketmasin.
        for i, t in enumerate(tahrirlar, 1):
            eski = (t or {}).get("old_text") or ""
            if not eski:
                return ("✏️ Ko'p tahrir", "bo'sh matn", "XATO: %d-tahrirda old_text bo'sh." % i)
            uchradi = matn.count(eski)
            if uchradi == 0:
                return ("✏️ Ko'p tahrir · " + os.path.basename(path), "moslik yo'q",
                        "XATO: %d-tahrirdagi old_text topilmadi. Hech narsa yozilmadi — "
                        "avval read_file bilan aniq matnni ol." % i)
            if uchradi > 1:
                return ("✏️ Ko'p tahrir · " + os.path.basename(path), "noaniq",
                        "XATO: %d-tahrirdagi old_text %d marta uchradi. Hech narsa "
                        "yozilmadi — atrofidagi qatorlarni qo'shib yagona qil." % (i, uchradi))
            matn = matn.replace(eski, (t or {}).get("new_text") or "", 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(matn)
        qoshildi, ochirildi = QATOR_FARQI(asl, matn) if QATOR_FARQI else (0, 0)
        nosozlik = TEKSHIR(path) if TEKSHIR else ""
        if sink is not None:
            sink["fayl"] = {"nom": os.path.basename(path), "amal": "tahrirlandi",
                            "qoshildi": qoshildi, "ochirildi": ochirildi}
        return ("✏️ Ko'p tahrir · " + os.path.basename(path),
                ("⚠️ sintaksis xatosi" if nosozlik else "%d bo'lak · +%d −%d"
                 % (len(tahrirlar), qoshildi, ochirildi)),
                "%d ta bo'lak almashtirildi: %s (+%d −%d qator)%s"
                % (len(tahrirlar), path, qoshildi, ochirildi,
                   "\n\n" + nosozlik if nosozlik else "\nSintaksis tekshiruvi o'tdi."))

    if name == "fayl_kochirish":
        manba = _yol(cwd, args.get("dan"))
        maqsad = _yol(cwd, args.get("ga"))
        if not os.path.exists(manba):
            return ("📦 Fayl ko'chirildi", "topilmadi", "XATO: topilmadi — " + manba)
        if os.path.exists(maqsad):
            return ("📦 Fayl ko'chirildi", "band",
                    "XATO: maqsad allaqachon mavjud — " + maqsad + ". Ustidan yozmadim.")
        os.makedirs(os.path.dirname(maqsad) or ".", exist_ok=True)
        os.rename(manba, maqsad)
        return ("📦 Ko'chirildi · %s → %s" % (os.path.basename(manba), os.path.basename(maqsad)),
                "bajarildi", "Ko'chirildi: %s → %s" % (manba, maqsad))

    if name == "fayl_ochirish":
        yol = _yol(cwd, args.get("path"))
        if not os.path.exists(yol):
            return ("🗑️ Fayl o'chirildi", "topilmadi", "XATO: topilmadi — " + yol)
        if os.path.isdir(yol):
            return ("🗑️ Fayl o'chirildi", "papka",
                    "XATO: bu papka. Papkani o'chirish uchun foydalanuvchidan ruxsat so'ra "
                    "va `run_command` bilan bajar.")
        # O'chirmaymiz — Chiqindiga surilg'aymiz. Xato o'chirish qaytariladigan bo'lsin.
        chiqindi = os.path.expanduser("~/.Trash")
        try:
            if os.path.isdir(chiqindi):
                nishon = os.path.join(chiqindi, os.path.basename(yol))
                if os.path.exists(nishon):
                    nishon += "_%d" % int(time.time())
                os.rename(yol, nishon)
                return ("🗑️ Chiqindiga surildi · " + os.path.basename(yol), "qaytarish mumkin",
                        "Fayl o'chirilmadi, Chiqindiga surildi: " + nishon)
        except OSError:
            pass
        os.unlink(yol)
        return ("🗑️ Fayl o'chirildi · " + os.path.basename(yol), "bajarildi", "O'chirildi: " + yol)

    if name == "rasm_korish":
        yol = _yol(cwd, args.get("path"))
        if not os.path.isfile(yol):
            return ("🖼️ Rasm ko'rildi", "topilmadi", "XATO: rasm topilmadi — " + yol)
        if os.path.splitext(yol)[1].lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            return ("🖼️ Rasm ko'rildi", "rasm emas",
                    "XATO: bu rasm fayli emas. Matn fayli uchun `read_file` ishlat.")
        if sink is not None:
            sink["image"] = yol
        return ("🖼️ Rasm ko'rildi · " + os.path.basename(yol),
                "%d KB" % (os.path.getsize(yol) // 1024),
                "Rasm senga ko'rsatildi: " + yol)

    if name == "fayl_qidirish":
        naqsh = str(args.get("naqsh") or "*").strip()
        joy = _yol(cwd, args.get("path"))
        toliq = naqsh if os.path.isabs(naqsh) else os.path.join(joy, "**", naqsh)
        topilgan = [p for p in _glob.glob(toliq, recursive=True) if os.path.isfile(p)]
        topilgan = [p for p in topilgan
                    if not any(x in p for x in ("/node_modules/", "/.git/", "/.venv/", "/__pycache__/"))]
        topilgan.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        kesilgan = topilgan[:200]
        return ("🗂️ Fayl qidirildi · " + naqsh, "%d fayl" % len(topilgan),
                _qirq("\n".join(kesilgan)) if kesilgan else "Mos fayl topilmadi.")

    if name == "rasm_yaratish":
        if KALIT is None:
            return ("🎨 Rasm yaratildi", "kalit yo'q", "XATO: OpenAI kaliti sozlanmagan.")
        tavsif = str(args.get("tavsif") or "").strip()
        if not tavsif:
            return ("🎨 Rasm yaratildi", "bo'sh", "XATO: rasm tavsifi bo'sh.")
        olcham = str(args.get("olcham") or "1024x1024")
        if olcham not in ("1024x1024", "1536x1024", "1024x1536"):
            olcham = "1024x1024"
        tana = json.dumps({
            "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            "prompt": tavsif, "size": olcham, "n": 1,
        }).encode("utf-8")
        so_rov = urllib.request.Request(
            "https://api.openai.com/v1/images/generations", data=tana, method="POST",
            headers={"Authorization": "Bearer " + KALIT(), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(so_rov, timeout=240) as javob:
                d = json.loads(javob.read().decode("utf-8"))
        except urllib.error.HTTPError as xato:
            xabar = xato.read().decode("utf-8", "replace")[:400]
            past = xabar.lower()
            if "safety" in past or "content_policy" in past or "rejected" in past:
                return ("🎨 Rasm yaratildi", "rad etildi",
                        "XATO: generator bu tavsifni rad etdi (odatda mashhur qahramon yoki "
                        "brend nomi sabab). Qahramonni nom aytmasdan TASVIRLAB qayta yoz.")
            return ("🎨 Rasm yaratildi", "HTTP %d" % xato.code, "XATO: " + xabar)
        except Exception as xato:
            return ("🎨 Rasm yaratildi", "xato", "XATO: " + str(xato)[:220])
        import base64
        b64 = ((d.get("data") or [{}])[0]).get("b64_json") or ""
        if not b64:
            return ("🎨 Rasm yaratildi", "bo'sh", "XATO: rasm qaytmadi.")
        papka = os.path.join(LOYIHA, "images")
        os.makedirs(papka, exist_ok=True)
        nom = re.sub(r"[^\w]+", "_", tavsif.lower())[:40].strip("_") or "rasm"
        yol = os.path.join(papka, "%s_%d.png" % (nom, int(time.time())))
        with open(yol, "wb") as f:
            f.write(base64.b64decode(b64))
        nisbiy = "images/" + os.path.basename(yol)
        if sink is not None:
            sink["image"] = yol
        return ("🎨 Rasm yaratildi · " + os.path.basename(yol), olcham,
                "Rasm tayyor: %s\nSuhbatda ko'rsatish uchun shu yo'lni yoz: %s" % (yol, nisbiy))

    return None


# ──────────────────────────────── Yordamchi agent ────────────────────────────
def _ulanish(name, args, cwd, sink):
    if name == "ulanishlar_holati":
        h = ulanish.holat()
        p = h["printer"]
        bolaklar = ["Printerlar: %d ta%s" % (p["soni"],
                    (" (chek printeri: %s)" % p["chek"]) if p["chek"] else "")]
        for x in p["royxat"]:
            bolaklar.append("  · %s — %s%s" % (x["nom"], x["holat"],
                                               " [standart]" if x["standart"] else ""))
        tv = h["tv"]
        bolaklar.append("TV: " + ("ulangan " + tv.get("host", "") if tv.get("ulangan")
                                  else "ulanmagan (sozlamalar → Ulanishlar)"))
        bolaklar.append("iPhone (Messages): " + ("tayyor" if h["iphone"]["messages_bor"] else "yo'q"))
        a = h["android"]
        bolaklar.append("Android telefon: " + ("%d ta ulangan" % len(a["qurilmalar"])
                                               if a["qurilmalar"] else
                                               ("adb bor, telefon ulanmagan" if a["adb"] else "adb yo'q")))
        tg = h["telegram"]
        bolaklar.append("Telegram: " + ("@" + tg.get("bot", "") if tg.get("ulangan") else "ulanmagan"))
        return ("🔌 Ulanishlar tekshirildi", "%d printer" % p["soni"], "\n".join(bolaklar))

    if name == "chop_etish":
        r = ulanish.chop_et(matn=args.get("matn") or "", fayl=args.get("fayl") or "",
                            printer=args.get("printer") or "", nusxa=args.get("nusxa") or 1)
        if not r.get("ok"):
            return ("🖨️ Chop etildi", "xato", "XATO: " + str(r.get("sabab")))
        return ("🖨️ Chop etishga yuborildi" + (" · " + args["printer"] if args.get("printer") else ""),
                "bajarildi", str(r.get("javob")))

    if name == "qurilmalar_qidirish":
        royxat = ulanish.qurilmalar(int(args.get("soniya") or 6))
        if not royxat:
            return ("📡 Qurilmalar qidirildi", "topilmadi",
                    "Wi-Fi da qurilma topilmadi. TV yoqiqmi va Mac bilan bir tarmoqdami — "
                    "tekshiring (telefon hotspotida odatda ko'rinmaydi).")
        satrlar = ["%s · %s · %s%s" % (d["nom"], d["tur"], d["ip"] or "?",
                                       "  ← boshqarsa bo'ladi" if d["boshqariladi"] else "")
                   for d in royxat]
        return ("📡 Qurilmalar topildi", "%d ta" % len(royxat), "\n".join(satrlar))

    if name == "tv_buyruq":
        r = ulanish.tv_buyruq(nom=args.get("tugma") or "", matn=args.get("matn") or "",
                              ilova=args.get("ilova") or "", url=args.get("url") or "")
        if not r.get("ok"):
            return ("📺 TV buyrug'i", "xato", "XATO: " + str(r.get("sabab")))
        return ("📺 TV · " + (args.get("tugma") or args.get("url") or args.get("ilova") or "matn"),
                "bajarildi", str(r.get("xabar")))

    if name == "sms_yuborish":
        r = ulanish.sms_yuborish(args.get("raqam"), args.get("matn"))
        if not r.get("ok"):
            return ("💬 SMS yuborildi", "xato",
                    "XATO: " + str(r.get("sabab")) +
                    "\nMac va iPhone bir Apple ID da bo'lishi hamda iPhone'da "
                    "Sozlamalar → Xabarlar → SMS uzatish yoqilgan bo'lishi kerak.")
        return ("💬 SMS yuborildi · " + str(r.get("kimga")), "bajarildi",
                "Yuborildi: " + str(r.get("kimga")))

    if name == "qongiroq_qilish":
        r = ulanish.qongiroq_qilish(args.get("raqam"))
        if not r.get("ok"):
            return ("📞 Qo'ng'iroq", "xato", "XATO: " + str(r.get("sabab")))
        return ("📞 Qo'ng'iroq · " + str(r.get("raqam")), "oyna ochildi", str(r.get("xabar")))

    if name == "telegram_yuborish":
        r = ulanish.telegram_yuborish(args.get("kimga"), args.get("matn"))
        if not r.get("ok"):
            return ("✈️ Telegram xabari", "xato", "XATO: " + str(r.get("sabab")))
        return ("✈️ Telegram · " + str(r.get("kimga")), "yuborildi",
                "Yuborildi: " + str(r.get("kimga")))

    if name == "telegram_suhbatlar":
        royxat = ulanish.telegram_suhbatlar()
        if not royxat:
            return ("✈️ Telegram suhbatlari", "bo'sh",
                    "Suhbat topilmadi. Telegram boti faqat O'ZIGA yozgan odamga javob "
                    "bera oladi — kerakli odam avval botga bir marta yozishi kerak.")
        return ("✈️ Telegram suhbatlari", "%d ta" % len(royxat),
                "\n".join("%s · id=%s · %s" % (d["nom"], d["id"], d["tur"]) for d in royxat))

    return None


def _jadval(name, args, cwd, sink):
    """Google Sheets. Natija suhbat burchagidagi panelda ham ko'rinadi."""
    if not name.startswith("sheets_"):
        return None
    import jadval

    def panel(sid, sarlavha, qatorlar, varaq=""):
        if sink is not None:
            sink["jadval"] = {"id": sid, "sarlavha": sarlavha, "varaq": varaq,
                              "havola": jadval.havola(sid),
                              "qatorlar": [[str(h) for h in q] for q in (qatorlar or [])[:60]]}

    if name == "sheets_yaratish":
        d = jadval.yaratish(args.get("nom") or "MuhasibPro jadvali",
                            args.get("sarlavhalar"))
        panel(d["id"], d["nom"], [args.get("sarlavhalar") or []])
        return ("📊 Jadval yaratildi · " + d["nom"], "tayyor",
                "Yaratildi.\nHavola: %s\nID: %s\n\nFoydalanuvchiga havolani ber."
                % (d["havola"], d["id"]))

    if name == "sheets_royxat":
        r = jadval.royxat(int(args.get("nechta") or 20))
        if not r:
            return ("📊 Jadvallar", "bo'sh",
                    "Ko'rinadigan jadval yo'q. Mavjud jadvalni ishlatish uchun uni "
                    "xizmat hisobiga ulashing: " + (jadval.hisob_pochtasi() or "?"))
        return ("📊 Jadvallar · %d ta" % len(r), "topildi",
                "\n".join("%s\n  id=%s\n  %s" % (x["nom"], x["id"], x["havola"]) for x in r))

    if name == "sheets_varaqlar":
        d = jadval.varaqlar(args.get("jadval"))
        return ("📊 Varaqlar · " + d["nom"], "%d ta" % len(d["varaqlar"]),
                "Jadval: %s\n" % d["nom"] +
                "\n".join("· %s (%sx%s)" % (v["nom"], v["qator"], v["ustun"]) for v in d["varaqlar"]))

    if name == "sheets_oqish":
        sid = jadval.jadval_id(args.get("jadval"))
        diapazon = str(args.get("diapazon") or "A1:Z200")
        qatorlar = jadval.oqish(sid, diapazon)
        panel(sid, "Google Sheets · " + diapazon, qatorlar)
        if not qatorlar:
            return ("📊 Jadval o'qildi", "bo'sh", "Bu diapazonda ma'lumot yo'q: " + diapazon)
        matn = "\n".join(" | ".join(str(h) for h in q) for q in qatorlar[:200])
        return ("📊 Jadval o'qildi · " + diapazon, "%d qator" % len(qatorlar),
                _qirq(matn) + "\n\nHavola: " + jadval.havola(sid))

    if name == "sheets_yozish":
        sid = jadval.jadval_id(args.get("jadval"))
        qatorlar = args.get("qatorlar") or []
        d = jadval.yozish(sid, str(args.get("diapazon") or "A1"), qatorlar)
        panel(sid, "Yozildi · " + d["diapazon"], qatorlar)
        return ("📊 Jadvalga yozildi · " + d["diapazon"], "%d katak" % d["yangilandi"],
                "Yozildi: %s\nHavola: %s" % (d["diapazon"], jadval.havola(sid)))

    if name == "sheets_qoshish":
        sid = jadval.jadval_id(args.get("jadval"))
        qatorlar = args.get("qatorlar") or []
        d = jadval.qoshish(sid, str(args.get("varaq") or "Sheet1"), qatorlar)
        panel(sid, "Qo'shildi · " + str(args.get("varaq") or "Sheet1"), qatorlar)
        return ("📊 Jadvalga qo'shildi", "%d qator" % d["qoshildi"],
                "Qo'shildi: %s\nHavola: %s" % (d["diapazon"], jadval.havola(sid)))

    if name == "sheets_tozalash":
        sid = jadval.jadval_id(args.get("jadval"))
        d = jadval.tozalash(sid, str(args.get("diapazon") or "A1:Z1000"))
        return ("📊 Jadval tozalandi · " + d["tozalandi"], "bajarildi",
                "Tozalandi: " + d["tozalandi"])

    if name == "sheets_varaq_qoshish":
        sid = jadval.jadval_id(args.get("jadval"))
        d = jadval.varaq_qoshish(sid, args.get("nom"))
        return ("📊 Varaq qo'shildi · " + str(d["nom"]), "tayyor",
                "Yangi varaq: %s\nHavola: %s" % (d["nom"], jadval.havola(sid, d["id"])))

    return None


def _boshqa(name, args, cwd, sink):
    if name == "kalendar_yozish":
        r = ulanish.kalendar_yozish(args.get("sarlavha"), args.get("sana"),
                                    args.get("soat") or "", int(args.get("davomiylik") or 60),
                                    args.get("izoh") or "")
        if not r.get("ok"):
            return ("📅 Kalendarga yozildi", "xato", "XATO: " + str(r.get("sabab")))
        return ("📅 Kalendarga yozildi · " + str(r["sarlavha"])[:44],
                "%s %s" % (r["sana"], r["soat"]),
                "Qo'shildi: %s — %s %s" % (r["sarlavha"], r["sana"], r["soat"]))

    if name == "kalendar_kun":
        r = ulanish.kalendar_kun(args.get("sana") or "")
        if not r.get("ok"):
            return ("📅 Kalendar ko'rildi", "xato", "XATO: " + str(r.get("sabab")))
        v = r["voqealar"]
        return ("📅 Bugungi voqealar", "%d ta" % len(v),
                "\n".join(v) if v else "Bugun voqea yo'q.")

    if name == "eslatma_yozish":
        r = ulanish.eslatma_yozish(args.get("matn"), args.get("sana") or "",
                                   args.get("soat") or "")
        if not r.get("ok"):
            return ("⏰ Eslatma qo'shildi", "xato", "XATO: " + str(r.get("sabab")))
        return ("⏰ Eslatma · " + str(r["matn"])[:44], r["muddat"],
                "Qo'shildi: %s (%s)" % (r["matn"], r["muddat"]))

    if name == "pochta_yuborish":
        r = ulanish.pochta_yuborish(args.get("kimga"), args.get("mavzu") or "",
                                    args.get("matn"), args.get("biriktirma") or "")
        if not r.get("ok"):
            return ("📧 Xat yuborildi", "xato", "XATO: " + str(r.get("sabab")))
        return ("📧 Xat yuborildi · " + str(r["kimga"]), "bajarildi",
                "Yuborildi: " + str(r["kimga"]))

    if name == "valyuta_kursi":
        r = ulanish.kurslar(args.get("valyuta") or "")
        if not r.get("ok"):
            return ("💱 Valyuta kursi", "xato", "XATO: " + str(r.get("sabab")))
        if r.get("valyuta"):
            return ("💱 %s · %s so'm" % (r["valyuta"], r["kurs"]), r["sana"],
                    "%s (%s): %s so'm, kunlik o'zgarish %s. Sana: %s"
                    % (r["valyuta"], r["nom"], r["kurs"], r["ozgarish"], r["sana"]))
        satr = "\n".join("%s (%s): %s so'm  [%s]" % (v["valyuta"], v["nom"], v["kurs"], v["ozgarish"])
                         for v in r["kurslar"])
        return ("💱 Markaziy bank kursi · " + r["sana"], "%d valyuta" % len(r["kurslar"]),
                "Sana: %s\n%s" % (r["sana"], satr))

    if name == "excel_oqish":
        r = ulanish.excel_oqish(args.get("path"), args.get("varaq") or "",
                                int(args.get("chegara") or 300))
        if not r.get("ok"):
            return ("📗 Excel o'qildi", "xato", "XATO: " + str(r.get("sabab")))
        matn = "\n".join(" | ".join(str(h) for h in q) for q in r["qatorlar"])
        return ("📗 Excel o'qildi · " + r["varaq"], "%d qator" % len(r["qatorlar"]),
                "Varaqlar: %s\n\n%s" % (", ".join(r["varaqlar"]), _qirq(matn)))

    if name == "excel_yozish":
        r = ulanish.excel_yozish(args.get("path"), args.get("qatorlar") or [],
                                 args.get("varaq") or "Varaq1")
        if not r.get("ok"):
            return ("📗 Excel yozildi", "xato", "XATO: " + str(r.get("sabab")))
        return ("📗 Excel yozildi · " + os.path.basename(r["yol"]), "%d qator" % r["qator"],
                "Yozildi: " + r["yol"])

    return None


def _yordamchi(name, args, cwd, sink):
    if name != "yordamchi_agent":
        return None
    if YORDAMCHI is None:
        return ("🤝 Yordamchi agent", "mavjud emas", "XATO: yordamchi agent ulanmagan.")

    xom = args.get("vazifalar")
    if isinstance(xom, list) and xom:
        vazifalar = [str(v).strip() for v in xom if str(v).strip()][:5]
    else:
        bitta = str(args.get("vazifa") or "").strip()
        vazifalar = [bitta] if bitta else []
    if not vazifalar:
        return ("🤝 Yordamchi agent", "bo'sh", "XATO: vazifa bo'sh.")

    if len(vazifalar) == 1:
        natija = YORDAMCHI(vazifalar[0], cwd)
        return ("🤝 Yordamchi agent ishladi · " + vazifalar[0][:50],
                "%d belgi" % len(natija or ""),
                _qirq(natija or "(yordamchi javob qaytarmadi)"))

    # Bir nechta vazifa — barchasi bir vaqtda ketadi. Har biri o'z kontekstida
    # ishlaydi, shuning uchun ular bir-biriga xalaqit bermaydi.
    javoblar = [None] * len(vazifalar)

    def ishla(i, vazifa):
        try:
            javoblar[i] = YORDAMCHI(vazifa, cwd)
        except Exception as xato:
            javoblar[i] = "XATO: " + str(xato)[:200]

    oqimlar = [threading.Thread(target=ishla, args=(i, v), daemon=True)
               for i, v in enumerate(vazifalar)]
    for o in oqimlar:
        o.start()
    for o in oqimlar:
        o.join(timeout=900)

    bolaklar = []
    for i, vazifa in enumerate(vazifalar):
        bolaklar.append("### %d. %s\n%s" % (i + 1, vazifa[:120],
                                            (javoblar[i] or "(javob kelmadi)").strip()))
    return ("🤝 %d yordamchi birga ishladi" % len(vazifalar),
            "%d javob" % sum(1 for j in javoblar if j),
            _qirq("\n\n".join(bolaklar)))


_GURUHLAR = (_brauzer, _ekran, _reja, _web, _git, _fayl, _ulanish,
             _jadval, _boshqa, _yordamchi)


def ishlat(name, args, cwd, sink=None, on_proc=None):
    """Vosita shu modulga tegishli bo'lsa bajaradi, aks holda None."""
    for guruh in _GURUHLAR:
        try:
            javob = guruh(name, args, cwd, sink)
        except Exception as xato:
            return ("🛠️ " + name, "xato", "XATO: " + str(xato)[:400])
        if javob is not None:
            return javob
    return None


# ──────────────────────────────────── Sxemalar ───────────────────────────────
def _f(nom, tavsif, xossalar, majburiy=()):
    return {"type": "function", "name": nom, "description": tavsif,
            "parameters": {"type": "object", "properties": xossalar,
                           "required": list(majburiy), "additionalProperties": False}}


TOOLS = [
    # ── Reja ──
    _f("reja_yozish",
       ("Ko'p qadamli vazifa uchun reja tuzadi va foydalanuvchiga jonli ko'rsatadi. "
        "Uch qadamdan ortiq ish boshlashdan OLDIN shuni chaqir, keyin har qadam "
        "tugagach holatini yangilab qayta chaqir — foydalanuvchi qayerdaligingni ko'rib turadi."),
       {"qadamlar": {"type": "array", "description": "Reja qadamlari, tartib bilan.",
                     "items": {"type": "object", "properties": {
                         "matn": {"type": "string", "description": "Qadam nimadan iborat."},
                         "holat": {"type": "string", "enum": ["kutmoqda", "ishlanmoqda", "tayyor"]},
                     }, "required": ["matn", "holat"], "additionalProperties": False}}},
       ("qadamlar",)),

    # ── Brauzer ──
    _f("brauzer_och",
       ("Haqiqiy Chrome oynasida saytni ochadi va sahifani o'qib beradi. Internetdagi "
        "har qanday ish shu bilan boshlanadi. Brauzer o'z profilida yuradi — bir marta "
        "kirilgan saytga keyin ham kirgan holda qolasan."),
       {"url": {"type": "string", "description": "Sayt manzili, masalan google.com"}},
       ("url",)),
    _f("brauzer_oqish",
       ("Ochiq sahifani o'qiydi: bosiladigan elementlar ref raqamlari bilan va sahifa matni. "
        "Bosish yoki yozishdan OLDIN doim shuni chaqir — ref lar shu yerdan olinadi."),
       {"faqat_matn": {"type": "boolean", "description": "true bo'lsa faqat matn, elementlarsiz."}}),
    _f("brauzer_bosish",
       "Sahifadagi tugma yoki havolani bosadi va bosgandan keyingi sahifani qaytaradi.",
       {"ref": {"type": "string", "description": "brauzer_oqish bergan ref, masalan ref_12."},
        "matn": {"type": "string", "description": "Yoki element matni (ref bo'lmasa)."},
        "selector": {"type": "string", "description": "Yoki CSS selektor."}}),
    _f("brauzer_yozish",
       "Sahifadagi maydonga matn yozadi. enter=true bo'lsa yozib bo'lib Enter ham bosadi.",
       {"matn": {"type": "string", "description": "Yoziladigan matn."},
        "ref": {"type": "string", "description": "Maydon ref i."},
        "selector": {"type": "string", "description": "Yoki CSS selektor, masalan input[name=q]."},
        "enter": {"type": "boolean", "description": "Yozgandan keyin Enter bosilsinmi."},
        "tozala": {"type": "boolean", "description": "Avval maydonni tozalasinmi (standart true)."}},
       ("matn",)),
    _f("brauzer_tugma", "Brauzerda tugma bosadi: Enter, Tab, Escape, ArrowDown, PageDown...",
       {"tugma": {"type": "string", "description": "Tugma nomi."}}, ("tugma",)),
    _f("brauzer_aylantirish", "Sahifani pastga yoki yuqoriga aylantiradi.",
       {"yon": {"type": "string", "enum": ["pastga", "yuqoriga"]},
        "miqdor": {"type": "integer", "description": "Necha piksel (standart 600)."}}),
    _f("brauzer_kutish",
       "Sahifada matn yoki element paydo bo'lishini kutadi. Sekin yuklanadigan saytlar uchun.",
       {"matn": {"type": "string", "description": "Kutilayotgan matn."},
        "selector": {"type": "string", "description": "Yoki CSS selektor."},
        "soniya": {"type": "integer", "description": "Eng ko'pi necha soniya (standart 15)."}}),
    _f("brauzer_skrin",
       ("Brauzer sahifasining rasmini oladi va SENGA ko'rsatadi. Sahifa ko'rinishini "
        "haqiqatan ko'rish kerak bo'lganda (dizayn, grafik, matn bilan tushunarsiz joy) ishlat."),
       {}),
    _f("brauzer_js", "Ochiq sahifada JavaScript bajaradi va natijasini qaytaradi.",
       {"kod": {"type": "string", "description": "JS ifodasi."}}, ("kod",)),
    _f("brauzer_orqaga", "Brauzerda oldingi sahifaga qaytadi.", {}),
    _f("brauzer_login_kutish",
       ("Sayt kirish (login) talab qilsa SHUNI chaqir. Panelda foydalanuvchiga xabar "
        "chiqadi, u o'sha panelning o'zida kirib \"Davom etish\" ni bosadi, keyin sen "
        "ishni davom ettirasan. Parol, karta yoki tasdiqlash kodini HECH QACHON o'zing "
        "yozma — har doim shu vositani ishlat."),
       {"izoh": {"type": "string", "description": "Foydalanuvchiga nima qilishi kerakligi, bir gapda."},
        "soniya": {"type": "integer", "description": "Necha soniya kutilsin (standart 300)."}},
       ("izoh",)),

    # ── Ekran ──
    _f("ekran_korish",
       ("Mac ekranining rasmini olib SENGA ko'rsatadi. Rasm ekranning mantiqiy o'lchamida "
        "bo'ladi — rasmda ko'rgan koordinatani to'g'ridan-to'g'ri `ekran_bosish` ga berasan. "
        "Brauzerdan tashqaridagi ilova bilan ishlash shu bilan boshlanadi."),
       {}),
    _f("ekran_bosish", "Ekranning aniq nuqtasini bosadi. Avval `ekran_korish` bilan qara.",
       {"x": {"type": "integer"}, "y": {"type": "integer"},
        "tur": {"type": "string", "enum": ["chap", "ong", "ikki"], "description": "Bosish turi."},
        "marta": {"type": "integer", "description": "Necha marta (2 = ikki marta bosish)."}},
       ("x", "y")),
    _f("ekran_yozish", "Klaviaturada matn yozadi — hozir fokusda turgan joyga tushadi.",
       {"matn": {"type": "string"}}, ("matn",)),
    _f("ekran_tugma", "Tugma yoki birikma bosadi: enter, tab, esc, cmd+t, cmd+shift+4...",
       {"tugma": {"type": "string"}}, ("tugma",)),
    _f("ekran_aylantirish", "Ekranda sahifani aylantiradi (Page Up/Down).",
       {"yon": {"type": "string", "enum": ["pastga", "yuqoriga"]},
        "miqdor": {"type": "integer", "description": "Necha marta bosilsin."}}),
    _f("ilova_ochish", "Mac ilovasini ochadi va oldinga chiqaradi. Masalan: Finder, Notes, Excel.",
       {"nom": {"type": "string", "description": "Ilova nomi."}}, ("nom",)),

    # ── Web ──
    _f("web_qidiruv",
       "Internetdan qidiradi va natijalar ro'yxatini (sarlavha, manzil, tavsif) qaytaradi.",
       {"sorov": {"type": "string", "description": "Qidiruv so'rovi."}}, ("sorov",)),
    _f("youtube_qidiruv",
       ("YouTube'dan haqiqiy video qidiradi: sarlavha, kanal, davomiylik va to'g'ri "
        "havola qaytaradi. Foydalanuvchi video so'rasa SHUNI ishlat — havolani "
        "o'zingdan to'qima. Javobga havolani qo'ysang suhbatda pleyer bo'lib ochiladi."),
       {"sorov": {"type": "string", "description": "Qidiruv so'rovi."},
        "nechta": {"type": "integer", "description": "Nechta natija (standart 5, eng ko'pi 12)."}},
       ("sorov",)),
    _f("web_olish",
       ("Berilgan manzildagi sahifa yoki API javobini matn ko'rinishida oladi. Tez, lekin "
        "JavaScript bilan chiziladigan saytlarda `brauzer_och` yaxshiroq."),
       {"url": {"type": "string"}}, ("url",)),

    # ── Fayl / rasm ──
    # ── Git ──
    _f("git_holat",
       ("Repozitoriy holati: tarmoq, o'zgargan fayllar, o'zgarish hajmi va oxirgi "
        "commitlar. Kod ustida ishlashdan OLDIN shuni chaqir — nima allaqachon "
        "o'zgarganini bilmasdan tahrir qilish xatoga olib keladi."), {}),
    _f("git_farq",
       "Aniq o'zgarishlarni qator-baqator ko'rsatadi (git diff).",
       {"fayl": {"type": "string", "description": "Faqat shu fayl. Bo'sh bo'lsa — hammasi."},
        "saqlangan": {"type": "boolean", "description": "true bo'lsa staged o'zgarishlar."}}),
    _f("git_tarix",
       "Commitlar tarixi. Fayl berilsa — o'sha fayl tarixi.",
       {"fayl": {"type": "string"},
        "nechta": {"type": "integer", "description": "Nechta commit (standart 15)."}}),

    # ── Fayl ustida aniq ish ──
    _f("multi_edit",
       ("Bitta faylga bir nechta tahrirni BIR AMALDA qiladi. Har bir old_text "
        "faylda aynan bir marta uchrashi shart. Bittasi ham mos kelmasa hech narsa "
        "yozilmaydi — fayl yarim tahrirlangan holda qolmaydi. Bir faylda 2 dan ortiq "
        "joyni o'zgartirayotgan bo'lsang `edit_file` emas, SHUNI ishlat."),
       {"path": {"type": "string"},
        "tahrirlar": {"type": "array", "description": "Tartib bilan bajariladigan almashtirishlar.",
                      "items": {"type": "object", "properties": {
                          "old_text": {"type": "string", "description": "Almashtiriladigan aniq matn."},
                          "new_text": {"type": "string", "description": "O'rniga yoziladigan matn."},
                      }, "required": ["old_text", "new_text"], "additionalProperties": False}}},
       ("path", "tahrirlar")),
    _f("fayl_kochirish", "Faylni ko'chiradi yoki nomini o'zgartiradi. Maqsad band bo'lsa to'xtaydi.",
       {"dan": {"type": "string"}, "ga": {"type": "string"}}, ("dan", "ga")),
    _f("fayl_ochirish",
       ("Faylni Chiqindiga suradi (butunlay o'chirmaydi — xato bo'lsa qaytarish mumkin). "
        "Foydalanuvchi so'ramagan faylni o'chirma."),
       {"path": {"type": "string"}}, ("path",)),
    _f("rasm_korish",
       ("Diskdagi rasmni SENGA ko'rsatadi. Dizayn, skrinshot yoki chizmani haqiqatan "
        "ko'rish kerak bo'lganda ishlat — `read_file` rasmni o'qiy olmaydi."),
       {"path": {"type": "string"}}, ("path",)),

    _f("fayl_qidirish", "Nom naqshi bo'yicha fayllarni topadi, oxirgi o'zgargani birinchi.",
       {"naqsh": {"type": "string", "description": "Masalan *.py yoki hisob*.json"},
        "path": {"type": "string", "description": "Qaysi papkada. Bo'sh bo'lsa ish papkasi."}},
       ("naqsh",)),
    _f("rasm_yaratish",
       ("Tavsif bo'yicha rasm yaratadi va faylga saqlaydi. Fotorealistik kerak bo'lsa "
        "tavsifga 'photorealistic, DSLR photo, natural lighting' qo'sh; 'cartoon', "
        "'3D render' so'zlarini ishlatma."),
       {"tavsif": {"type": "string", "description": "Rasm tavsifi (inglizcha aniqroq chiqadi)."},
        "olcham": {"type": "string", "enum": ["1024x1024", "1536x1024", "1024x1536"]}},
       ("tavsif",)),

    # ── Ulanishlar: printer, TV, telefon, Telegram ──
    _f("ulanishlar_holati",
       ("Qaysi qurilmalar ulanganini ko'rsatadi: printerlar, TV, iPhone, Android "
        "telefon va Telegram. Qurilma bilan ish boshlashdan oldin shuni chaqir."), {}),
    _f("chop_etish",
       ("Matn yoki faylni printerga yuboradi. Chek printeri bor bo'lsa uning nomini "
        "`printer` ga ber — sotuv cheki, qarz tilxati va hisobot shunda chiqadi. "
        "Chek printeri tor (58/80mm), shuning uchun qatorlarni qisqa yoz."),
       {"matn": {"type": "string", "description": "Chop etiladigan matn."},
        "fayl": {"type": "string", "description": "Yoki fayl yo'li (PDF, rasm, matn)."},
        "printer": {"type": "string", "description": "Printer nomi. Bo'sh bo'lsa standart printer."},
        "nusxa": {"type": "integer", "description": "Nechta nusxa."}}),
    _f("qurilmalar_qidirish",
       ("Wi-Fi dagi qurilmalarni topadi: TV, Chromecast, AirPlay va tarmoq printerlari. "
        "Mac va qurilma bir tarmoqda bo'lishi shart."),
       {"soniya": {"type": "integer", "description": "Necha soniya qidirilsin (standart 6)."}}),
    _f("tv_buyruq",
       ("Ulangan Android TV ni boshqaradi. Tugmalar: yoqish, uy, orqaga, ok, yuqoriga, "
        "pastga, chapga, ongga, ovoz+, ovoz-, ovozsiz, play, toxtat. TV avval "
        "sozlamalardan ulangan bo'lishi kerak (ekrandagi kod bilan)."),
       {"tugma": {"type": "string", "description": "Bosiladigan tugma."},
        "matn": {"type": "string", "description": "TV dagi maydonga yoziladigan matn."},
        "url": {"type": "string", "description": "TV da ochiladigan havola."},
        "ilova": {"type": "string", "description": "Ochiladigan ilova (paket nomi yoki havola)."}}),
    _f("sms_yuborish",
       ("iPhone orqali SMS yoki iMessage yuboradi. YUBORISHDAN OLDIN foydalanuvchidan "
        "kim va nima yozilishini tasdiqlab ol — bu qaytarib bo'lmaydigan amal."),
       {"raqam": {"type": "string", "description": "Telefon raqami yoki Apple ID."},
        "matn": {"type": "string", "description": "Xabar matni."}},
       ("raqam", "matn")),
    _f("qongiroq_qilish",
       ("Raqamga qo'ng'iroq boshlaydi (FaceTime → iPhone). Foydalanuvchidan raqamni "
        "tasdiqlab ol. Qo'ng'iroqni yakuniy tasdiqlash Mac oynasida bo'ladi."),
       {"raqam": {"type": "string"}}, ("raqam",)),
    _f("telegram_yuborish",
       ("Telegram orqali xabar yuboradi. `kimga` — `telegram_suhbatlar` bergan id yoki "
        "@username. YUBORISHDAN OLDIN kim va nima yozilishini tasdiqlab ol."),
       {"kimga": {"type": "string", "description": "Chat id yoki @username."},
        "matn": {"type": "string"}},
       ("kimga", "matn")),
    _f("telegram_suhbatlar",
       ("Telegram botiga yozgan odamlar va guruhlar ro'yxati (id bilan). Xabar "
        "yuborishdan oldin kerakli id ni shundan ol."), {}),

    # ── Google Sheets ──
    _f("sheets_yaratish",
       ("Yangi Google jadval yaratadi va havolasini qaytaradi. Foydalanuvchi "
        "\"jadvalga tushir\", \"Google Sheets'ga yoz\" desa va tayyor jadval "
        "ko'rsatmasa — shuni chaqir."),
       {"nom": {"type": "string", "description": "Jadval nomi."},
        "sarlavhalar": {"type": "array", "description": "Birinchi qator — ustun nomlari.",
                        "items": {"type": "string"}}}),
    _f("sheets_royxat", "Ishlata oladigan jadvallar ro'yxati (id va havolasi bilan).",
       {"nechta": {"type": "integer"}}),
    _f("sheets_varaqlar", "Jadval ichidagi varaqlar (tab) ro'yxati va o'lchami.",
       {"jadval": {"type": "string", "description": "Jadval havolasi yoki id si."}},
       ("jadval",)),
    _f("sheets_oqish",
       ("Jadvaldan ma'lumot o'qiydi va suhbat burchagidagi panelda ko'rsatadi. "
        "Diapazon A1 uslubida: `A1:F50` yoki `Varaq2!A:D`."),
       {"jadval": {"type": "string"},
        "diapazon": {"type": "string", "description": "Standart A1:Z200."}},
       ("jadval",)),
    _f("sheets_yozish",
       ("Jadvalning aniq joyiga yozadi (ustidan yozadi). Formulani ham yozsa bo'ladi: "
        "`=SUM(B2:B10)` kabi qiymat matn sifatida beriladi va Sheets uni formula deb qabul qiladi."),
       {"jadval": {"type": "string"},
        "diapazon": {"type": "string", "description": "Boshlanish katagi, masalan A1 yoki Hisobot!B2."},
        "qatorlar": {"type": "array", "description": "Qatorlar ro'yxati, har biri kataklar ro'yxati.",
                     "items": {"type": "array", "items": {"type": "string"}}}},
       ("jadval", "diapazon", "qatorlar")),
    _f("sheets_qoshish",
       ("Jadval oxiriga yangi qator(lar) qo'shadi — mavjud ma'lumot o'chmaydi. "
        "Jurnal, kunlik hisobot va sotuvlar ro'yxati uchun asosiy amal."),
       {"jadval": {"type": "string"},
        "varaq": {"type": "string", "description": "Varaq nomi (standart Sheet1)."},
        "qatorlar": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}},
       ("jadval", "qatorlar")),
    _f("sheets_tozalash", "Berilgan diapazonni tozalaydi. Ehtiyot bo'l — ma'lumot o'chadi.",
       {"jadval": {"type": "string"}, "diapazon": {"type": "string"}},
       ("jadval", "diapazon")),
    _f("sheets_varaq_qoshish", "Jadvalga yangi varaq (tab) qo'shadi.",
       {"jadval": {"type": "string"}, "nom": {"type": "string"}}, ("jadval", "nom")),

    # ── Kalendar, eslatma, pochta ──
    _f("kalendar_yozish",
       ("macOS Kalendariga voqea qo'shadi. iCloud yoqilgan bo'lsa telefonda ham chiqadi."),
       {"sarlavha": {"type": "string"},
        "sana": {"type": "string", "description": "YYYY-MM-DD."},
        "soat": {"type": "string", "description": "HH:MM. Berilmasa 09:00."},
        "davomiylik": {"type": "integer", "description": "Daqiqada (standart 60)."},
        "izoh": {"type": "string"}},
       ("sarlavha", "sana")),
    _f("kalendar_kun", "Bugungi kalendar voqealarini o'qiydi.", {"sana": {"type": "string"}}),
    _f("eslatma_yozish", "macOS Eslatmalar (Reminders) ga vazifa qo'shadi.",
       {"matn": {"type": "string"}, "sana": {"type": "string", "description": "YYYY-MM-DD."},
        "soat": {"type": "string", "description": "HH:MM."}},
       ("matn",)),
    _f("pochta_yuborish",
       ("macOS Mail orqali elektron xat yuboradi. YUBORISHDAN OLDIN kim va nima "
        "yozilishini foydalanuvchiga ko'rsatib tasdiqlab ol."),
       {"kimga": {"type": "string"}, "mavzu": {"type": "string"},
        "matn": {"type": "string"}, "biriktirma": {"type": "string", "description": "Fayl yo'li."}},
       ("kimga", "matn")),

    # ── Valyuta va Excel ──
    _f("valyuta_kursi",
       ("O'zbekiston Markaziy bankining rasmiy kursi. Valyuta kassalari, dollar "
        "hisob-kitobi va narx belgilashda ishlat — kursni xotiradan aytma."),
       {"valyuta": {"type": "string", "description": "USD, EUR, RUB... Bo'sh bo'lsa asosiylari."}}),
    _f("excel_oqish", "Diskdagi .xlsx faylni o'qiydi.",
       {"path": {"type": "string"}, "varaq": {"type": "string"},
        "chegara": {"type": "integer", "description": "Nechta qator (standart 300)."}},
       ("path",)),
    _f("excel_yozish", "Yangi .xlsx yaratadi yoki mavjudiga varaq qo'shadi.",
       {"path": {"type": "string"}, "varaq": {"type": "string"},
        "qatorlar": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}},
       ("path", "qatorlar")),

    # ── Yordamchi ──
    _f("yordamchi_agent",
       ("Alohida yordamchi agentlarga mustaqil izlanish vazifasini beradi — ular o'zi "
        "fayl o'qiydi, qidiradi va faqat xulosa qaytaradi. Katta izlanish uchun ishlat: "
        "asosiy suhbat uzun natijalar bilan to'lib ketmaydi.\n"
        "`vazifalar` ga bir nechta (5 tagacha) mustaqil vazifa bersang, ular BIR VAQTDA "
        "ishlaydi — bu ancha tez. Bir-biriga bog'liq vazifalarni birga berma.\n"
        "Har bir vazifani to'liq va o'zi tushunarli qilib yoz: yordamchi bu suhbatni ko'rmaydi."),
       {"vazifa": {"type": "string", "description": "Bitta vazifa."},
        "vazifalar": {"type": "array", "description": "Bir vaqtda bajariladigan mustaqil vazifalar.",
                      "items": {"type": "string"}}}),
]
