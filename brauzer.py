#!/usr/bin/env python3
"""Brauzer dvigateli — agent haqiqiy Chrome bilan ishlaydi (Chrome DevTools Protocol).

Nega shunday: sayt oynasini iframe ichida ko'rsatib bo'lmaydi (X-Frame-Options),
qolaversa saytga kirish, tugma bosish va login qilish uchun haqiqiy brauzer kerak.
Shuning uchun alohida Chrome oynasi ochiladi, u o'z profilida yuradi — bir marta
kirilgan saytda keyingi safar ham kirgan holda qolasiz.

Tashqi kutubxona kerak emas: WebSocket qo'lda yozilgan, faqat standart kutubxona.
"""
import atexit
import base64
import http.client
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]
PROFIL = os.path.expanduser("~/.agy_brauzer_profil")
PORT = int(os.environ.get("AGY_BROWSER_PORT", "9333"))
OYNA_ENI = int(os.environ.get("AGY_BROWSER_WIDTH", "1280"))
OYNA_BOYI = int(os.environ.get("AGY_BROWSER_HEIGHT", "820"))
MATN_CHEGARA = 14000


def chrome_topish():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    raise RuntimeError("Google Chrome topilmadi. Chrome o'rnating yoki Safari'da qo'lda oching.")


# ───────────────────────────── WebSocket (minimal) ────────────────────────────
class WS:
    def __init__(self, url, timeout=30):
        m = re.match(r"ws://([^/:]+):(\d+)(/.*)", url)
        if not m:
            raise ValueError("WebSocket manzili noto'g'ri: " + url)
        host, port, path = m.group(1), int(m.group(2)), m.group(3)
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            "GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n" % (path, host, port, key)
        ).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Chrome DevTools ulanishni yopdi.")
            buf += chunk
        if b"101" not in buf.split(b"\r\n")[0]:
            raise ConnectionError("Chrome DevTools qo'l berishni rad etdi.")
        self.rest = buf.split(b"\r\n\r\n", 1)[1]

    def _oq(self, n):
        while len(self.rest) < n:
            chunk = self.sock.recv(max(4096, n - len(self.rest)))
            if not chunk:
                raise ConnectionError("Chrome bilan aloqa uzildi.")
            self.rest += chunk
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def send(self, text):
        data = text.encode("utf-8")
        n = len(data)
        head = bytearray([0x81])
        if n < 126:
            head.append(0x80 | n)
        elif n < (1 << 16):
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        mask = os.urandom(4)
        head += mask
        self.sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        chunks, opcode = [], None
        while True:
            b1, b2 = self._oq(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            masked, ln = b2 & 0x80, b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._oq(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._oq(8))[0]
            mask = self._oq(4) if masked else None
            payload = self._oq(ln) if ln else b""
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 0x8:
                raise ConnectionError("Chrome oynasi yopildi.")
            if op == 0x9:
                self.sock.sendall(b"\x8a\x80" + os.urandom(4))
                continue
            if op == 0xA:
                continue
            if op in (0x1, 0x2):
                opcode = op
            chunks.append(payload)
            if fin:
                break
        data = b"".join(chunks)
        return data.decode("utf-8", "replace") if opcode == 0x1 else data

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


# ─────────────────────────────────── Sessiya ──────────────────────────────────
class Brauzer:
    """Bitta Chrome oynasi. Barcha vositalar shu obyekt orqali ishlaydi."""

    def __init__(self):
        self.jarayon = None
        self.ws = None
        self.n = 0
        self.qulf = threading.RLock()
        self.oxirgi_url = ""
        self.oxirgi_sarlavha = ""
        self.oxirgi_skrin = b""
        self.oxirgi_skrin_vaqt = 0.0

    # ── quyi qatlam ──────────────────────────────────────────────────────────
    def _port_band(self):
        try:
            c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=1.5)
            c.request("GET", "/json/version")
            c.getresponse().read()
            return True
        except Exception:
            return False

    def _sahifa_ws(self, urinish=50):
        for _ in range(urinish):
            try:
                c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=2)
                c.request("GET", "/json/list")
                nishonlar = json.loads(c.getresponse().read())
                sahifalar = [t for t in nishonlar
                             if t.get("type") == "page" and t.get("webSocketDebuggerUrl")
                             and not str(t.get("url", "")).startswith("devtools://")]
                if sahifalar:
                    return sahifalar[0]["webSocketDebuggerUrl"]
            except Exception:
                pass
            time.sleep(0.4)
        raise RuntimeError("Chrome DevTools'ga ulanib bo'lmadi.")

    def _qulf_egasi(self):
        """SingletonLock `host-PID` ga ishora qiladi. Egasi tirik bo'lsa PID,
        aks holda 0 qaytadi."""
        try:
            nishon = os.readlink(os.path.join(PROFIL, "SingletonLock"))
        except OSError:
            return 0
        oxirgi = nishon.rsplit("-", 1)[-1]
        if not oxirgi.isdigit():
            return 0
        pid = int(oxirgi)
        try:
            os.kill(pid, 0)          # signal yubormaydi, faqat tirikligini so'raydi
            return pid
        except OSError:
            return 0                 # jarayon yo'q — qulf eskirgan

    def _qulflarni_tozala(self):
        """Faqat EGASIZ qulfni tozalaydi.

        Ilgari qulf shartsiz o'chirilardi. Agar o'sha paytda Chrome tirik
        bo'lsa, ikkinchi Chrome ham shu profilni ochib yuborardi va profil
        buzilardi — "Something went wrong when opening your profile" xatosi
        aynan shundan chiqadi. Endi egasi tirik bo'lsa qulfga tegilmaydi.
        """
        if self._qulf_egasi():
            return False
        for nom in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            try:
                yol = os.path.join(PROFIL, nom)
                if os.path.islink(yol) or os.path.exists(yol):
                    os.unlink(yol)
            except OSError:
                pass
        return True

    def _ishga_tushir(self):
        if self._port_band():
            return
        # Profil bitta Chrome'ga tegishli. Kimdir uni allaqachon ochib turgan
        # bo'lsa (masalan dasturning boshqa nusxasi), ikkinchisini ishga
        # tushirish profilni buzadi — shuning uchun to'xtaymiz va aytamiz.
        egasi = self._qulf_egasi()
        if egasi:
            raise RuntimeError(
                "Brauzer profili allaqachon ochiq (Chrome PID %d), lekin u boshqa "
                "portda ishlayapti. MuhasibPro'ning ikkinchi nusxasi ochiq bo'lsa "
                "uni yoping, yoki o'sha Chrome oynasini yopib qayta urinib ko'ring."
                % egasi)
        chrome = chrome_topish()
        os.makedirs(PROFIL, exist_ok=True)
        args = [
            chrome,
            "--remote-debugging-port=%d" % PORT,
            "--user-data-dir=" + PROFIL,
            "--window-size=%d,%d" % (OYNA_ENI, OYNA_BOYI),
            "--no-first-run", "--no-default-browser-check",
            "--disable-features=CalculateNativeWinOcclusion,Translate",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "about:blank",
        ]
        if os.environ.get("AGY_BROWSER_HEADLESS") == "1":
            args.insert(1, "--headless=new")

        for urinish in (1, 2):
            self.jarayon = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, start_new_session=True)
            for _ in range(60):
                if self._port_band():
                    return
                if self.jarayon.poll() is not None:
                    break        # Chrome darrov chiqib ketdi — odatda qolib ketgan qulf
                time.sleep(0.3)
            # Ikkinchi urinish faqat qulf EGASIZ bo'lsa mantiqiy. Egasi tirik
            # bo'lsa qayta urinish ikkinchi Chrome ochib profilni buzadi.
            if urinish == 1:
                if not self._qulflarni_tozala():
                    break
                time.sleep(0.6)
        raise RuntimeError(
            "Chrome ishga tushmadi (port %d ochilmadi). Shu profilni ishlatayotgan "
            "Chrome oynasi ochiq bo'lsa uni yopib qayta urinib ko'ring." % PORT)

    def _ulan(self):
        if self.ws is not None:
            return
        self._ishga_tushir()
        self.ws = WS(self._sahifa_ws())
        for domen in ("Page.enable", "Runtime.enable", "DOM.enable", "Network.enable"):
            try:
                self._xom(domen, {})
            except Exception:
                pass

    def _xom(self, metod, parametr=None):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": metod, "params": parametr or {}}))
        chegara = time.time() + 60
        while time.time() < chegara:
            xabar = json.loads(self.ws.recv())
            if xabar.get("id") == mid:
                if "error" in xabar:
                    raise RuntimeError("%s: %s" % (metod, xabar["error"].get("message", "")))
                return xabar.get("result", {})
        raise RuntimeError(metod + ": javob kelmadi (60s).")

    def call(self, metod, parametr=None):
        with self.qulf:
            try:
                self._ulan()
                return self._xom(metod, parametr)
            except (ConnectionError, OSError, RuntimeError):
                # Oyna yopilgan yoki ulanish uzilgan bo'lsa — bir marta qayta ulanamiz.
                try:
                    if self.ws:
                        self.ws.close()
                except Exception:
                    pass
                self.ws = None
                self._ulan()
                return self._xom(metod, parametr)

    def js(self, ifoda, kutish=True):
        r = self.call("Runtime.evaluate", {
            "expression": ifoda,
            "awaitPromise": kutish,
            "returnByValue": True,
            "userGesture": True,
        })
        if r.get("exceptionDetails"):
            xato = ((r["exceptionDetails"].get("exception") or {}).get("description")
                    or json.dumps(r["exceptionDetails"])[:300])
            raise RuntimeError("Sahifa xatosi: " + str(xato)[:300])
        return r.get("result", {}).get("value")

    def yopish(self):
        """Chrome'ni MULOYIM yopadi.

        Majburan o'ldirilsa (SIGKILL yoki `pkill`) Chrome profilni tartibga
        solib ulgurmaydi va keyingi ochilishda "Something went wrong when
        opening your profile" chiqadi. Shuning uchun avval Browser.close
        buyrug'ini beramiz, keyin SIGTERM, va faqat oxirida majburlaymiz.
        """
        with self.qulf:
            try:
                if self.ws:
                    try:
                        self._xom("Browser.close", {})   # Chrome o'zi tartibga soladi
                    except Exception:
                        pass
                    self.ws.close()
            except Exception:
                pass
            self.ws = None
            jarayon = self.jarayon
            self.jarayon = None
        if jarayon and jarayon.poll() is None:
            try:
                jarayon.terminate()
                jarayon.wait(timeout=8)          # yopilishini kutamiz
            except Exception:
                try:
                    jarayon.kill()
                except Exception:
                    pass


def hammasini_yop():
    """Dastur tugaganda chaqiriladi — profil iflos qolmasin."""
    b = _SESSIYA
    if b is not None:
        try:
            b.yopish()
        except Exception:
            pass

    # ── ustki qatlam: agent vositalari ───────────────────────────────────────
    def holat(self):
        try:
            info = self.js("JSON.stringify({u:location.href,t:document.title})") or "{}"
            d = json.loads(info)
            self.oxirgi_url = d.get("u", "")
            self.oxirgi_sarlavha = d.get("t", "")
        except Exception:
            pass
        return {"url": self.oxirgi_url, "sarlavha": self.oxirgi_sarlavha}

    def och(self, url, kutish=25):
        url = (url or "").strip()
        if not url:
            raise ValueError("Manzil bo'sh.")
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            url = "https://" + url
        self.call("Page.navigate", {"url": url})
        chegara = time.time() + kutish
        holat = ""
        while time.time() < chegara:
            time.sleep(0.35)
            try:
                holat = self.js("document.readyState") or ""
            except Exception:
                continue
            if holat in ("interactive", "complete"):
                break
        time.sleep(0.5)          # SPA'lar uchun kichik nafas
        return self.holat()

    def orqaga(self):
        self.js("history.back()")
        time.sleep(1.2)
        return self.holat()

    def skrin(self, toliq=False):
        r = self.call("Page.captureScreenshot", {
            "format": "jpeg", "quality": 72, "captureBeyondViewport": bool(toliq),
        })
        data = base64.b64decode(r.get("data") or "")
        if data:
            self.oxirgi_skrin = data
            self.oxirgi_skrin_vaqt = time.time()
        return data

    def skrin_fayl(self, papka):
        data = self.skrin()
        if not data:
            raise RuntimeError("Skrinshot olinmadi.")
        os.makedirs(papka, exist_ok=True)
        yol = os.path.join(papka, "brauzer_%d.jpg" % int(time.time() * 1000))
        with open(yol, "wb") as f:
            f.write(data)
        return yol

    # Sahifadagi bosiladigan/yoziladigan elementlarni ref bilan belgilaydi.
    _OQISH_JS = r"""
(() => {
  const SEL = 'a[href],button,input,textarea,select,[role="button"],[role="link"],'
            + '[role="tab"],[role="menuitem"],[role="checkbox"],[role="radio"],'
            + '[role="textbox"],[role="combobox"],[role="option"],[onclick],'
            + '[contenteditable="true"],summary,label[for]';
  document.querySelectorAll('[data-agy-ref]').forEach(e => e.removeAttribute('data-agy-ref'));
  const koz = { w: innerWidth, h: innerHeight };
  const qatorlar = [];
  let n = 0;
  const matn = el => {
    let t = (el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
             el.getAttribute('title') || el.value || el.innerText || el.textContent || '').trim();
    return t.replace(/\s+/g, ' ').slice(0, 110);
  };
  document.querySelectorAll(SEL).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (r.bottom < -400 || r.top > koz.h + 2400) return;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') return;
    if (el.disabled) return;
    n++;
    const ref = 'ref_' + n;
    el.setAttribute('data-agy-ref', ref);
    const tur = el.tagName.toLowerCase() +
      (el.type ? ':' + el.type : '') +
      (el.getAttribute('role') ? '[' + el.getAttribute('role') + ']' : '');
    const korinib = r.top >= -2 && r.top < koz.h;
    qatorlar.push(ref + ' <' + tur + '> ' + (matn(el) || '(matnsiz)') +
      (korinib ? '' : '  ·ekrandan tashqarida'));
  });
  const tanaMatn = (document.body ? (document.body.innerText || '') : '')
    .replace(/\n{3,}/g, '\n\n').trim();
  return JSON.stringify({
    url: location.href, sarlavha: document.title,
    elementlar: qatorlar, matn: tanaMatn,
    scroll: Math.round(scrollY) + '/' + Math.round(document.body ? document.body.scrollHeight : 0)
  });
})()
"""

    def oqi(self, faqat_matn=False, chegara=MATN_CHEGARA):
        xom = self.js(self._OQISH_JS)
        try:
            d = json.loads(xom or "{}")
        except Exception:
            d = {}
        self.oxirgi_url = d.get("url", "")
        self.oxirgi_sarlavha = d.get("sarlavha", "")
        matn = (d.get("matn") or "")[:chegara]
        bolaklar = ["URL: " + self.oxirgi_url,
                    "Sarlavha: " + self.oxirgi_sarlavha,
                    "Scroll: " + str(d.get("scroll", ""))]
        if not faqat_matn:
            elementlar = d.get("elementlar") or []
            bolaklar.append("\n── Bosiladigan/yoziladigan elementlar (%d ta) ──" % len(elementlar))
            bolaklar.append("\n".join(elementlar[:220]))
        bolaklar.append("\n── Sahifa matni ──\n" + matn)
        return "\n".join(bolaklar), d

    def _element_ifoda(self, ref="", matn="", selector=""):
        if selector:
            return "document.querySelector(%s)" % json.dumps(selector)
        if ref:
            return "document.querySelector('[data-agy-ref=\"%s\"]')" % re.sub(r"[^\w]", "", ref)
        if matn:
            # Ko'rinadigan elementlar orasidan matni mos kelganini topadi.
            return ("(() => {const q=%s.toLowerCase();"
                    "const hammasi=[...document.querySelectorAll('a,button,input,[role=\"button\"],"
                    "[role=\"link\"],[role=\"tab\"],summary,label,div[onclick],span[onclick]')];"
                    "const mos=hammasi.filter(e=>{const r=e.getBoundingClientRect();"
                    "if(r.width<2||r.height<2)return false;"
                    "const t=((e.innerText||e.value||e.getAttribute('aria-label')||'')+'').toLowerCase();"
                    "return t.includes(q);});"
                    "mos.sort((a,b)=>((a.innerText||'').length-(b.innerText||'').length));"
                    "return mos[0]||null;})()" % json.dumps(matn))
        raise ValueError("ref, matn yoki selector dan bittasi kerak.")

    def bos(self, ref="", matn="", selector=""):
        ifoda = self._element_ifoda(ref, matn, selector)
        natija = self.js("""
(() => {
  const el = %s;
  if (!el) return JSON.stringify({ok:false, sabab:'element topilmadi'});
  el.scrollIntoView({block:'center', inline:'center'});
  const r = el.getBoundingClientRect();
  return JSON.stringify({ok:true, x: r.left + r.width/2, y: r.top + r.height/2,
    nom: ((el.innerText||el.value||el.getAttribute('aria-label')||el.tagName)+'').trim().slice(0,80)});
})()
""" % ifoda)
        d = json.loads(natija or "{}")
        if not d.get("ok"):
            return {"ok": False, "sabab": d.get("sabab", "topilmadi")}
        x, y = float(d["x"]), float(d["y"])
        time.sleep(0.18)
        for tur in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", {
                "type": tur, "x": x, "y": y, "button": "left", "clickCount": 1,
                "buttons": 1 if tur == "mousePressed" else 0,
            })
        time.sleep(0.9)
        return {"ok": True, "nom": d.get("nom", ""), "url": self.holat().get("url", "")}

    def yoz(self, matn, ref="", selector="", tozala=True, enter=False):
        ifoda = self._element_ifoda(ref, "", selector) if (ref or selector) else "document.activeElement"
        natija = self.js("""
(() => {
  const el = %s;
  if (!el) return JSON.stringify({ok:false, sabab:'maydon topilmadi'});
  el.scrollIntoView({block:'center'});
  el.focus();
  if (%s) {
    if ('value' in el) { el.value=''; el.dispatchEvent(new Event('input',{bubbles:true})); }
    else if (el.isContentEditable) el.textContent='';
  }
  const r = el.getBoundingClientRect();
  return JSON.stringify({ok:true, x:r.left+r.width/2, y:r.top+r.height/2});
})()
""" % (ifoda, "true" if tozala else "false"))
        d = json.loads(natija or "{}")
        if not d.get("ok"):
            return {"ok": False, "sabab": d.get("sabab", "topilmadi")}
        self.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": d["x"], "y": d["y"],
                                               "button": "left", "clickCount": 1, "buttons": 1})
        self.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": d["x"], "y": d["y"],
                                               "button": "left", "clickCount": 1, "buttons": 0})
        time.sleep(0.15)
        self.call("Input.insertText", {"text": str(matn)})
        time.sleep(0.2)
        if enter:
            self.tugma("Enter")
            time.sleep(1.1)
        return {"ok": True, "url": self.holat().get("url", "")}

    _TUGMA = {
        "enter": ("Enter", 13, "\r"), "return": ("Enter", 13, "\r"),
        "tab": ("Tab", 9, "\t"), "escape": ("Escape", 27, ""), "esc": ("Escape", 27, ""),
        "backspace": ("Backspace", 8, ""), "delete": ("Delete", 46, ""),
        "arrowdown": ("ArrowDown", 40, ""), "arrowup": ("ArrowUp", 38, ""),
        "arrowleft": ("ArrowLeft", 37, ""), "arrowright": ("ArrowRight", 39, ""),
        "pagedown": ("PageDown", 34, ""), "pageup": ("PageUp", 33, ""),
        "home": ("Home", 36, ""), "end": ("End", 35, ""), "space": (" ", 32, " "),
    }

    def tugma(self, nom):
        kalit = str(nom or "").strip().lower()
        key, kod, matn = self._TUGMA.get(kalit, (nom, 0, ""))
        umumiy = {"key": key, "windowsVirtualKeyCode": kod, "nativeVirtualKeyCode": kod}
        self.call("Input.dispatchKeyEvent", dict(umumiy, type="keyDown", text=matn))
        self.call("Input.dispatchKeyEvent", dict(umumiy, type="keyUp"))
        time.sleep(0.25)
        return {"ok": True}

    def aylantir(self, yon="pastga", miqdor=600):
        delta = int(miqdor) * (-1 if str(yon).startswith(("yuq", "up")) else 1)
        self.js("window.scrollBy({top:%d, behavior:'instant'})" % delta)
        time.sleep(0.4)
        return {"ok": True, "scroll": self.js("Math.round(scrollY)")}

    # ── Foydalanuvchi paneldan to'g'ridan-to'g'ri boshqarganda ────────────
    # Agent ref bo'yicha ishlaydi, odam esa ko'rgan joyini bosadi. Shuning
    # uchun bu yerda xom koordinata bilan ishlaydigan alohida yo'l bor.
    def olcham(self):
        try:
            d = json.loads(self.js("JSON.stringify({w:innerWidth,h:innerHeight})") or "{}")
            return int(d.get("w") or OYNA_ENI), int(d.get("h") or OYNA_BOYI)
        except Exception:
            return OYNA_ENI, OYNA_BOYI

    def xom_bos(self, x, y, ikki=False):
        for tur in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", {
                "type": tur, "x": float(x), "y": float(y), "button": "left",
                "clickCount": 2 if ikki else 1,
                "buttons": 1 if tur == "mousePressed" else 0,
            })
        time.sleep(0.25)
        return {"ok": True}

    def xom_yoz(self, matn):
        """Fokusdagi maydonga matn kiritadi. Parol ham shu yo'ldan o'tadi —
        u hech qayerga yozilmaydi va faqat shu Mac ichida qoladi."""
        self.call("Input.insertText", {"text": str(matn)})
        return {"ok": True}

    def xom_aylantir(self, x, y, delta):
        self.call("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": float(x), "y": float(y),
            "deltaX": 0, "deltaY": float(delta),
        })
        return {"ok": True}

    def kut(self, matn="", selector="", soniya=15):
        chegara = time.time() + max(1, min(int(soniya), 60))
        while time.time() < chegara:
            try:
                if selector:
                    bor = self.js("!!document.querySelector(%s)" % json.dumps(selector))
                elif matn:
                    bor = self.js("(document.body?document.body.innerText:'').toLowerCase()"
                                  ".includes(%s.toLowerCase())" % json.dumps(matn))
                else:
                    bor = self.js("document.readyState === 'complete'")
                if bor:
                    return {"ok": True, "kutildi": round(soniya - (chegara - time.time()), 1)}
            except Exception:
                pass
            time.sleep(0.5)
        return {"ok": False, "sabab": "kutish vaqti tugadi"}


_SESSIYA = None
_SESSIYA_QULF = threading.Lock()


def sessiya():
    global _SESSIYA
    with _SESSIYA_QULF:
        if _SESSIYA is None:
            _SESSIYA = Brauzer()
        return _SESSIYA


def tirikmi():
    """Chrome ochiqmi — ishga tushirmasdan tekshiradi."""
    b = _SESSIYA
    if b is None:
        return False
    return b._port_band()


def oxirgi_kadr():
    """Jonli panel uchun: ochiq bo'lsa yangi kadr, aks holda oxirgi saqlangani."""
    b = sessiya()
    try:
        data = b.skrin()
        if data:
            return data, ""
    except Exception as exc:
        if b.oxirgi_skrin:
            return b.oxirgi_skrin, ""
        return b"", str(exc)[:200]
    return b.oxirgi_skrin, "Kadr olinmadi."


# Dastur qanday tugasa ham Chrome muloyim yopiladi.
atexit.register(hammasini_yop)
