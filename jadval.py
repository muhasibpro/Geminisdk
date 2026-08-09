#!/usr/bin/env python3
"""Google Sheets — jadval o'qish, yozish va yaratish.

Ulanish usuli: **xizmat hisobi** (service account). Nega shunday:
  · Parol yoki brauzerdan qaytish (OAuth redirect) kerak emas.
  · Kalit bir marta yuklab olinadi va shu Mac'da qoladi.
  · Foydalanuvchi jadvalni xizmat hisobi pochtasiga "ulashadi" — xuddi
    hamkasbiga ulashgandek. Ruxsatni xohlagan payt bekor qiladi.

Kalit `.env` dagi `GOOGLE_SA_JSON` da: fayl yo'li yoki JSON matnining o'zi.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE = "https://www.googleapis.com/drive/v3/files"
DOIRA = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file"]
_TOKEN = {"qiymat": "", "tugaydi": 0.0}
QULF = threading.Lock()


def _kalit_manba():
    return (os.environ.get("GOOGLE_SA_JSON") or "").strip()


def _kalit():
    """Xizmat hisobi kalitini o'qiydi — fayl yo'li ham, JSON matni ham bo'ladi."""
    xom = _kalit_manba()
    if not xom:
        return None
    try:
        if xom.lstrip().startswith("{"):
            return json.loads(xom)
        yol = os.path.expanduser(xom)
        if os.path.isfile(yol):
            with open(yol, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None
    return None


def sozlangan():
    return skript_ulangan() or oauth_ulangan() or _kalit() is not None


def hisob_pochtasi():
    """Foydalanuvchi jadvalni shu pochtaga ulashadi."""
    k = _kalit() or {}
    return k.get("client_email", "")


# ══════════════════ Apps Script — eng oson yo'l (Cloud Console'siz) ══════════
# Google har bir dasturdan OAuth ro'yxatidan o'tishni talab qiladi, lekin
# foydalanuvchining O'ZI yozgan skript bundan mustasno: u o'z hisobi nomidan
# ishlaydi. Shuning uchun bu yerda foydalanuvchi Google Sheets ichida kichik
# skript ochadi va uning manzilini shu yerga joylaydi. Cloud Console, JSON
# kalit va jadvalni ulashish — hech biri kerak emas.

def skript_url():
    return (os.environ.get("SHEETS_SCRIPT_URL") or "").strip()


def skript_siri():
    """Faqat shu dastur murojaat qila olishi uchun maxfiy so'z."""
    sir = (os.environ.get("SHEETS_SCRIPT_SIR") or "").strip()
    if not sir:
        import secrets
        sir = secrets.token_urlsafe(18)
    return sir


def skript_ulangan():
    return bool(skript_url())


def skript_kodi(sir=""):
    """Foydalanuvchi Google Sheets ichiga joylaydigan skript."""
    return SKRIPT_ANDAZA.replace("__SIR__", sir or skript_siri())


SKRIPT_ANDAZA = r"""/**
 * MuhasibPro — Google Sheets ko'prigi
 * Bu skript SIZNING hisobingiz nomidan ishlaydi. Undan tashqariga hech narsa
 * chiqmaydi: faqat quyidagi maxfiy so'zni bilgan dastur murojaat qila oladi.
 */
const SIR = '__SIR__';

function doPost(e) {
  try {
    const s = JSON.parse(e.postData.contents || '{}');
    if (s.sir !== SIR) return javob({ ok: false, sabab: 'Maxfiy so\'z mos emas' });

    const amal = s.amal;
    if (amal === 'tekshir') return javob({ ok: true, xabar: 'ishlayapti' });

    if (amal === 'yaratish') {
      const yangi = SpreadsheetApp.create(s.nom || 'MuhasibPro');
      return javob({ ok: true, id: yangi.getId(), nom: yangi.getName(),
                     havola: yangi.getUrl() });
    }

    if (amal === 'royxat') {
      const fayllar = DriveApp.getFilesByType(MimeType.GOOGLE_SHEETS);
      const chiqish = [];
      while (fayllar.hasNext() && chiqish.length < 25) {
        const f = fayllar.next();
        chiqish.push({ id: f.getId(), nom: f.getName(), havola: f.getUrl() });
      }
      return javob({ ok: true, jadvallar: chiqish });
    }

    const kitob = SpreadsheetApp.openById(s.id);
    if (amal === 'varaqlar') {
      return javob({ ok: true, nom: kitob.getName(),
        varaqlar: kitob.getSheets().map(function (v) {
          return { nom: v.getName(), qator: v.getLastRow(), ustun: v.getLastColumn() };
        }) });
    }

    const varaqNomi = s.varaq || kitob.getSheets()[0].getName();
    let varaq = kitob.getSheetByName(varaqNomi);
    if (!varaq) varaq = kitob.insertSheet(varaqNomi);

    if (amal === 'oqish') {
      const d = s.diapazon ? varaq.getRange(s.diapazon).getValues() : varaq.getDataRange().getValues();
      return javob({ ok: true, qatorlar: d });
    }

    if (amal === 'yozish') {
      const q = s.qatorlar || [];
      if (!q.length) return javob({ ok: true, qator: 0 });
      const en = Math.max.apply(null, q.map(function (r) { return r.length; }));
      const tekis = q.map(function (r) {
        const nusxa = r.slice(); while (nusxa.length < en) nusxa.push(''); return nusxa;
      });
      if (s.tozala) varaq.clear();
      varaq.getRange(1, 1, tekis.length, en).setValues(tekis);
      return javob({ ok: true, qator: tekis.length });
    }

    if (amal === 'qoshish') {
      const q = s.qatorlar || [];
      q.forEach(function (r) { varaq.appendRow(r); });
      return javob({ ok: true, qator: q.length });
    }

    if (amal === 'tozalash') {
      if (s.diapazon) varaq.getRange(s.diapazon).clearContent(); else varaq.clear();
      return javob({ ok: true });
    }

    return javob({ ok: false, sabab: 'Noma\'lum amal: ' + amal });
  } catch (xato) {
    return javob({ ok: false, sabab: String(xato) });
  }
}

function javob(d) {
  return ContentService.createTextOutput(JSON.stringify(d))
    .setMimeType(ContentService.MimeType.JSON);
}
"""


def _skript_sorov(maydonlar, kutish=60):
    url = skript_url()
    if not url:
        raise RuntimeError("Apps Script manzili sozlanmagan.")
    tana = json.dumps(dict(maydonlar, sir=skript_siri())).encode("utf-8")
    so_rov = urllib.request.Request(url, data=tana, method="POST",
                                    headers={"Content-Type": "application/json"})
    try:
        # Apps Script javobni script.googleusercontent.com ga yo'naltiradi —
        # urllib buni o'zi kuzatadi.
        with urllib.request.urlopen(so_rov, timeout=kutish) as javob:
            xom = javob.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as xato:
        matn = xato.read().decode("utf-8", "replace")[:300]
        if xato.code in (401, 403):
            raise RuntimeError("Skript ruxsat bermadi. Deploy qilishda "
                               "«Who has access» ni «Anyone» qilib qo'ying.")
        raise RuntimeError("Skript xatosi (%d): %s" % (xato.code, matn))
    try:
        d = json.loads(xom)
    except ValueError:
        if "<html" in xom.lower():
            raise RuntimeError("Skript HTML qaytardi — manzil noto'g'ri yoki deploy "
                               "«Anyone» emas. Web app manzilini qayta nusxalang "
                               "(/exec bilan tugashi kerak).")
        raise RuntimeError("Skript tushunarsiz javob qaytardi: " + xom[:200])
    if not d.get("ok"):
        raise RuntimeError(str(d.get("sabab") or "skript xatosi"))
    return d


def skript_tekshir():
    return _skript_sorov({"amal": "tekshir"}, kutish=45)


# ─────────────────────────── OAuth: o'z Google hisobingiz ───────────────────
# Xizmat hisobidan farqi: har bir jadvalni alohida ulashish shart emas —
# o'z hisobingizdagi hamma jadval darrov ochiladi. Ruxsat bir marta beriladi
# va yangilanish tokeni bilan o'zi uzayadi.
OAUTH_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN = "https://oauth2.googleapis.com/token"


def _oauth_mijoz():
    """`.env` dagi client_id/secret. Yuklangan client_secret.json ham bo'ladi."""
    xom = (os.environ.get("GOOGLE_OAUTH_CLIENT") or "").strip()
    if not xom:
        return None
    try:
        if xom.lstrip().startswith("{"):
            d = json.loads(xom)
        else:
            yol = os.path.expanduser(xom)
            if not os.path.isfile(yol):
                return None
            with open(yol, "r", encoding="utf-8") as f:
                d = json.load(f)
    except Exception:
        return None
    # Google `installed` yoki `web` kaliti ichida beradi
    ich = d.get("installed") or d.get("web") or d
    if ich.get("client_id") and ich.get("client_secret"):
        return {"client_id": ich["client_id"], "client_secret": ich["client_secret"]}
    return None


def oauth_sozlangan():
    return _oauth_mijoz() is not None


def oauth_ulangan():
    return bool((os.environ.get("GOOGLE_OAUTH_REFRESH") or "").strip())


def oauth_havola(redirect):
    """Foydalanuvchi shu manzilda ruxsat beradi — brauzer panelida ochiladi."""
    mijoz = _oauth_mijoz()
    if not mijoz:
        raise RuntimeError("Avval Google OAuth mijoz faylini (client_secret.json) qo'shing.")
    return OAUTH_AUTH + "?" + urllib.parse.urlencode({
        "client_id": mijoz["client_id"],
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(DOIRA),
        "access_type": "offline",
        "prompt": "consent",             # yangilanish tokeni har doim kelsin
    })


def _oauth_sorov(maydonlar):
    tana = urllib.parse.urlencode(maydonlar).encode()
    so_rov = urllib.request.Request(OAUTH_TOKEN, data=tana, method="POST")
    try:
        with urllib.request.urlopen(so_rov, timeout=30) as javob:
            return json.loads(javob.read().decode("utf-8"))
    except urllib.error.HTTPError as xato:
        xabar = xato.read().decode("utf-8", "replace")
        try:
            d = json.loads(xabar)
            xabar = d.get("error_description") or d.get("error") or xabar
        except Exception:
            pass
        raise RuntimeError(str(xabar)[:300])


def oauth_almashish(code, redirect):
    """Ruxsatdan qaytgan kodni doimiy yangilanish tokeniga almashtiradi."""
    mijoz = _oauth_mijoz()
    if not mijoz:
        raise RuntimeError("OAuth mijoz sozlanmagan.")
    d = _oauth_sorov({
        "code": code, "client_id": mijoz["client_id"],
        "client_secret": mijoz["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code",
    })
    yangilanish = d.get("refresh_token")
    if not yangilanish:
        raise RuntimeError("Google yangilanish tokenini bermadi. Ruxsatni bekor qilib "
                           "(myaccount.google.com/permissions) qaytadan urinib ko'ring.")
    with QULF:
        _TOKEN["qiymat"] = d.get("access_token", "")
        _TOKEN["tugaydi"] = time.time() + int(d.get("expires_in") or 3600) - 60
    return yangilanish


def _oauth_token():
    mijoz = _oauth_mijoz()
    yangilanish = (os.environ.get("GOOGLE_OAUTH_REFRESH") or "").strip()
    if not mijoz or not yangilanish:
        return ""
    d = _oauth_sorov({
        "client_id": mijoz["client_id"], "client_secret": mijoz["client_secret"],
        "refresh_token": yangilanish, "grant_type": "refresh_token",
    })
    _TOKEN["qiymat"] = d.get("access_token", "")
    _TOKEN["tugaydi"] = time.time() + int(d.get("expires_in") or 3600) - 60
    return _TOKEN["qiymat"]


def _token():
    with QULF:
        if _TOKEN["qiymat"] and time.time() < _TOKEN["tugaydi"] - 60:
            return _TOKEN["qiymat"]
        # Avval OAuth — u foydalanuvchining o'z hisobi va qulayroq.
        if oauth_ulangan():
            token = _oauth_token()
            if token:
                return token
        kalit = _kalit()
        if not kalit:
            raise RuntimeError("Google Sheets ulanmagan. Sozlamalar → Ulanishlar "
                               "bo'limidan Google hisobingiz bilan ulaning.")
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        creds = service_account.Credentials.from_service_account_info(kalit, scopes=DOIRA)
        creds.refresh(Request())
        _TOKEN["qiymat"] = creds.token
        _TOKEN["tugaydi"] = time.time() + 3300
        return creds.token


def _sorov(url, usul="GET", tana=None, kutish=45):
    data = json.dumps(tana).encode("utf-8") if tana is not None else None
    so_rov = urllib.request.Request(url, data=data, method=usul, headers={
        "Authorization": "Bearer " + _token(),
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(so_rov, timeout=kutish) as javob:
            xom = javob.read().decode("utf-8")
        return json.loads(xom) if xom.strip() else {}
    except urllib.error.HTTPError as xato:
        xabar = xato.read().decode("utf-8", "replace")
        try:
            xabar = (json.loads(xabar).get("error") or {}).get("message") or xabar
        except Exception:
            pass
        if xato.code in (403, 404):
            raise RuntimeError(
                "%s\n\nEhtimol jadval xizmat hisobiga ulashilmagan. Google Sheets'da "
                "«Share» tugmasini bosib, quyidagi pochtani Muharrir (Editor) qilib "
                "qo'shing:\n%s" % (xabar[:300], hisob_pochtasi() or "(kalit yo'q)"))
        raise RuntimeError(xabar[:400])


ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})")


def jadval_id(manba):
    """Havoladan ham, ID dan ham ishlaydi — foydalanuvchi havolani tashlashi tabiiy."""
    manba = str(manba or "").strip()
    mos = ID_RE.search(manba)
    return mos.group(1) if mos else manba


def havola(sid, varaq_id=None):
    url = "https://docs.google.com/spreadsheets/d/" + sid
    return url + ("/edit#gid=%s" % varaq_id if varaq_id is not None else "/edit")


# ──────────────────────────────────── Amallar ────────────────────────────────
def _skriptmi():
    """Skript yo'li ulangan bo'lsa hamma amal shundan o'tadi — u eng oson va
    hech qanday qo'shimcha ruxsat talab qilmaydi."""
    return skript_ulangan()


def yaratish(nom, sarlavhalar=None):
    if _skriptmi():
        d = _skript_sorov({"amal": "yaratish", "nom": nom or "MuhasibPro jadvali"})
        if sarlavhalar:
            yozish(d["id"], "A1", [list(sarlavhalar)])
        return {"id": d["id"], "nom": d.get("nom", nom), "havola": d.get("havola", havola(d["id"]))}
    return _yaratish_api(nom, sarlavhalar)


def _yaratish_api(nom, sarlavhalar=None):
    """Yangi jadval yaratadi va uni ochiq havola bilan ulashadi."""
    tana = {"properties": {"title": str(nom or "MuhasibPro jadvali")}}
    d = _sorov(API, "POST", tana)
    sid = d.get("spreadsheetId")
    if sarlavhalar:
        yozish(sid, "A1", [list(sarlavhalar)])
    # Havolasi borlar ko'ra olsin — aks holda foydalanuvchi o'z jadvalini ocholmaydi.
    try:
        _sorov(DRIVE + "/" + sid + "/permissions",
               "POST", {"role": "writer", "type": "anyone"})
    except Exception:
        pass
    return {"id": sid, "nom": tana["properties"]["title"], "havola": havola(sid)}


def varaqlar(sid):
    if _skriptmi():
        return _skript_sorov({"amal": "varaqlar", "id": jadval_id(sid)})
    d = _sorov("%s/%s?fields=properties.title,sheets.properties" % (API, jadval_id(sid)))
    return {
        "nom": (d.get("properties") or {}).get("title", ""),
        "varaqlar": [{"nom": (v.get("properties") or {}).get("title", ""),
                      "id": (v.get("properties") or {}).get("sheetId"),
                      "qator": ((v.get("properties") or {}).get("gridProperties") or {}).get("rowCount"),
                      "ustun": ((v.get("properties") or {}).get("gridProperties") or {}).get("columnCount")}
                     for v in (d.get("sheets") or [])],
    }


def _varaq_ajrat(diapazon, standart=""):
    """`Varaq2!A1:C9` → ("Varaq2", "A1:C9")"""
    if "!" in (diapazon or ""):
        varaq, _, qism = diapazon.partition("!")
        return varaq.strip("'"), qism
    return standart, diapazon


def oqish(sid, diapazon="A1:Z200"):
    sid = jadval_id(sid)
    if _skriptmi():
        varaq, qism = _varaq_ajrat(diapazon)
        d = _skript_sorov({"amal": "oqish", "id": sid, "varaq": varaq, "diapazon": qism})
        return d.get("qatorlar") or []
    url = "%s/%s/values/%s" % (API, sid, urllib.parse.quote(diapazon))
    d = _sorov(url)
    return d.get("values") or []


def yozish(sid, diapazon, qatorlar, tozala=False):
    sid = jadval_id(sid)
    tayyor = [[("" if h is None else h) for h in q] for q in qatorlar]
    if _skriptmi():
        varaq, _ = _varaq_ajrat(diapazon)
        d = _skript_sorov({"amal": "yozish", "id": sid, "varaq": varaq,
                           "qatorlar": tayyor, "tozala": bool(tozala)})
        return {"yangilandi": d.get("qator", len(tayyor)), "diapazon": diapazon}
    url = ("%s/%s/values/%s?valueInputOption=USER_ENTERED"
           % (API, sid, urllib.parse.quote(diapazon)))
    d = _sorov(url, "PUT", {"values": tayyor})
    return {"yangilandi": d.get("updatedCells", 0), "diapazon": d.get("updatedRange", diapazon)}


def qoshish(sid, varaq, qatorlar):
    """Oxiriga qator qo'shadi — jurnal va hisobot uchun asosiy amal."""
    sid = jadval_id(sid)
    tayyor = [[("" if h is None else h) for h in q] for q in qatorlar]
    if _skriptmi():
        nom, _ = _varaq_ajrat(varaq or "", varaq or "")
        d = _skript_sorov({"amal": "qoshish", "id": sid, "varaq": nom, "qatorlar": tayyor})
        return {"qoshildi": d.get("qator", len(tayyor)), "diapazon": nom}
    joy = (varaq or "A1") if "!" in (varaq or "") else ((varaq or "Sheet1") + "!A1")
    url = ("%s/%s/values/%s:append?valueInputOption=USER_ENTERED"
           "&insertDataOption=INSERT_ROWS" % (API, sid, urllib.parse.quote(joy)))
    d = _sorov(url, "POST", {"values": tayyor})
    yangi = (d.get("updates") or {})
    return {"qoshildi": yangi.get("updatedRows", len(tayyor)),
            "diapazon": yangi.get("updatedRange", joy)}


def tozalash(sid, diapazon):
    sid = jadval_id(sid)
    if _skriptmi():
        varaq, qism = _varaq_ajrat(diapazon)
        _skript_sorov({"amal": "tozalash", "id": sid, "varaq": varaq, "diapazon": qism})
        return {"tozalandi": diapazon}
    url = "%s/%s/values/%s:clear" % (API, sid, urllib.parse.quote(diapazon))
    _sorov(url, "POST", {})
    return {"tozalandi": diapazon}


def varaq_qoshish(sid, nom):
    sid = jadval_id(sid)
    if _skriptmi():
        # Skript yo'lida varaq yozishda o'zi yaratiladi.
        return {"nom": nom, "id": None}
    d = _sorov("%s/%s:batchUpdate" % (API, sid), "POST",
               {"requests": [{"addSheet": {"properties": {"title": str(nom)}}}]})
    yangi = (((d.get("replies") or [{}])[0]).get("addSheet") or {}).get("properties") or {}
    return {"nom": yangi.get("title", nom), "id": yangi.get("sheetId")}


def royxat(nechta=20):
    """Ko'rish mumkin bo'lgan jadvallar."""
    if _skriptmi():
        d = _skript_sorov({"amal": "royxat"})
        return (d.get("jadvallar") or [])[:nechta]
    url = (DRIVE + "?q=" + urllib.parse.quote("mimeType='application/vnd.google-apps.spreadsheet'")
           + "&pageSize=%d&fields=files(id,name,modifiedTime)&orderBy=modifiedTime desc" % nechta)
    d = _sorov(url)
    return [{"id": f["id"], "nom": f.get("name", ""), "havola": havola(f["id"]),
             "ozgargan": f.get("modifiedTime", "")} for f in (d.get("files") or [])]


def holat():
    k = _kalit()
    javob = {"ulangan": sozlangan(),
             "usul": ("skript" if skript_ulangan() else
                      ("google" if oauth_ulangan() else ("xizmat" if k else ""))),
             "skript_url": skript_url(),
             "mijoz_bor": oauth_sozlangan(),
             "pochta": (k or {}).get("client_email", ""),
             "avto": dict(AVTO)}
    if not javob["ulangan"]:
        return javob
    try:
        javob["jadvallar"] = len(royxat(10))
    except Exception as xato:
        javob["xato"] = str(xato)[:160]
    return javob


# ═══════════════════════════ Avtomatik sinxronlash ═══════════════════════════
# Daftarga har yozilganda jadval o'zi yangilanadi. To'liq qayta yozamiz —
# shunda o'chirilgan amal ham jadvaldan yo'qoladi va ikki tomon bir xil bo'ladi.
AVTO = {"id": "", "varaq": "Amallar", "oxirgi": 0.0, "holat": "", "navbat": False}
_AVTO_QULF = threading.Lock()
_KECHIKISH = 4.0          # ketma-ket yozuvlar bitta yuborishga birlashsin

SARLAVHA = ["Sana", "Tur", "Kim", "Tovar", "Miqdor", "Birlik", "Narx",
            "Summa", "Valyuta", "Kassa", "To'lov", "Izoh", "ID"]


def avto_sozla(jadval_manba="", varaq=""):
    AVTO["id"] = jadval_id(jadval_manba) if jadval_manba else ""
    if varaq:
        AVTO["varaq"] = varaq
    AVTO["holat"] = ""
    return dict(AVTO)


def _amal_qatori(a):
    return [
        str(a.get("sana") or ""), str(a.get("tur") or ""), str(a.get("kim") or ""),
        str(a.get("tovar") or ""), a.get("miqdor") or "", str(a.get("birlik") or ""),
        a.get("narx") or "", a.get("summa") or "", str(a.get("valyuta") or ""),
        str(a.get("kassa_nomi") or ""), str(a.get("tolov") or ""),
        str(a.get("izoh") or ""), str(a.get("id") or ""),
    ]


def sinxronla(kuchli=False):
    """Daftardagi barcha amallarni jadvalga yozadi."""
    if not AVTO["id"]:
        return {"ok": False, "sabab": "avto-sinxron sozlanmagan"}
    if not sozlangan():
        return {"ok": False, "sabab": "Google Sheets ulanmagan"}
    import hisob
    amallar = hisob.amallar(limit=500)
    amallar = list(reversed(amallar))          # eskisidan yangisiga
    qatorlar = [SARLAVHA] + [_amal_qatori(a) for a in amallar]
    try:
        varaq = AVTO["varaq"] or "Amallar"
        try:
            varaq_qoshish(AVTO["id"], varaq)   # bo'lmasa yaratamiz
        except Exception:
            pass                               # bor bo'lsa xato beradi — normal
        # Eski qatorlar qolib ketmasin: avval tozalab, keyin yozamiz.
        tozalash(AVTO["id"], "%s!A1:M2000" % varaq)
        yozish(AVTO["id"], "%s!A1" % varaq, qatorlar)
        AVTO["oxirgi"] = time.time()
        AVTO["holat"] = "%d amal · %s" % (len(amallar), time.strftime("%H:%M:%S"))
        return {"ok": True, "qator": len(amallar), "havola": havola(AVTO["id"])}
    except Exception as xato:
        AVTO["holat"] = "xato: " + str(xato)[:120]
        return {"ok": False, "sabab": str(xato)[:240]}


def _kechiktirib_yubor():
    """Daftar o'zgardi — bir necha soniyadan keyin bir marta yuboramiz."""
    if not AVTO["id"] or not sozlangan():
        return
    with _AVTO_QULF:
        if AVTO["navbat"]:
            return                              # allaqachon navbatda
        AVTO["navbat"] = True

    def ishla():
        time.sleep(_KECHIKISH)
        with _AVTO_QULF:
            AVTO["navbat"] = False
        sinxronla()

    threading.Thread(target=ishla, daemon=True).start()


def kuzatuvni_yoq():
    """hisob.py ga ulanadi — har yozuvdan keyin sinxron ishga tushadi."""
    import hisob
    if _kechiktirib_yubor not in hisob.KUZATUVCHILAR:
        hisob.KUZATUVCHILAR.append(_kechiktirib_yubor)
