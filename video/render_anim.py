#!/usr/bin/env python3
"""HTML/SVG animatsiyani HAQIQIY harakatlanuvchi MP4 videoga aylantiradi.

Ishlash tartibi: headless Chrome sahifani ochadi, har kadr uchun sahifadagi
`window.SEEK(t)` funksiyasini chaqiradi va skrinshot oladi — so'ng ffmpeg
kadrlardan video yig'adi. Vaqt brauzer soatidan emas, bizdan boshqariladi,
shuning uchun natija har safar bir xil (deterministik) chiqadi.

Sahifa shartnomasi (HTML shu ikkitasini e'lon qilishi kerak):
    window.DURATION = 30;          // soniya
    window.SEEK = function(t){ ... };   // t soniyaga mos holatni chizadi

Foydalanish:
    python3 render_anim.py --html scene.html --out kino.mp4 \
        --fps 30 --w 1920 --h 1080 \
        --audio ovoz1.mp3@2.5 --audio ovoz2.mp3@10 \
        --config timeline.json

    --audio FAYL@BOSHLANISH[:BALANDLIK]   (bir nechta marta yozish mumkin)
    --config FAYL.json  → sahifaga window.CONFIG bo'lib uzatiladi
"""
import argparse
import base64
import http.client
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def find_chrome():
    env = os.environ.get("CHROME")          # boshqa joydagi Chrome/Chromium uchun
    if env and os.path.exists(env):
        return env
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    p = shutil.which("google-chrome") or shutil.which("chromium")
    if p:
        return p
    sys.exit("Chrome topilmadi — Google Chrome o'rnating.")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ─────────────────────────── minimal WebSocket (CDP uchun) ───────────────────
class WS:
    """Faqat standart kutubxona bilan yozilgan kichik WebSocket mijozi."""

    def __init__(self, url, timeout=60):
        assert url.startswith("ws://")
        rest = url[5:]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        self.rf = self.sock.makefile("rb")
        while True:
            line = self.rf.readline()
            if line in (b"\r\n", b"\n", b""):
                break

    def _read_exact(self, n):
        buf = self.rf.read(n)
        if buf is None or len(buf) < n:
            raise ConnectionError("WebSocket uzildi")
        return buf

    def send(self, text):
        data = text.encode()
        head = bytearray([0x81])
        n = len(data)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
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
            b1, b2 = self._read_exact(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            masked, ln = b2 & 0x80, b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read_exact(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(ln) if ln else b""
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 0x8:                       # close
                raise ConnectionError("WebSocket yopildi")
            if op == 0x9:                       # ping → pong
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


class CDP:
    def __init__(self, ws_url):
        self.ws = WS(ws_url)
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def eval(self, expression, await_promise=True):
        r = self.call("Runtime.evaluate", {
            "expression": expression, "awaitPromise": await_promise,
            "returnByValue": True, "userGesture": True,
        })
        if r.get("exceptionDetails"):
            raise RuntimeError("Sahifa xatosi: " + json.dumps(r["exceptionDetails"])[:400])
        return r.get("result", {}).get("value")


# ─────────────────────────────────── render ──────────────────────────────────
def launch_chrome(chrome, port, w, h, profile):
    args = [
        chrome, "--headless=new", f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}", f"--window-size={w},{h}",
        "--hide-scrollbars", "--mute-audio", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions",
        "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
        "--force-device-scale-factor=1", "--allow-file-access-from-files",
        "--disable-features=CalculateNativeWinOcclusion",
        "about:blank",
    ]
    if sys.platform.startswith("linux") and os.geteuid() == 0:
        args.insert(1, "--no-sandbox")      # Linux konteynerida root bo'lsa Chrome shusiz ochilmaydi
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def page_ws_url(port, tries=60):
    for _ in range(tries):
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            c.request("GET", "/json/list")
            targets = json.loads(c.getresponse().read())
            for t in targets:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.4)
    sys.exit("Chrome DevTools'ga ulanib bo'lmadi.")


def parse_audio(spec):
    """'fayl.mp3@12.5:0.8' → (fayl, boshlanish, balandlik)"""
    vol = 1.0
    path = spec
    start = 0.0
    if "@" in spec:
        path, _, tail = spec.partition("@")
        if ":" in tail:
            tail, _, v = tail.partition(":")
            vol = float(v)
        start = float(tail or 0)
    if not os.path.exists(path):
        sys.exit(f"Audio topilmadi: {path}")
    return path, start, vol


def encode(frames_dir, fps, out, audios, w, h, ext):
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-framerate", str(fps), "-i", os.path.join(frames_dir, f"f%06d.{ext}")]
    for path, _, _ in audios:
        cmd += ["-i", path]

    if audios:
        parts, labels = [], []
        for i, (_, start, vol) in enumerate(audios):
            lbl = f"a{i}"
            parts.append(f"[{i+1}:a]adelay={int(start*1000)}|{int(start*1000)},volume={vol}[{lbl}]")
            labels.append(f"[{lbl}]")
        parts.append("".join(labels) + f"amix=inputs={len(audios)}:normalize=0:dropout_transition=0[aout]")
        cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]",
                "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-vf", f"scale={w}:{h}", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--duration", type=float, default=0, help="0 → sahifadagi window.DURATION")
    ap.add_argument("--audio", action="append", default=[], help="fayl.mp3@boshlanish[:balandlik]")
    ap.add_argument("--config", default="", help="JSON fayl → window.CONFIG")
    ap.add_argument("--png", action="store_true", help="PNG kadrlar (sekinroq, yo'qotishsiz)")
    ap.add_argument("--keep-frames", default="")
    a = ap.parse_args()

    html = os.path.abspath(a.html)
    if not os.path.exists(html):
        sys.exit(f"HTML topilmadi: {html}")
    audios = [parse_audio(s) for s in a.audio]
    cfg = {}
    if a.config:
        with open(a.config) as f:
            cfg = json.load(f)

    chrome = find_chrome()
    port = free_port()
    profile = tempfile.mkdtemp(prefix="anim-chrome-")
    frames = a.keep_frames or tempfile.mkdtemp(prefix="anim-frames-")
    os.makedirs(frames, exist_ok=True)
    ext = "png" if a.png else "jpg"
    proc = launch_chrome(chrome, port, a.w, a.h, profile)

    try:
        cdp = CDP(page_ws_url(port))
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride",
                 {"width": a.w, "height": a.h, "deviceScaleFactor": 1, "mobile": False})
        cdp.call("Page.navigate", {"url": "file://" + html})

        for _ in range(150):                      # sahifa tayyor bo'lishini kutamiz
            time.sleep(0.2)
            try:
                if cdp.eval("typeof window.SEEK === 'function'"):
                    break
            except Exception:
                pass
        else:
            sys.exit("Sahifada window.SEEK(t) topilmadi — HTML shartnomasiga qarang.")

        if cfg:
            cdp.eval("window.CONFIG = " + json.dumps(cfg) + "; if(window.APPLY_CONFIG) APPLY_CONFIG();")

        dur = a.duration or float(cdp.eval("window.DURATION || 0") or 0)
        if dur <= 0:
            sys.exit("Davomiylik noma'lum: --duration bering yoki window.DURATION e'lon qiling.")

        total = int(round(dur * a.fps))
        print(f"Render: {total} kadr, {a.fps} fps, {dur:.2f}s, {a.w}x{a.h}")
        shot = {"format": "png"} if a.png else {"format": "jpeg", "quality": 96}
        t0 = time.time()
        for i in range(total):
            t = i / a.fps
            cdp.eval(f"window.SEEK({t:.6f})")
            r = cdp.call("Page.captureScreenshot", shot)
            with open(os.path.join(frames, f"f{i+1:06d}.{ext}"), "wb") as f:
                f.write(base64.b64decode(r["data"]))
            if i % 30 == 0 or i == total - 1:
                el = time.time() - t0
                pct = (i + 1) / total
                eta = el / pct - el if pct else 0
                print(f"  {i+1}/{total} ({pct*100:5.1f}%)  qolgan ~{eta:4.0f}s", flush=True)

        print("ffmpeg bilan yig'ilmoqda…")
        encode(frames, a.fps, os.path.abspath(a.out), audios, a.w, a.h, ext)
        print("Tayyor:", a.out)
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
        if not a.keep_frames:
            shutil.rmtree(frames, ignore_errors=True)


if __name__ == "__main__":
    main()
