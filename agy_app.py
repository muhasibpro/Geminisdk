#!/usr/bin/env python3
"""Antigravity (agy) grafik interfeysi — API kalitsiz, Google account bilan.
Login terminal ochmaydi (fonda PTY). Chat papkaga ulanib fayllar ustida agent kabi ishlaydi.
Ishga tushirish:  python3 agy_app.py   |   http://localhost:8777
"""
import base64
import difflib
import fcntl
import glob
import json
import mimetypes
import os
import pty
import queue
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import termios
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import hisob                      # hisob-kitob yadrosi: bitta jurnal, hammasi shundan
import vositalar                  # brauzer, ekran, reja, web va rasm vositalari
import brauzer                    # Chrome boshqaruvi (jonli panel shundan oziqlanadi)
import ulanish                    # printer, TV, telefon va Telegram ulanishlari

PORT = int(os.environ.get("PORT", "8777"))
HOST = os.environ.get("HOST", "0.0.0.0")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


AGY = os.path.expanduser("~/.local/bin/agy")
if not os.path.exists(AGY):
    AGY = shutil.which("agy") or "agy"
CODEX = shutil.which("codex") or "/Applications/ChatGPT.app/Contents/Resources/codex"
CODEX_CHATGPT_MODEL = "__codex_chatgpt__"
HOME = os.path.expanduser("~")
# agy CLI print rejimida standart 5 daqiqalik limit qo'yadi va uzun vazifalarni
# (video render, ko'p fayl yozish) "timeout waiting for response" bilan uzib qo'yadi.
PRINT_TIMEOUT = os.environ.get("AGY_PRINT_TIMEOUT", "6h")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ATTACHMENT_DIR = os.path.join(PROJECT_ROOT, ".agy_uploads")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
ENV_LOCK = threading.Lock()
DESKTOP_CAPTURE_LOCK = threading.Lock()
# Agent saytda kirish talab qilingan joyga yetganda shu yerda kutib turadi;
# foydalanuvchi panelda kirib "Davom etish" ni bosgach ish davom etadi.
LOGIN_KUTISH = threading.Event()
LOGIN_SO_ROV = {"faol": False, "izoh": "", "boshlandi": 0.0, "soniya": 0}
def _load_env_file():
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

COMPOSER_INSTRUCTIONS = """You are AGY Master Composer, an autonomous Senior Staff Software Engineer and multi-agent-capable task orchestrator.

Execute the user's task end-to-end in the selected workspace with precision and ownership. Do not stop for routine confirmation, do not make surface-level patches, and do not claim success before the requested behavior is actually verified.

Execution protocol:
1. Read every applicable AGENTS.md and follow it strictly. Treat project conventions, existing architecture, and user scope as binding constraints.
2. Before editing, inspect the exact definitions, call sites, schemas, imports, routes, and related tests. Trace dependencies and determine the root cause; never guess at an API, data shape, or file path.
3. For complex work, break investigation, implementation, and verification into independent tracks. Use parallel tools or subagents only when they are actually available; otherwise complete those tracks systematically yourself without pretending they ran in parallel.
4. Make the complete set of focused multi-file edits needed for a coherent solution. Preserve working behavior and avoid unrelated rewrites.
5. Check edge cases, errors, backwards compatibility, and documentation whenever the change affects them.
6. Run the narrowest relevant test, compilation, lint, or dry-run after edits, followed by broader validation when practical. For Python projects, prefer the configured .venv/bin/python when it exists.
7. If a check fails, investigate and fix the cause before reporting completion. If validation cannot run, explain exactly what was blocked and what remains unverified.
8. End with a concise handoff: what changed, why it works, and the validation results.

Work autonomously and creatively inside these rules. The user's task follows below; execute it now:

"""

COMPLEX_TASK_RE = re.compile(
    r"\b(refactor|debug|fix|bug|architecture|multi[- ]?file|composer|agent|codebase|test|build|"
    r"tuzat|xato|loyiha|dastur|fayl|sinov|tekshir|arxitektura)\b",
    re.IGNORECASE,
)
VISUAL_TASK_RE = re.compile(
    r"\b(image|photo|picture|visual|video|animation|animate|generate|edit image|"
    r"rasm|surat|video|animatsiya|multfilm|qimirla|tahrirla|o'zgartir)\b",
    re.IGNORECASE,
)
TRUE_HUMAN_MOTION_RE = re.compile(
    r"(haqiqiy|real|fotorealistik|photo|rasm).{0,48}(odam|inson|human|person|qimir|harakat|motion|animat|video)"
    r"|(odam|inson|human|person).{0,48}(haqiqiy|real|qimir|harakat|motion|animat|video)"
    r"|haqiqiy\s+odamdek|real\s+odamdek|image[- ]?to[- ]?video",
    re.IGNORECASE,
)
VISUAL_PRODUCTION_INSTRUCTIONS = """

Visual production mode is active.
- If the user attached an image, it is the source of truth. Inspect it before acting and edit only the requested areas; do not replace it with an unrelated image or invent unrequested changes.
- For image creation or edits, use the available image-generation or image-editing capability. Save the resulting asset in the workspace and return its exact local path so the chat can render it.
- For photorealistic requests, explicitly target a photorealistic DSLR-style result with real people and natural lighting; do not substitute cartoon, illustration, or 3D-render styling.
- Every video request is a new production run. Do not list, replay, or present an existing MP4 as the answer unless the user explicitly asks for a previous video. Create a new, uniquely named output under the workspace and report that exact path.
- For video, first identify whether the user needs a vector cartoon, a 2D photo rig, or genuine image-to-video motion. Follow the repository's video/ pipeline and AGENTS.md exactly. Never fake animation with a static-image zoom/pan, Ken Burns effect, slideshow transitions, or a token moving overlay.
- For requested edits to a supplied image, preserve its identity, composition, and unaffected areas. State a limitation instead of silently producing a different result.
- Verify generated image/video files exist and report their exact output paths.
"""
TRUE_HUMAN_MOTION_INSTRUCTIONS = """

True Human Motion Mode is active. The user explicitly wants a person in a real photo to move like a real person, not a photo cutout with a moving limb.

Non-negotiable rules:
- Never reuse, show, rename, or report any prior MP4 as this request's result. The user asked for a new video.
- Do not call a 2D layer, CSS transform, camera move, zoom, parallax, or single-limb rotation “real human animation”. The repository's local photo-rig pipeline is only 2D articulated motion and does not satisfy this request.
- First run `.venv/bin/python video/make_ai_real_promo.py --check-config`. When it reports ready and the user supplied a reference image, use `video/make_ai_real_promo.py` for the new production; it uses the server-side Gemini Veo, Fal, or Replicate image-to-video API and puts the final MP4 in the workspace root. Never expose or print API keys from `.env`.
- Before rendering, check whether a genuine image-to-video capability is configured and available. Use it only when it can synthesize coherent full-body motion while preserving the supplied person's identity and requested action.
- If no genuine image-to-video capability is available, say so clearly before producing a file. Do not create a humorous partial-motion substitute or claim that it meets the request. Offer the repository's labelled 2D rig only as an explicit fallback, never as the default.
- When genuine image-to-video is available, use the supplied photo as reference, specify the exact body action, preserve face/clothes/background unless changed, and verify the newly generated video file exists.
"""
MODEL_CACHE = {"checked_at": 0.0, "models": []}
STATUS_CACHE = {"checked_at": 0.0, "signed": False, "models": [], "refreshing": False}
STATUS_LOCK = threading.Lock()
CODEX_STATUS_CACHE = {"checked_at": 0.0, "available": False, "ready": False, "status": ""}
CODEX_STATUS_LOCK = threading.Lock()
CODEX_THREADS = {}
CODEX_THREADS_LOCK = threading.Lock()

URL_RE = re.compile(r"https://accounts\.google\.com/\S+")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
AUTH_RESULT_RE = re.compile(r"applyAuthResult:\s*email=([^,\s]+),\s*authMethod=([^,\s]+)", re.IGNORECASE)
GOOGLE_AVATAR_RE = re.compile(r"https://lh3\.googleusercontent\.com/[^\s\"'<>]+", re.IGNORECASE)
ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Za-z]|\x1b[=>]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

_EMAIL = None
_GOOGLE_ACCOUNT = None


def find_email():
    global _EMAIL
    if _EMAIL is not None:
        return _EMAIL
    files = [
        os.path.expanduser("~/.gemini/config/config.json"),
        os.path.expanduser("~/.gemini/config/projects/default-cli-project.json"),
        os.path.expanduser("~/.gemini/antigravity-cli/jetski_state.pbtxt"),
        os.path.expanduser("~/.gemini/antigravity-cli/cli.log"),
    ]
    files += glob.glob(os.path.expanduser("~/.gemini/antigravity-cli/*.json"))
    for p in files:
        try:
            content = open(p, encoding="utf-8", errors="ignore").read()
            emails = EMAIL_RE.findall(content)
            if emails:
                _EMAIL = emails[-1]
                return _EMAIL
        except Exception:
            pass
    _EMAIL = ""
    return _EMAIL


def clear_google_account_cache():
    global _EMAIL, _GOOGLE_ACCOUNT
    _EMAIL = None
    _GOOGLE_ACCOUNT = None


def find_google_account():
    """Return only Google identity metadata that the local CLI session exposes."""
    global _GOOGLE_ACCOUNT
    if _GOOGLE_ACCOUNT is not None:
        return _GOOGLE_ACCOUNT

    email = find_email()
    auth_method = ""
    avatar_url = ""
    log_paths = glob.glob(os.path.expanduser("~/.gemini/antigravity-cli/log/*.log"))
    for path in sorted(log_paths, key=lambda item: os.path.getmtime(item)):
        try:
            content = open(path, encoding="utf-8", errors="ignore").read()
            matches = AUTH_RESULT_RE.findall(content)
            if matches:
                logged_email, auth_method = matches[-1]
                email = logged_email or email
            avatars = GOOGLE_AVATAR_RE.findall(content)
            if avatars:
                avatar_url = avatars[-1].rstrip(".,;)")
        except OSError:
            continue

    account_type = {
        "consumer": "Google Consumer",
        "workspace": "Google Workspace",
        "cloud": "Google Cloud",
    }.get(auth_method.lower(), "Google Account")
    _GOOGLE_ACCOUNT = {
        "email": email,
        "accountType": account_type,
        "plan": "Tarif ma’lumoti Google CLI tomonidan berilmagan",
        "avatarUrl": avatar_url,
    }
    return _GOOGLE_ACCOUNT


class PtyLogin:
    def __init__(self):
        self.pid = None
        self.fd = None
        self.buf = ""
        self.url = None
        self._menu = False
        self.lock = threading.Lock()

    def running(self):
        if self.pid is None:
            return False
        try:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
            if pid == 0:
                return True
            self.pid = None
            return False
        except ChildProcessError:
            self.pid = None
            return False

    def start(self):
        self.stop()
        with self.lock:
            self.buf = ""
            self.url = None
            self._menu = False
        env = dict(os.environ, TERM="xterm-256color", NO_COLOR="1")
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.execve(AGY, [AGY], env)
            except Exception:
                os._exit(127)
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 45, 140, 0, 0))
        except Exception:
            pass
        self.pid = pid
        self.fd = fd
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        fd = self.fd
        while True:
            try:
                r, _, _ = select.select([fd], [], [], 0.4)
                if fd not in r:
                    if not self.running():
                        break
                    continue
                data = os.read(fd, 4096)
                if not data:
                    break
            except OSError:
                break
            text = ANSI_RE.sub("", data.decode("utf-8", "replace"))
            with self.lock:
                self.buf = (self.buf + text)[-12000:]
                m = URL_RE.search(self.buf)
                if m and not self.url:
                    self.url = m.group(0)
                if not self._menu and "OAuth" in self.buf:
                    try:
                        os.write(fd, b"\r")
                        self._menu = True
                    except OSError:
                        pass

    def write_line(self, t):
        if self.fd is not None:
            try:
                os.write(self.fd, (t.strip() + "\r").encode())
                return True
            except OSError:
                return False
        return False

    def stop(self):
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except Exception:
                pass
            try:
                os.waitpid(self.pid, 0)
            except Exception:
                pass
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
        self.pid = None
        self.fd = None


LOGIN = PtyLogin()
CONVO = False


def _refresh_status_cache():
    try:
        result = subprocess.run([AGY, "models"], capture_output=True, text=True, timeout=8)
    except Exception:
        result = None

    models = []
    signed = False
    if result:
        output = result.stdout or ""
        low = (output + (result.stderr or "")).lower()
        signed = result.returncode == 0 and "sign in" not in low and "sign-in" not in low and "authenticat" not in low
        if signed:
            for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}", output):
                lowered = token.lower()
                if any(keyword in lowered for keyword in ("gemini", "flash", "pro", "claude", "gpt")) and token not in models:
                    models.append(token)

    with STATUS_LOCK:
        if result is not None:
            STATUS_CACHE["signed"] = signed
            STATUS_CACHE["models"] = models
            STATUS_CACHE["checked_at"] = time.time()
            if models:
                MODEL_CACHE["models"] = models
                MODEL_CACHE["checked_at"] = time.time()
        STATUS_CACHE["refreshing"] = False
    if signed and LOGIN.running():
        LOGIN.stop()


def status_probe():
    now = time.time()
    with STATUS_LOCK:
        if not STATUS_CACHE["checked_at"]:
            STATUS_CACHE["signed"] = bool(find_email())
        refresh_needed = now - STATUS_CACHE["checked_at"] >= 30
        if refresh_needed and not STATUS_CACHE["refreshing"]:
            STATUS_CACHE["refreshing"] = True
            threading.Thread(target=_refresh_status_cache, daemon=True).start()
        return STATUS_CACHE["signed"], list(STATUS_CACHE["models"])


def available_models():
    """Model ro'yxatini qisqa muddat keshlaydi, har chatda CLI'ni qayta chaqirmaydi."""
    now = time.time()
    if now - MODEL_CACHE["checked_at"] < 300:
        return MODEL_CACHE["models"]
    _, models = status_probe()
    if models:
        MODEL_CACHE["checked_at"] = now
        MODEL_CACHE["models"] = models
    return MODEL_CACHE["models"]


def codex_cli_status():
    now = time.time()
    with CODEX_STATUS_LOCK:
        if now - CODEX_STATUS_CACHE["checked_at"] < 30:
            return dict(CODEX_STATUS_CACHE)

    available = bool(CODEX and os.path.isfile(CODEX) and os.access(CODEX, os.X_OK))
    ready = False
    status = "Codex CLI topilmadi. ChatGPT desktop ilovasini o‘rnating yoki Codex CLI ni sozlang."
    if available:
        try:
            result = subprocess.run(
                [CODEX, "login", "status"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            ready = result.returncode == 0 and "logged in" in output.lower()
            status = "Codex CLI ChatGPT hisobingiz bilan tayyor." if ready else (
                output[:240] or "Codex CLI ga `codex login` orqali kiring."
            )
        except Exception as exc:
            status = "Codex CLI tekshirilmadi: " + str(exc)

    value = {
        "checked_at": now,
        "available": available,
        "ready": ready,
        "status": status,
    }
    with CODEX_STATUS_LOCK:
        CODEX_STATUS_CACHE.update(value)
        return dict(CODEX_STATUS_CACHE)


def is_visual_request(prompt, has_attachment=False):
    return has_attachment or bool(VISUAL_TASK_RE.search(prompt or ""))


def is_true_human_motion_request(prompt):
    return bool(TRUE_HUMAN_MOTION_RE.search(prompt or ""))


def select_composer_model(prompt, requested_model, visual=False):
    """Murakkab coding so'rovlar uchun mavjud eng kuchli modelni tanlaydi."""
    if requested_model:
        return requested_model
    if not (visual or COMPLEX_TASK_RE.search(prompt or "") or len(prompt or "") >= 220):
        return ""

    def score(name):
        value = name.lower()
        points = 0
        if "pro" in value: points += 100
        if "claude" in value: points += 90
        if "sonnet" in value: points += 80
        if "gemini" in value: points += 30
        if "flash" in value: points -= 80
        if "lite" in value: points -= 60
        return points

    models = available_models()
    return max(models, key=score) if models else ""


def composer_prompt(prompt, visual=False, true_motion=False):
    instructions = COMPOSER_INSTRUCTIONS
    if visual:
        instructions += VISUAL_PRODUCTION_INSTRUCTIONS
    if true_motion:
        instructions += TRUE_HUMAN_MOTION_INSTRUCTIONS
    return instructions + (prompt or "").strip()


def persist_attached_image(image):
    if not isinstance(image, dict):
        return ""

    mime_type = str(image.get("mime_type") or "").lower()
    encoded_data = image.get("data")
    extension = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }.get(mime_type)
    if not extension or not isinstance(encoded_data, str):
        return ""

    try:
        raw_image = base64.b64decode(encoded_data, validate=True)
    except (ValueError, TypeError):
        return ""
    if not raw_image or len(raw_image) > 25 * 1024 * 1024:
        return ""

    os.makedirs(ATTACHMENT_DIR, exist_ok=True)
    filename = f"reference_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.{extension}"
    output_path = os.path.join(ATTACHMENT_DIR, filename)
    with open(output_path, "wb") as output_file:
        output_file.write(raw_image)
    return output_path


def _load_video_provider_module():
    video_dir = os.path.join(PROJECT_ROOT, "video")
    if video_dir not in sys.path:
        sys.path.insert(0, video_dir)
    from ai_video_generator import provider_label, provider_ready, provider_setup_hint
    return provider_label, provider_ready, provider_setup_hint


def video_configuration_status():
    provider_label, provider_ready, provider_setup_hint = _load_video_provider_module()
    ready, status = provider_ready()
    return {
        "provider": "gemini",
        "label": provider_label("gemini"),
        "keyConfigured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "ready": ready,
        "status": status,
        "setupHint": provider_setup_hint("gemini"),
    }


def save_gemini_api_key(value):
    api_key = str(value or "").strip()
    if len(api_key) < 20 or len(api_key) > 512 or any(char.isspace() for char in api_key):
        raise ValueError("Gemini API kaliti noto'g'ri formatda.")

    values = {
        "GEMINI_API_KEY": api_key,
        "AI_VIDEO_PROVIDER": "gemini",
    }
    with ENV_LOCK:
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as env_file:
                lines = env_file.readlines()
        except FileNotFoundError:
            lines = []

        remaining = set(values)
        updated_lines = []
        for line in lines:
            match = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=.*$", line)
            key_name = match.group(2) if match else ""
            if key_name in values:
                updated_lines.append(f"{key_name}={values[key_name]}\n")
                remaining.discard(key_name)
            else:
                updated_lines.append(line)
        if updated_lines and not updated_lines[-1].endswith("\n"):
            updated_lines[-1] += "\n"
        for key_name in sorted(remaining):
            updated_lines.append(f"{key_name}={values[key_name]}\n")

        temporary_path = f"{ENV_PATH}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as env_file:
                env_file.writelines(updated_lines)
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, ENV_PATH)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    os.environ["GEMINI_API_KEY"] = api_key
    os.environ["AI_VIDEO_PROVIDER"] = "gemini"


def clear_gemini_api_key():
    with ENV_LOCK:
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as env_file:
                lines = env_file.readlines()
        except FileNotFoundError:
            lines = []

        updated_lines = []
        found = False
        for line in lines:
            match = re.match(r"^(\s*)GEMINI_API_KEY\s*=.*$", line)
            if match:
                updated_lines.append("GEMINI_API_KEY=\n")
                found = True
            else:
                updated_lines.append(line)
        if not found:
            if updated_lines and not updated_lines[-1].endswith("\n"):
                updated_lines[-1] += "\n"
            updated_lines.append("GEMINI_API_KEY=\n")

        temporary_path = f"{ENV_PATH}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as env_file:
                env_file.writelines(updated_lines)
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, ENV_PATH)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
    os.environ["GEMINI_API_KEY"] = ""


# OpenAI API'da HAQIQATAN mavjud ovozlar. Ilgari bu ro'yxatda ChatGPT Desktop'ning
# mahsulot nomlari (sol, breeze, cove, ember…) turardi — ular API ovoz ID'si emas,
# shuning uchun har bir so'rov 400 qaytarib, jimgina edge-tts ga tushib ketardi.
REALTIME_MODEL_DEFAULT = "gpt-realtime-2.1"     # eng yangi jonli ovoz modeli
OPENAI_TTS_VOICES = (
    "marin", "cedar", "coral", "sage", "verse", "ash",
    "ballad", "alloy", "echo", "shimmer", "nova", "fable", "onyx",
)
# Eski (mavjud bo'lmagan) nomlar saqlanib qolgan bo'lsa — eng yaqin haqiqiy ovozga
# yo'naltiramiz, shunda foydalanuvchi sozlamasi buzilmaydi.
OPENAI_VOICE_ALIASES = {
    "sol": "marin", "breeze": "shimmer", "juniper": "nova", "sky": "coral",
    "cove": "cedar", "ember": "ash", "arbor": "onyx", "spruce": "echo", "vale": "sage",
    "tts-1": "marin",
}
# TTS ga beriladigan uslub ko'rsatmasi — aksentsiz, tabiiy o'zbekcha talaffuz uchun.
# Jonli suhbat ko'rsatmasi bilan bir xil xarakter — ikkalasi bir odamdek eshitilsin.
OPENAI_TTS_STYLE = (
    "You are speaking Uzbek to a close friend you like. Warm, easy, quietly amused — as if you are "
    "half-smiling the whole time. Light and effortless, never formal, never like a news reader. "
    "Vary your pitch naturally and let some words trail off softly. Leave small natural pauses "
    "between thoughts. Start answering promptly, with no long silence before you begin. Perfect native Tashkent Uzbek pronunciation with no "
    "foreign, English or Russian accent whatsoever. "
    "Read numbers and sums the way an Uzbek speaker would say them aloud."
)
VOICE_AUDIO_MIME_TYPES = {
    "audio/webm": "recording.webm",
    "audio/ogg": "recording.ogg",
    "audio/wav": "recording.wav",
    "audio/x-wav": "recording.wav",
    "audio/mp4": "recording.m4a",
    "audio/mpeg": "recording.mp3",
}
VOICE_PHONETIC_REPAIRS = (
    (r"\bovoid\b", "ovoz"),
    (r"\byalantiriladi\b", "aylantiriladi"),
    (r"\bnotog['’]?ri\b", "noto‘g‘ri"),
    (r"\bmuumkinmi\b", "mumkinmi"),
    (r"\bvaat\b", "vaqt"),
)


def _update_env_values(values):
    """Atomically update local .env values without returning their contents."""
    with ENV_LOCK:
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as env_file:
                lines = env_file.readlines()
        except FileNotFoundError:
            lines = []

        remaining = set(values)
        updated_lines = []
        for line in lines:
            match = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=.*$", line)
            key_name = match.group(2) if match else ""
            if key_name in values:
                updated_lines.append(f"{key_name}={values[key_name]}\n")
                remaining.discard(key_name)
            else:
                updated_lines.append(line)
        if updated_lines and not updated_lines[-1].endswith("\n"):
            updated_lines[-1] += "\n"
        for key_name in sorted(remaining):
            updated_lines.append(f"{key_name}={values[key_name]}\n")

        temporary_path = f"{ENV_PATH}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as env_file:
                env_file.writelines(updated_lines)
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, ENV_PATH)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)


def voice_configuration_status():
    configured = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    # Faqat API'da haqiqatan mavjud ovozlar. Har biri sinovdan o'tgan.
    voice_details = [
        {"id": "marin", "name": "Marin (Ayol, iliq — Tavsiya ✨)", "category": "openai", "provider": "openai"},
        {"id": "cedar", "name": "Cedar (Erkak, tabiiy — Tavsiya ✨)", "category": "openai", "provider": "openai"},
        {"id": "coral", "name": "Coral (Ayol, jonli)", "category": "openai", "provider": "openai"},
        {"id": "shimmer", "name": "Shimmer (Ayol, tiniq)", "category": "openai", "provider": "openai"},
        {"id": "nova", "name": "Nova (Ayol, quvnoq)", "category": "openai", "provider": "openai"},
        {"id": "sage", "name": "Sage (Ayol, sokin)", "category": "openai", "provider": "openai"},
        {"id": "ash", "name": "Ash (Erkak, sokin)", "category": "openai", "provider": "openai"},
        {"id": "ballad", "name": "Ballad (Erkak, mayin)", "category": "openai", "provider": "openai"},
        {"id": "verse", "name": "Verse (Erkak, ifodali)", "category": "openai", "provider": "openai"},
        {"id": "echo", "name": "Echo (Erkak, past ovoz)", "category": "openai", "provider": "openai"},
        {"id": "onyx", "name": "Onyx (Erkak, vazmin)", "category": "openai", "provider": "openai"},
        {"id": "alloy", "name": "Alloy (Neytral)", "category": "openai", "provider": "openai"},
        {"id": "fable", "name": "Fable (Hikoyachi)", "category": "openai", "provider": "openai"},
        {"id": "uz-UZ-SardorNeural", "name": "Sardor (O‘zbekcha Edge, Erkak)", "category": "uzbek", "provider": "edge"},
        {"id": "uz-UZ-MadinaNeural", "name": "Madina (O‘zbekcha Edge, Ayol)", "category": "uzbek", "provider": "edge"},
    ]
    voice_ids = [v["id"] for v in voice_details]
    return {
        "keyConfigured": configured,
        "ready": True,
        "model": os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        "realtimeModel": os.environ.get("OPENAI_REALTIME_MODEL", REALTIME_MODEL_DEFAULT),
        "transcriptionModel": os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-live-transcribe"),
        "eagerness": os.environ.get("OPENAI_REALTIME_EAGERNESS", "high"),
        "speed": os.environ.get("OPENAI_REALTIME_SPEED", "1.05"),
        # Ovoz oynasidagi tanlagichlar shu ro'yxatlardan to'ldiriladi
        "realtimeModels": ["gpt-realtime-2.1", "gpt-realtime"],
        "transcribeModels": ["gpt-live-transcribe", "gpt-4o-transcribe",
                             "gpt-4o-mini-transcribe", "whisper-1"],
        "eagerLevels": [
            {"id": "high",   "name": "Tez — darhol javob beradi"},
            {"id": "medium", "name": "O'rtacha — bir oz kutadi"},
            {"id": "low",    "name": "Vazmin — gapni to'liq kutadi"},
        ],
        "defaultVoice": os.environ.get("OPENAI_REALTIME_VOICE", "marin").strip() or "marin",
        "voices": voice_ids,
        "voiceDetails": voice_details,
        "status": (
            "OpenAI ovozlari (Marin, Cedar…) va o‘zbekcha Edge-TTS tayyor."
            if configured
            else "OpenAI kaliti yo‘q — faqat o‘zbekcha Edge-TTS (Madina, Sardor) ishlaydi."
        ),
        "solApiAvailable": configured,
        "solNote": "Jonli suhbat " + os.environ.get("OPENAI_REALTIME_MODEL", REALTIME_MODEL_DEFAULT) + " ustida ishlaydi.",
    }


def save_openai_api_key(value):
    api_key = str(value or "").strip()
    if len(api_key) < 20 or len(api_key) > 512 or any(char.isspace() for char in api_key):
        raise ValueError("OpenAI API kaliti noto‘g‘ri formatda.")
    _update_env_values({"OPENAI_API_KEY": api_key})
    os.environ["OPENAI_API_KEY"] = api_key


def clear_openai_api_key():
    _update_env_values({"OPENAI_API_KEY": ""})
    os.environ["OPENAI_API_KEY"] = ""


def _openai_api_key():
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OpenAI API kaliti sozlanmagan. Sozlamalardan kalitni kiriting.")
    return api_key


def _openai_xato_matni(detail, code=0):
    """OpenAI xatosini foydalanuvchi tushunadigan va nima qilishni biladigan
    matnga aylantiradi. HTTP xatosi ham, oqim ichidagi xato hodisasi ham shu
    yerdan o'tadi — ikkalasi bir xil ko'rinsin."""
    past = str(detail or "").lower()
    if ("credit" in past or "quota" in past or "billing" in past
            or "insufficient" in past or code == 429):
        return ("OpenAI hisobingizda mablag' tugagan — shuning uchun ChatGPT Sol "
                "javob bera olmaydi.\n\n"
                "**Nima qilish:** platform.openai.com/settings/organization/billing "
                "sahifasiga kirib balans to'ldiring. Bu ChatGPT obunasidan alohida "
                "hisob — Plus yoki Pro obunasi API uchun ishlamaydi.\n\n"
                "Kredit qo'shilgunicha hisob daftari, Sozlamalar → Ulanishlar va "
                "brauzer paneli ishlayveradi.")
    if code == 401 or "api key" in past or "unauthorized" in past:
        return ("OpenAI API kaliti qabul qilinmadi. `.env` dagi `OPENAI_API_KEY` ni "
                "tekshiring — kalit o'chirilgan yoki noto'g'ri ko'chirilgan bo'lishi mumkin.")
    return "OpenAI xatosi" + (": " + str(detail)[:220] if detail else ".")


def _openai_error_message(error):
    detail = ""
    try:
        body = error.read().decode("utf-8", "replace")
        detail = str(json.loads(body).get("error", {}).get("message") or body)
    except Exception:
        pass
    return _openai_xato_matni(detail, getattr(error, "code", 0))


def _openai_request(path, data, content_type, timeout=45):
    request = urllib.request.Request(
        "https://api.openai.com" + path,
        data=data,
        method="POST",
        headers={
            "Authorization": "Bearer " + _openai_api_key(),
            "Content-Type": content_type,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        raise ValueError(_openai_error_message(error)) from error
    except urllib.error.URLError as error:
        raise ValueError("OpenAI ovoz xizmatiga ulanib bo‘lmadi: " + str(error.reason)) from error




def _clean_text_for_speech(text):
    clean = re.sub(r"\x60\x60\x60[\s\S]*?\x60\x60\x60", " ", str(text or ""))
    clean = re.sub(r"!\[[^\]]*\]\([^)]+\)|\[[^\]]*\]\([^)]+\)", " ", clean)
    clean = re.sub(r"\x60([^\x60]*)\x60", r"\1", clean)
    clean = re.sub(r"(^|\n)\s{0,3}[#>*-]+\s*", r"\1", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:900]


def trigger_chatgpt_desktop_voice_session(prompt: str = "") -> bool:
    """Activates ChatGPT Desktop App and launches native Voice Mode (Start voice chat button).
    
    Uses the confirmed working method: Tab x3 to navigate to the Start voice chat
    waveform button, then Space to press it — without typing any text into the input.
    """
    # Confirmed working: 3x Tab navigates to the Start Voice Chat waveform button,
    # then Space activates it. This avoids Option+Space which only focuses the input.
    script = '''
tell application "ChatGPT" to activate
delay 0.5
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 49
end tell
'''
    res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return res.returncode == 0


def generate_edge_tts_speech(text, voice="uz-UZ-SardorNeural", rate="+25%"):
    clean = _clean_text_for_speech(text)
    if not clean:
        raise ValueError("O‘qish uchun matn topilmadi.")
    import asyncio
    import edge_tts
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    async def _run():
        communicate = edge_tts.Communicate(clean, voice, rate=rate)
        await communicate.save(tmp_path)

    try:
        asyncio.run(_run())
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        return audio_bytes
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass



def _multipart_audio_payload(audio, mime_type):
    boundary = "----muhasibvoice" + uuid.uuid4().hex
    filename = VOICE_AUDIO_MIME_TYPES[mime_type]
    # DIQQAT: "language": "uz" YOZMA — OpenAI uni qabul qilmaydi va 400 qaytaradi
    # ("Language 'uz' is not supported"). Til ko'rsatilmasa avtomatik aniqlanadi,
    # imlo esa quyidagi prompt bilan o'zbek lotiniga yo'naltiriladi.
    # whisper-1 turkcha imloga og'ib ketadi ("iki yüz min"), gpt-4o-transcribe
    # esa prompt bilan to'g'ri yozadi ("ikki yuz ming") — shuning uchun shu tanlandi.
    fields = {
        "model": os.environ.get("OPENAI_TRANSCRIBE_HTTP_MODEL", "gpt-4o-transcribe").strip()
                 or "gpt-4o-transcribe",
        "prompt": (
            "Bu o‘zbek tilidagi suhbat. Matnni faqat o‘zbek lotin alifbosida yoz. "
            "Misol: Salom, bugun kassada ikki million so‘m bor. Alisherga ikki yuz ming qarz berdim. "
            "MUHASIB POS, kassa, qarz, ombor, savdo, foyda, hisobot, xarajat, kirim."
        ),
    }
    parts = []
    for name, value in fields.items():
        parts.extend(
            [
                ("--" + boundary + "\r\n").encode(),
                ('Content-Disposition: form-data; name="' + name + '"\r\n\r\n').encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    parts.extend(
        [
            ("--" + boundary + "\r\n").encode(),
            (
                'Content-Disposition: form-data; name="file"; filename="'
                + filename + '"\r\n'
            ).encode(),
            ("Content-Type: " + mime_type + "\r\n\r\n").encode(),
            audio,
            b"\r\n",
            ("--" + boundary + "--\r\n").encode(),
        ]
    )
    return b"".join(parts), "multipart/form-data; boundary=" + boundary


def normalize_voice_audio_mime_type(mime_type):
    """Map browser MediaRecorder values to the MIME types accepted by OpenAI."""
    normalized = str(mime_type or "").split(";", 1)[0].strip().lower()
    aliases = {
        "audio/x-m4a": "audio/mp4",
        "audio/mp3": "audio/mpeg",
        "application/ogg": "audio/ogg",
        "video/webm": "audio/webm",
    }
    return aliases.get(normalized, normalized)


def normalize_voice_transcript(text):
    normalized = str(text or "").strip()
    for pattern, replacement in VOICE_PHONETIC_REPAIRS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def transcribe_openai_audio(encoded_audio, mime_type):
    mime_type = normalize_voice_audio_mime_type(mime_type)
    if mime_type not in VOICE_AUDIO_MIME_TYPES:
        raise ValueError("Audio formati qo‘llab-quvvatlanmaydi. WEBM, WAV, MP3, M4A yoki OGG yuboring.")
    try:
        audio = base64.b64decode(str(encoded_audio or ""), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Mikrofon audio ma’lumoti o‘qilmadi.") from exc
    if not audio or len(audio) > 25 * 1024 * 1024:
        raise ValueError("Audio bo‘sh yoki 25 MB dan katta.")
    payload, content_type = _multipart_audio_payload(audio, mime_type)
    body, _ = _openai_request("/v1/audio/transcriptions", payload, content_type, timeout=90)
    try:
        text = json.loads(body.decode("utf-8")).get("text", "")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("OpenAI transkripsiya javobi o‘qilmadi.") from exc
    text = normalize_voice_transcript(text)
    if not text:
        raise ValueError("Ovozdan matn aniqlanmadi. Qayta aniqroq gapiring.")
    return text


def _true_motion_prompt(user_prompt):
    return (
        "Create a genuine photorealistic image-to-video clip from the supplied reference photo. "
        "The person moves with natural biological full-body motion, subtle blinking, realistic facial expressions, "
        "natural hand gestures, stable anatomy, and coherent clothing. Preserve identity, face, background, "
        "and camera composition unless the user explicitly asks otherwise. No 2D cutout animation, no still-image "
        "camera pan, no warped limbs, no text overlay. User direction: " + (user_prompt or "").strip()
    )


def stream_true_human_motion(prompt, attachment_path, on_proc=None):
    if not attachment_path:
        message = "Real video uchun avval real rasmni chatga biriktiring. Rasm bo'lmasa vektor video yaratilmaydi."
        yield {"error": message}
        yield {"done": True, "text": "⚠️ " + message}
        return

    try:
        provider_label, provider_ready, provider_setup_hint = _load_video_provider_module()
        ready, status = provider_ready()
        label = provider_label()
        setup_hint = provider_setup_hint()
    except Exception as exc:
        ready, status = False, str(exc)
        label = "AI video provayderi"
        setup_hint = "Video provayderi sozlamalarini tekshiring."
    if not ready:
        message = (
            "Haqiqiy AI video sozlanmagan: " + status + ". "
            + setup_hint + " Kalit bo'lmaganda 8777 vektor videoga qaytmaydi."
        )
        yield {"action": "🔐 " + label + " kaliti tekshirildi"}
        yield {"error": message}
        yield {"done": True, "text": "⚠️ " + message}
        return

    script = os.path.join(PROJECT_ROOT, "video", "make_ai_real_promo.py")
    args = [
        sys.executable, script, attachment_path,
        "--motion-prompt", _true_motion_prompt(prompt),
    ]
    yield {"action": "🎞️ " + label + " Image-to-Video · yangi real motion klip boshlandi"}
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=PROJECT_ROOT,
        start_new_session=True,
    )
    if on_proc:
        on_proc(process)

    output_lines = []
    stream_queue = queue.Queue()

    def pump_output():
        try:
            for line in process.stdout:
                stream_queue.put(line)
        finally:
            stream_queue.put(None)

    threading.Thread(target=pump_output, daemon=True).start()
    while True:
        try:
            line = stream_queue.get(timeout=2)
        except queue.Empty:
            yield {"ping": True}
            continue
        if line is None:
            break
        clean = line.strip()
        if not clean:
            continue
        output_lines.append(clean)
        yield {"action": clean[:400]}

    code = process.wait()
    output = "\n".join(output_lines)
    if code:
        failures = [line[1:].strip() for line in output_lines if line.startswith("❌")]
        detail = failures[-1] if failures else (output[-800:] or "AI video jarayoni xato bilan tugadi.")
        message = "Haqiqiy AI video yaratilolmadi. " + detail
        yield {"error": message}
        yield {"done": True, "text": "⚠️ " + message}
        return
    generated = []
    for candidate in re.findall(r"(/[^\r\n]+?\.mp4)", output):
        path = os.path.abspath(os.path.expanduser(candidate.strip()))
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            generated.append(path)
    if not generated:
        message = "AI jarayoni tugadi, lekin tayyor MP4 fayl topilmadi. Video muvaffaqiyatli deb belgilanmadi."
        yield {"error": message}
        yield {"done": True, "text": "⚠️ " + message}
        return
    yield {"done": True, "text": "✅ Haqiqiy AI video tayyor.\n" + generated[-1]}


def _tool_label(tool_name, parameters=None):
    name = str(tool_name or "").lower()
    labels = (
        (("image", "generate_image", "imagegen"), "🎨 Rasm yaratilmoqda"),
        (("video", "generate_video"), "🎬 Video tayyorlanmoqda"),
        (("read", "open_file", "cat"), "📄 Fayl o'qilmoqda"),
        (("write", "edit", "patch", "apply"), "✍️ Fayllar yangilanmoqda"),
        (("search", "find", "grep", "rg"), "🔎 Kod bazasi qidirilmoqda"),
        (("browser", "web", "fetch"), "🌐 Ma'lumot tekshirilmoqda"),
        (("exec", "command", "terminal", "shell"), "⌨️ Buyruq bajarilmoqda"),
    )
    label = "🛠️ Agent ishlayapti" if not name else "🛠️ " + str(tool_name).replace("_", " ")[:80]
    for matches, candidate in labels:
        if any(match in name for match in matches):
            label = candidate
            break

    if isinstance(parameters, dict):
        for key_name in ("path", "file_path", "file", "filename"):
            value = parameters.get(key_name)
            if isinstance(value, str) and value.strip():
                filename = os.path.basename(value.rstrip("/"))
                if filename:
                    return label + " · " + filename[:96]
    return label


def _codex_item_action(item):
    item_type = str((item or {}).get("type") or "")
    if item_type == "reasoning":
        return "🧠 Codex tahlil qilmoqda"
    if item_type == "command_execution":
        command = str(item.get("command") or "buyruq")
        return "⌨️ Codex buyruq bajaradi · " + command[:100]
    if item_type == "file_change":
        return "📝 Codex fayllarni o‘zgartirmoqda"
    if item_type == "mcp_tool_call":
        return "🔌 Codex instrumenti ishlayapti"
    if item_type == "web_search":
        return "🌐 Codex ma’lumot tekshirmoqda"
    return ""


def stream_codex_chat(prompt, cont, cwd, session, on_proc=None, visual=False, true_motion=False):
    status = codex_cli_status()
    if not status["ready"]:
        yield {"done": True, "error": "Codex CLI tayyor emas: " + status["status"]}
        return

    with CODEX_THREADS_LOCK:
        previous_thread = CODEX_THREADS.get(session) if cont and session else None

    agent_prompt = composer_prompt(prompt, visual, true_motion)
    if previous_thread:
        args = [
            CODEX,
            "exec",
            "resume",
            previous_thread,
            "--json",
            "--skip-git-repo-check",
            agent_prompt,
        ]
    else:
        args = [
            CODEX,
            "exec",
            "--json",
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "-C",
            cwd,
        ]
        if os.path.isdir(PROJECT_ROOT) and os.path.abspath(cwd) != PROJECT_ROOT:
            args += ["--add-dir", PROJECT_ROOT]
        args.append(agent_prompt)

    yield {"action": "🧠 Codex CLI · ChatGPT hisobi"}
    yield {"action": "📂 papka: " + cwd}
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        start_new_session=True,
    )
    if on_proc:
        on_proc(process)

    result_text = ""
    result_error = ""
    output_lines = []
    stream_queue = queue.Queue()

    def pump_output():
        try:
            for line in process.stdout:
                stream_queue.put(line)
        finally:
            stream_queue.put(None)

    threading.Thread(target=pump_output, daemon=True).start()
    while True:
        try:
            line = stream_queue.get(timeout=2.0)
        except queue.Empty:
            yield {"ping": True}
            continue
        if line is None:
            break
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            output_lines.append(line)
            continue

        event_type = str(event.get("type") or "")
        if event_type == "thread.started":
            thread_id = str(event.get("thread_id") or "")
            if thread_id and session:
                with CODEX_THREADS_LOCK:
                    CODEX_THREADS[session] = thread_id
            continue
        if event_type.startswith("item."):
            item = event.get("item") or {}
            action = _codex_item_action(item)
            if action:
                yield {"action": action}
            if item.get("type") == "agent_message" and item.get("text"):
                result_text = str(item["text"])
            continue
        if event_type in ("error", "turn.failed"):
            result_error = str(event.get("message") or event.get("error") or "Codex CLI xatosi")

    process.wait()
    if process.returncode and not result_error:
        result_error = "\n".join(output_lines[-5:]).strip() or "Codex CLI xatosi (%s)." % process.returncode
    if result_error:
        yield {"done": True, "error": result_error}
    else:
        yield {"done": True, "text": result_text.strip() or "(Codex javobi bo‘sh)"}


# ══════════════════════════════════════════════════════════════════
#  CHATGPT SOL — bulutli tezkor agent (OpenAI Responses API, streaming)
#
#  Nega alohida yo'l: `agy -p` va `codex exec` har bir xabarda yangi
#  jarayon ko'taradi va javob matnini faqat oxirida beradi — shuning
#  uchun oddiy "salom" ham 15-30 soniya kutadi. Bu yerda esa to'g'ridan
#  to'g'ri API ga ulanamiz: birinchi so'z ~1.3 soniyada keladi va matn
#  token-token oqib chiqadi (ChatGPT'dagidek).
#
#  Chuqurlik yo'qolmaydi: model haqiqiy vositalar bilan fayl o'qiydi,
#  tahrirlaydi, qidiradi va terminal buyrug'ini bajaradi — har bir qadam
#  UI ga `action` + `detail` hodisasi sifatida jonli uzatiladi.
# ══════════════════════════════════════════════════════════════════
SOL_MODEL_ID = "__chatgpt_sol__"
SOL_MODEL = (os.environ.get("OPENAI_CHAT_MODEL") or "gpt-5.6-sol").strip()
SOL_MAX_STEPS = int(os.environ.get("OPENAI_CHAT_MAX_STEPS", "60"))
SOL_HISTORY_LIMIT = 80
SOL_TOOL_OUTPUT_LIMIT = 24000
SOL_SESSIONS = {}
SOL_SESSIONS_LOCK = threading.Lock()

SOL_SYSTEM = """Sen — MUHASIB ish stoli yordamchisisan, ChatGPT Sol modelida ishlaysan.

## Gapirish uslubi
- Foydalanuvchi qaysi tilda yozsa — o'sha tilda javob ber. O'zbekcha yozsa, tabiiy va ravon o'zbek tilida gapir; so'zma-so'z tarjima uslubidan qoch.
- Muqaddima va bo'sh iboralarsiz yoz: "albatta", "yaxshi savol", "keling ko'raylik" kerak emas. To'g'ridan-to'g'ri javobdan boshla.
- Javob uzunligi savolga mos bo'lsin: qisqa savolga bir-ikki gap, murakkab vazifaga tuzilgan javob.
- Aniq gapir: raqam, fayl nomi va yo'lni to'liq yoz. Bilmasang — bilmayman deb ayt, to'qib yozma.

## Qachon vosita ishlatiladi
- Salomlashish, ta'rif, fikr, tushuntirish, matn yozish, hisob-kitob — vosita CHAQIRMA, darrov javob ber.
- Fayl, kod, papka, loyiha holati yoki terminal natijasi so'ralsa — TAXMIN QILMA, vosita bilan haqiqatan tekshir.
- O'zgartirishda tartib: avval o'qi → keyin tahrirla → keyin natijani tekshir. Tekshirmasdan "bajarildi" deb yozma.
- Xato chiqsa sababini top va tuzat. Tuzata olmasang, nima to'sqinlik qilganini aniq ayt.

## ANIQLIK — ishning sifati shunga bog'liq

**Kod ustida ishlashdan oldin:**
- `git_holat` chaqir. Nima allaqachon o'zgarganini bilmasdan tahrir qilsang,
  boshqa birovning ishini bosib ketishing mumkin.
- O'zgartiradigan narsangning ta'rifini VA uni chaqiradigan joylarni o'qi
  (`search_code`). Faqat bitta joyni ko'rib tahrir qilma — funksiya nomini
  o'zgartirsang, uni chaqiradigan hamma joy sinadi.
- Nomni, maydonni yoki yo'lni xotiradan yozma. Har doim `read_file` yoki
  `search_code` bilan aynan qanday yozilganini ko'r.

**Tahrir qilayotganda:**
- Bir faylda ikkitadan ortiq joyni o'zgartirsang `multi_edit` ishlat: u yo
  hammasini qiladi, yo hech narsani — fayl yarim tahrirlangan holda qolmaydi.
- `old_text` ni atrofidagi qatorlar bilan ol, faqat bitta joyga mos kelsin.
- Faylni to'liq qayta yozish (`write_file`) — faqat yangi fayl uchun. Mavjud
  faylda tahrir ishlat, aks holda ko'rmagan qismlaringni o'chirib yuborasan.

**Tahrirdan keyin:**
- Python, JS va JSON fayllari avtomatik sintaksis tekshiruvidan o'tadi. Natijada
  "SINTAKSIS XATOSI" chiqsa — bu boshqa ishga o'tish emas, DARROV tuzatish signali.
- Sintaksis o'tgani ishlayapti degani emas. Eng tor tekshiruvni haqiqatan yugurt:
  fayl importi, bitta test, `--help`, yoki tegishli buyruq. Keyin kengroq tekshir.
- Foydalanuvchiga "tayyor" deyishdan oldin o'zingdan so'ra: buni haqiqatan
  yugurtib ko'rdimmi yoki shunchaki to'g'ri bo'lishi kerak deb o'ylayapmanmi?

**Katta izlanishda:** bir nechta mustaqil savol bo'lsa `yordamchi_agent` ga
`vazifalar` ro'yxatini ber — ular bir vaqtda ishlaydi va sen faqat xulosalarni
olasan. Bu ham tezroq, ham suhbatni toza saqlaydi.

**Aytilmagan ishni qilma.** Foydalanuvchi so'ramagan faylni o'chirma, so'ramagan
qismni qayta yozma, "yaxshiroq bo'ladi" deb qo'shimcha o'zgarish kiritma. Kerak
deb hisoblasang — avval ayt, keyin qil.

## O'ZINGNI O'ZING BOSHQARASAN
Sen ishni oxirigacha o'zing olib borasan. Har qadamda "davom etaymi?", "shuni
qilaymi?" deb so'rab to'xtama — foydalanuvchi vazifani aytgan bo'lsa, ruxsat
bergan bo'ladi. Qaysi vosita kerakligini, qaysi tartibda ishlatishni va qachon
to'xtashni o'zing hal qil.

Faqat mana bularda to'xtab so'ra:
- Ma'lumot yetishmaydi va taxmin qilib bo'lmaydi (qaysi summa, kimga, qaysi fayl).
- Qaytarib bo'lmaydigan ish: fayl/papka o'chirish, pul to'lash, xabar yuborish,
  saytda "Yuborish"/"Sotib olish"/"O'chirish" tugmasini bosish.
- Parol, karta raqami yoki shaxsiy hujjat kiritish kerak bo'lib qolsa — buni
  HECH QACHON o'zing yozma. Brauzer oynasi foydalanuvchining ko'z oldida ochiq
  turibdi: "shu oynada o'zingiz kiring, keyin davom etaman" deb ayt.

Qadamlar chegarasi bor, lekin u katta — vazifani bo'lib yuborishni so'rashdan
oldin ishni haqiqatan oxirigacha olib borishga harakat qil.

## Jarayonni ko'rsatish — foydalanuvchi hammasini ko'rib turadi
Vosita chaqirishdan oldin bir qisqa gap yoz. Bu gap yakuniy javobga
QO'SHILMAYDI — u suhbatda alohida qator bo'lib turadi, ostidagi vositalar esa
uning tagiga yig'iladi. Ya'ni bu gap bo'limning sarlavhasi.

Qanday yozish kerak:
- Bir-ikki gap, ko'pi bilan. Nuqta bilan tugaydigan tugal gap.
- Avval nima aniqlanganini, keyin endi nima qilishingni ayt:
  "Arxitektura aniq. Endi brauzer dvigatelini yozaman."
  "Kalitda kredit tugagan — vositalarni to'g'ridan-to'g'ri sinayman."
- Vosita nomlarini sanab chiqma ("read_file chaqiraman" deb yozma) — natijani
  ayt: "hisob.py dagi qoldiq hisobini ko'raman."
- "Endi", "Keyin" bilan boshlash yaxshi; "Albatta", "Keling", "Yaxshi savol"
  kerak emas.
- Har vosita oldidan takrorlanadigan bir xil gap yozma. Yangi bo'lim
  boshlanganda yoki yo'nalish o'zgarganda yoz.
- Uch qadamdan ortiq ish bo'lsa avval `reja_yozish` bilan reja tuz. Har qadam
  tugagach rejani yangilab qayta chaqir — panel jonli o'zgaradi va foydalanuvchi
  qayerdaligingni ko'rib turadi. Kichik ishga reja kerak emas.
- Uzun natijani qisqartir, lekin muhim raqam, xato matni va fayl yo'llarini tashlab yuborma.

## Internet va saytlar
`brauzer_*` vositalari haqiqiy Chrome oynasini boshqaradi — u foydalanuvchining
ekranida ochiladi va chat ichidagi panelda jonli ko'rinadi.
- Tartib: `brauzer_och` → `brauzer_oqish` (ref larni ol) → `brauzer_bosish` /
  `brauzer_yozish` → yana o'qi. Ref'siz bosishga urinma.
- Sahifa sekin yuklansa `brauzer_kutish`, ko'rinishni haqiqatan ko'rish kerak
  bo'lsa `brauzer_skrin` (rasm senga ko'rsatiladi).
- Sayt kirish (login) yoki "men robot emasman" tekshiruvini so'rasa —
  `brauzer_login_kutish` chaqir. Panelda foydalanuvchiga xabar chiqadi, u
  o'sha panelning ichida bosib-yozib kiradi va "Davom et" ni bosadi, sen esa
  ishni davom ettirasan. Profil saqlanadi, shuning uchun bu bir marta bo'ladi.
- Parol, karta raqami, SMS kodi yoki hujjat ma'lumotini HECH QACHON o'zing
  kiritma va CAPTCHA yechishga urinma — har doim `brauzer_login_kutish`.
- Oddiy ma'lumot kerak bo'lsa `web_qidiruv` va `web_olish` tezroq — brauzer
  faqat haqiqatan sayt bilan ishlash kerak bo'lganda.
- Video so'ralsa `youtube_qidiruv` chaqir va u qaytargan HAVOLANI aynan
  ko'chirib javobga qo'y — suhbatda pleyer bo'lib ochiladi. Havolani xotiradan
  yozma yoki o'zgartirma: YouTube manzillari taxmin qilinmaydi, noto'g'ri
  havola esa ochilmaydigan video beradi.

## Qurilmalar — printer, TV, telefon, Telegram
`ulanishlar_holati` bilan nima ulanganini bil, keyin ishlat.
- **Printer:** `chop_etish`. Chek printeri (58/80mm) tor — qatorlarni qisqa yoz,
  jadval chizma. Sotuv cheki, qarz tilxati va kunlik hisobot shunga chiqadi.
- **TV:** `tv_buyruq`. Ulanmagan bo'lsa foydalanuvchini Sozlamalar → Ulanishlar
  ga yo'llab yubor: u yerda TV ekranida kod chiqadi va bir marta ulanadi.
- **Xabar va qo'ng'iroq:** `sms_yuborish`, `qongiroq_qilish`, `telegram_yuborish`.

## Jadval va hujjatlar
- **Google Sheets:** `sheets_yaratish`, `sheets_oqish`, `sheets_yozish`,
  `sheets_qoshish`. O'qilgan yoki yozilgan ma'lumot suhbat burchagidagi
  oynada avtomatik ko'rinadi — javobda jadvalni qayta chizib o'tirma, qisqa
  xulosa va **havolani** ber.
- Mavjud jadval ustida ishlashda avval `sheets_varaqlar` bilan tuzilmani ko'r,
  keyin yoz. Ustidan yozadigan `sheets_yozish` emas, qator qo'shadigan
  `sheets_qoshish` ni afzal ko'r — mavjud ma'lumot o'chib ketmasin.
- Jadval ulanmagan bo'lsa yoki ruxsat yo'q desa, foydalanuvchini Sozlamalar →
  Ulanishlar ga yo'nalt: u yerda kalit qo'shish va jadvalni ulashish yozilgan.
- **Excel:** `excel_oqish` / `excel_yozish` — fayl diskda kerak bo'lsa.
- **Valyuta:** `valyuta_kursi` — Markaziy bank kursi. Dollar hisob-kitobi,
  narx belgilash va valyuta kassasida kursni xotiradan AYTMA, shundan ol.
- **Kalendar va eslatma:** `kalendar_yozish`, `eslatma_yozish`. "Ertaga
  Alisherdan qarz olishni eslat" kabi gapda shuni ishlat.

**Xabar yuborish qoidasi — buni buzma.** Xabar va qo'ng'iroq qaytarib
bo'lmaydigan amal. Yuborishdan OLDIN foydalanuvchiga aynan shu ko'rinishda
ko'rsat va tasdiqlashini kut:
  Kimga: <ism yoki raqam>
  Matn: "<to'liq matn>"
  Yuborayinmi?
Foydalanuvchi "ha" degandagina yubor. "Falonchiga yozib yubor" degan gap
tasdiq EMAS — bu vazifa qo'yish; matnni tayyorlab, tasdiq so'ra. Faqat
foydalanuvchi matnni to'liq aytib "hozir yubor" desa, so'ramasdan yuborsa
bo'ladi. Bir vaqtda ko'p odamga tarqatma.

Instagram va shunga o'xshash saytlarda parol bilan avtomatlashtirish yo'q —
`brauzer_och` bilan ochib, `brauzer_login_kutish` bilan foydalanuvchining
o'zini kiritasan.

## Mac ekrani
`ekran_*` vositalari butun Mac'ni boshqaradi — brauzerdan tashqaridagi ilovalar uchun.
- Doim `ekran_korish` dan boshla: rasm senga ko'rsatiladi va u ekranning mantiqiy
  o'lchamida bo'ladi, ya'ni rasmda ko'rgan koordinatani to'g'ridan-to'g'ri
  `ekran_bosish` ga berasan.
- Har bosishdan keyin yana `ekran_korish` bilan natijani tekshir — ko'rmasdan
  ketma-ket bosaverma.
- Sayt bilan ishlash kerak bo'lsa ekran emas, `brauzer_*` ishlat — u aniqroq.
- Ekran ruxsati berilmagan bo'lsa xato chiqadi: foydalanuvchiga Tizim sozlamalari →
  Maxfiylik va xavfsizlik → Ekranni yozib olish (va Kirish imkoniyati) da ruxsat
  berishni ayt, keyin dasturni qayta ishga tushirsin.

## HISOB-KITOB — asosiy vazifang
Sen bu odamning hisobchisisan. U oddiy gap bilan aytadi, sen `amal_yozish` bilan jurnalga yozasan.
Alohida dastur, jadval yoki dashboard yo'q — faqat shu suhbat.

Gapni amalga o'girish jadvali:

| Foydalanuvchi aytadi | tur | Muhim maydonlar |
|---|---|---|
| "Alisherga 200 ming qarz berdim" | `qarz_berdim` | kim, summa |
| "Sardordan 5 million qarz oldim" | `qarz_oldim` | kim, summa |
| "Sardorga 1 million qaytardim" | `qarz_qaytardim` | kim, summa |
| "Jasur 500 ming qaytardi" | `qarz_qaytarildi` | kim, summa |
| "3 dona non 5 mingdan sotdim" | `sotuv` | tovar, miqdor, birlik, narx, tolov=naqd |
| "Jasurga 2 kg go'sht nasiyaga berdim" | `sotuv` | + kim, tolov=qarz |
| "Sardordan 10 kg un naqtga oldim, kilosi 8 ming" | `xarid` | kim, tovar, miqdor, birlik, narx, tolov=naqd |
| "Sardordan 10 kg un qarzga oldim" | `xarid` | + tolov=qarz |
| "benzinga 50 ming sarfladim" | `xarajat` | summa, izoh |
| "50 ming boshqa daromad tushdi" | `kirim` | summa, izoh |

Qoidalar:
- **Raqamlarni to'g'ri o'gir:** "200 ming"=200000, "5 million"/"5 mln"=5000000, "1,5 million"=1500000.
- **naqt/naqd = naqd pul, nasiya/qarzga/keyin to'layman = qarz.** Farqi katta: naqd kassaga tegadi, qarz esa qarz hisobiga.
- **Kim berdi/kim oldi — aralashtirma.** "Men qarz berdim" ≠ "menga qarz berishdi". Gapni sinchiklab o'qi.
- **Kuryer va xodimlarga tovar berish:** Kuryer yoki xodim do'kon ishchisi bo'lsa, u qarzdor hisoblanmaydi! Tovar `ombor_otkazma` bilan Asosiy ombordan Kuryer omboriga/lokatsiyasiga o'tkaziladi (dan_ombor="Asosiy", ga_ombor="Kuryer"). Tovar baribir omborda turadi va Kuryer sotganda `sotuv` yoziladi.
- Foydalanuvchi "dollarda", "so'mda" desa yoki boshqa kassani aytsa — `kassa_nomi`
  va `valyuta` ni ber. Kassa hali ochilmagan bo'lsa avval `kassa_ochish` chaqir.
- VALYUTA SOTISH/ALMASHTIRISH (masalan "USDT sotdim 10135 ga") — bu `pul_otkazish`:
  chiqim kassadan yechiladi, kirim kassaga tushadi. `sotuv` faqat TOVAR uchun.
- `hisob.json` faylini read_file/write_file/edit vositalari bilan O'ZGARTIRISH
  QAT'IYAN TAQIQLANADI — faqat hisob vositalari orqali yoz. Qo'lda yozilgan
  yozuv zanjirni buzadi va qoldiqlarni noto'g'ri qiladi.
- Bir gapda bir necha amal bo'lsa (masalan "2 kg go'sht va 1 kg un sotdim"), har biriga alohida `amal_yozish` chaqir.
- Tovar nomi, o'lchov birligi va odam ismini foydalanuvchi qanday aytsa shunday yoz — o'zingdan o'zgartirma.
- **Yangi tovar omborga birinchi marta kirsa** unga rasm qo'y: `generate_image` bilan
  oq fonda, studiya yorug'ligidagi mahsulot rasmini yarat va `tovar_rasm` bilan
  biriktir. Foydalanuvchi so'ramasa ham qilaver — ro'yxat shunda tushunarli bo'ladi.
  Ko'p tovarga birdan kerak bo'lsa avval `rasmsiz_tovarlar` ni chaqir.

**ENG MUHIM QOIDA — YETISHMAGAN NARSANI O'YLAB TOPMA:**
Foydalanuvchi "tovar sotib oldim" yoki "qarz berdim" deb qisqa aytsa, bu
YOZISH BUYRUG'I EMAS — bu suhbat boshlanishi. `amal_yozish` ni CHAQIRMA.
Avval bir qisqa savol bilan yetishmagan narsani so'ra:
  · xarid/sotuv → qaysi tovar, qancha miqdorda, qanchadan, kimdan/kimga,
    naqdmi yoki nasiyaga?
  · qarz → kim bilan va qancha summa?
  · xarajat/kirim → qancha va nimaga/nimadan?
Hech qachon "tovar", "mahsulot", "noma'lum" kabi to'ldirgich nom, 1 dona
miqdor yoki 0 narx yozma — bunday yozuvning ma'nosi yo'q va jurnal uni
rad etadi. Hammasi ma'lum bo'lgandagina yoz.
- `izoh` maydoniga ism, summa yoki tovar nomini TAKRORLAMA — ular alohida maydonlarda saqlanadi va tarixda ikki marta ko'rinib qoladi. Izohni faqat qo'shimcha ma'lumot bo'lsa yoz (masalan "tug'ilgan kun uchun"), aks holda bo'sh qoldir.
- **Ma'lumot yetishmasa — taxmin qilma, so'ra.** Summa aytilmagan bo'lsa yozma, avval so'ra.
- "Qarzim qancha?", "kassada qancha bor?", "foydam qancha?", "omborda nima bor?" → `hisobot_olish` chaqirib, aniq raqamlar bilan javob ber.
- Yozib bo'lgach, natijani bir gapda tasdiqla va o'zgargan qoldiqni ayt. Masalan: "Yozildi. Alisherning qarzi endi 350 000 so'm."
- Xato yozilgan bo'lsa `amallar_royxati` bilan topib, `amal_ochirish` bilan o'chir.
- Bu biznes har qanday sohada bo'lishi mumkin (non, oltin, xizmat, kiyim). Hech qanday sohaga xos taxmin qilma.

## Ish muhiti
- Ish papkasi: {cwd}
- Loyiha ildizi: {root}
- Bugungi sana: {today}
- Ish papkasida yoki loyiha ildizida AGENTS.md bo'lsa — undagi qoidalar majburiy. Ayniqsa video, ovoz va rasm qoidalarini buzma.
"""

SOL_TOOLS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Faylni o'qiydi va qator raqamlari bilan qaytaradi. Fayl haqida gapirishdan oldin doim shu bilan tekshir.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Fayl yo'li (nisbiy yoki to'liq)."},
                "offset": {"type": "integer", "description": "Nechanchi qatordan boshlab (1 dan)."},
                "limit": {"type": "integer", "description": "Nechta qator o'qilsin (standart 400)."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_dir",
        "description": "Papka ichidagi fayl va papkalar ro'yxatini o'lchamlari bilan qaytaradi.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Papka yo'li. Bo'sh bo'lsa — ish papkasi."}},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_code",
        "description": "Matn yoki regex bo'yicha fayllar ichidan qidiradi (ripgrep/grep). Kod yoki qiymat qayerdaligini topish uchun.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Qidiriladigan matn yoki regex."},
                "path": {"type": "string", "description": "Qaysi papkada qidirilsin. Bo'sh bo'lsa — ish papkasi."},
                "glob": {"type": "string", "description": "Fayl filtri, masalan *.py"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Faylni to'liq yozadi (mavjud bo'lsa ustidan yozadi). Yangi fayl yaratish uchun ishlat.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "description": "Faylning to'liq yangi mazmuni."},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "edit_file",
        "description": "Fayl ichidagi aniq matn bo'lagini almashtiradi. old_text faylda bir marta uchrashi shart.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string", "description": "Almashtiriladigan aniq matn (bo'shliqlari bilan)."},
                "new_text": {"type": "string", "description": "O'rniga yoziladigan matn."},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "amal_yozish",
        "description": ("Hisob-kitob jurnaliga bitta amal yozadi: sotuv, xarid, qarz berish/olish, "
                        "qaytarish, xarajat, kirim yoki omborlararo o'tkazma. Foydalanuvchi biznes harakatini aytganda shuni chaqir."),
        "parameters": {
            "type": "object",
            "properties": {
                "tur": {
                    "type": "string",
                    "enum": ["sotuv", "xarid", "qarz_berdim", "qarz_oldim", "qarz_qaytardim",
                             "qarz_qaytarildi", "xarajat", "kirim", "boshlangich", "otkazma", "ombor_otkazma"],
                    "description": "Amal turi.",
                },
                "kim": {"type": "string", "description": "Shaxs yoki ta'minotchi ismi."},
                "tovar": {"type": "string", "description": "Tovar yoki xizmat nomi (sotuv/xaridda/o'tkazmada)."},
                "miqdor": {"type": "number", "description": "Nechta/necha kg."},
                "birlik": {"type": "string", "description": "dona, kg, litr, metr, gramm va h.k."},
                "narx": {"type": "number", "description": "Bitta birlik narxi."},
                "summa": {"type": "number", "description": "Jami summa. Miqdor×narx dan avtomatik ham chiqadi."},
                "tan_narx": {"type": "number", "description": "Sotuvda birlik tannarxi (bilinsa)."},
                "tolov": {"type": "string", "enum": ["naqd", "karta", "qarz"],
                          "description": "naqd/karta — pul harakat qiladi; qarz — nasiyaga."},
                "izoh": {"type": "string", "description": "Qisqa izoh."},
                "kassa_nomi": {"type": "string", "description": ("Qaysi kassaga yozilsin. "
                    "Aytilmasa asosiy kassaga tushadi. Valyuta kassaga mos kelishi shart.")},
                "valyuta": {"type": "string", "description": ("Amal valyutasi (USD, UZS...). "
                    "Kassa valyutasiga mos kelmasa yozuv rad etiladi.")},
                "barkod": {"type": "string", "description": ("Tovar barkodi. Berilsa tovar nomi "
                    "shundan aniqlanadi — skanerdan o'qilgan kod uchun qulay.")},
                "dan_ombor": {"type": "string", "description": "Qaysi ombordan/lokatsiyadan (ombor_otkazma uchun)."},
                "ga_ombor": {"type": "string", "description": "Qaysi omborga/kuryerga/xodimgaga (ombor_otkazma uchun)."},
            },
            "required": ["tur"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "hisobot_olish",
        "description": ("Joriy holatni qaytaradi: kassa, ombor qoldig'i, qarzdorlar, qarzlarim va foyda. "
                        "Qoldiq yoki hisobot so'ralganda shuni chaqir — taxmin qilma."),
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "type": "function",
        "name": "amallar_royxati",
        "description": "Oxirgi yozilgan amallarni ko'rsatadi. Xatoni topish yoki tarixni ko'rish uchun.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Nechta amal (standart 20)."},
                "kim": {"type": "string", "description": "Faqat shu odam bo'yicha."},
                "tur": {"type": "string", "description": "Faqat shu tur bo'yicha."},
                "tovar": {"type": "string", "description": "Faqat shu tovar bo'yicha."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "amal_ochirish",
        "description": "Xato yozilgan amalni id bo'yicha o'chiradi. Avval amallar_royxati bilan id ni top.",
        "parameters": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Amal id si."}},
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "biznes_sozlama",
        "description": "Biznes nomi va valyutasini o'rnatadi.",
        "parameters": {
            "type": "object",
            "properties": {
                "nom": {"type": "string", "description": "Biznes nomi, masalan 'Zargar Sardor'."},
                "valyuta": {"type": "string", "description": "UZS, USD va h.k."},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "kassa_ochish",
        "description": ("Yangi kassa (hisob) ochadi — masalan dollar kassasi yoki ikkinchi "
                        "do'kon kassasi. Foydalanuvchi \"yana bir kassa och\", \"dollarda "
                        "alohida hisob och\" desa shuni chaqir. Har kassa o'z valyutasida "
                        "yuritiladi va boshqasi bilan qo'shilmaydi."),
        "parameters": {
            "type": "object",
            "properties": {
                "nom": {"type": "string", "description": "Kassa nomi, masalan 'Dollar kassa'."},
                "valyuta": {"type": "string", "description": "UZS, USD, EUR... Aytilmasa biznes valyutasi."},
            },
            "required": ["nom"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "barkod_biriktirish",
        "description": ("Tovarga barkod biriktiradi. Barkod aytilmasa avtomatik EAN-13 "
                        "yasaladi (200-prefiks — do'kon ichida erkin ishlatiladi). "
                        "\"Unga barkod ber\", \"shu kodni biriktir\" desa shuni chaqir."),
        "parameters": {
            "type": "object",
            "properties": {
                "tovar": {"type": "string", "description": "Tovar nomi."},
                "barkod": {"type": "string", "description": "Mavjud barkod. Bo'sh qoldirilsa avtomatik yasaladi."},
            },
            "required": ["tovar"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "tovar_rasm",
        "description": ("Tovarga rasm biriktiradi. Rasm yo'li `generate_image` bilan "
                        "yaratilgan fayl yoki tashqi URL bo'lishi mumkin. Yangi tovar "
                        "kirganda yoki foydalanuvchi \"rasm qo'y\" desa chaqir."),
        "parameters": {
            "type": "object",
            "properties": {
                "tovar": {"type": "string", "description": "Tovar nomi."},
                "rasm": {"type": "string", "description": "Rasm fayl yo'li (images/... ) yoki to'liq URL."},
            },
            "required": ["tovar", "rasm"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "rasmsiz_tovarlar",
        "description": ("Ombordagi rasmi yo'q tovarlar ro'yxati. \"Rasmlarni qo'yib chiq\" "
                        "desa avval shuni chaqir, keyin har biriga `generate_image` bilan "
                        "rasm yaratib `tovar_rasm` bilan biriktir."),
        "parameters": {"type": "object", "properties": {}, "required": [],
                       "additionalProperties": False},
    },
    {
        "type": "function",
        "name": "barkod_topish",
        "description": ("Barkod bo'yicha tovarni va uning ombordagi qoldig'ini topadi. "
                        "Foydalanuvchi barkod raqamini aytsa yoki skanerdan o'qilsa shuni chaqir."),
        "parameters": {
            "type": "object",
            "properties": {"barkod": {"type": "string", "description": "Barkod raqami."}},
            "required": ["barkod"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "pul_otkazish",
        "description": ("Kassalar orasida pul o'tkazadi yoki valyuta ayirboshlaydi. "
                        "Foydalanuvchi \"USDT sotdim\", \"dollarni so'mga almashtirdim\", "
                        "\"u kassadan bunga o'tkaz\" desa SHUNI chaqir (sotuv EMAS — sotuv "
                        "faqat tovar uchun). Chiqim kassadan yechiladi, kirim kassaga tushadi, "
                        "zanjir uzilmaydi."),
        "parameters": {
            "type": "object",
            "properties": {
                "chiqim_kassa": {"type": "string", "description": "Pul chiqadigan kassa nomi."},
                "kirim_kassa": {"type": "string", "description": "Pul kiradigan kassa nomi."},
                "chiqim_summa": {"type": "number", "description": "Chiqim kassadan yechiladigan summa (o'z valyutasida)."},
                "kirim_summa": {"type": "number", "description": "Kirim kassaga tushadigan summa (o'z valyutasida). Aytilmasa chiqim bilan teng."},
                "izoh": {"type": "string", "description": "Qisqa izoh, masalan kurs."},
            },
            "required": ["chiqim_kassa", "kirim_kassa", "chiqim_summa"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "kassa_nomlash",
        "description": ("Mavjud kassaning nomini o'zgartiradi. Foydalanuvchi \"kassa nomini "
                        "o'zgartir\", \"USDT kassani Zayniddin deb nomla\", \"birinchi kassaga "
                        "nom ber\" desa shuni chaqir. Eski nomga yozilgan amallar avtomatik "
                        "yangi nomga ko'chadi."),
        "parameters": {
            "type": "object",
            "properties": {
                "eski_nom": {"type": "string", "description": "Hozirgi nomi. Bilmasang avval kassalar_royxati chaqir."},
                "yangi_nom": {"type": "string", "description": "Yangi nom."},
            },
            "required": ["eski_nom", "yangi_nom"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "kassa_ochirish",
        "description": ("Kassani ro'yxatdan olib tashlaydi. Asosiy kassani o'chirib bo'lmaydi. "
                        "Amallar jurnalda saqlanib qoladi."),
        "parameters": {
            "type": "object",
            "properties": {"nom": {"type": "string", "description": "O'chiriladigan kassa nomi."}},
            "required": ["nom"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "kassalar_royxati",
        "description": "Ochilgan barcha kassalarni va ularning valyutasi hamda qoldig'ini qaytaradi.",
        "parameters": {"type": "object", "properties": {}, "required": [],
                       "additionalProperties": False},
    },
    {
        "type": "function",
        "name": "run_command",
        "description": "Ish papkasida terminal buyrug'ini bajaradi va natijasini qaytaradi. Serverni abadiy ushlab qoladigan buyruqlarni (http.server, npm run dev) ishga tushirma.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bajariladigan shell buyrug'i."},
                "timeout": {"type": "integer", "description": "Soniyalarda kutish chegarasi (standart 120, eng ko'pi 900)."},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
]

# Brauzer, ekran, reja, web va rasm vositalari alohida modulda — shu yerda qo'shiladi.
SOL_TOOLS += vositalar.TOOLS


def _fayl_tekshir(path):
    """Yozilgan faylni darrov sintaksis bo'yicha tekshiradi.

    Bu aniqlikning eng arzon va eng kuchli omili: agent xato yozsa buni
    keyingi qadamda emas, o'sha zahoti biladi va tuzatadi. Aks holda xato
    fayl diskda qolib ketadi va "bajarildi" deb hisobot beriladi.
    """
    kengaytma = os.path.splitext(path)[1].lower()
    try:
        if kengaytma == ".py":
            venv = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
            python = venv if os.path.exists(venv) else sys.executable
            done = subprocess.run([python, "-m", "py_compile", path],
                                  capture_output=True, text=True, timeout=45)
            if done.returncode != 0:
                return "SINTAKSIS XATOSI — fayl buzuq holda saqlandi, DARROV tuzat:\n" + \
                       (done.stderr or done.stdout or "").strip()[:1200]
            return ""
        if kengaytma == ".json":
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
            return ""
        if kengaytma in (".js", ".mjs", ".cjs"):
            node = shutil.which("node")
            if not node:
                return ""
            done = subprocess.run([node, "--check", path],
                                  capture_output=True, text=True, timeout=45)
            if done.returncode != 0:
                return "SINTAKSIS XATOSI — fayl buzuq holda saqlandi, DARROV tuzat:\n" + \
                       (done.stderr or "").strip()[:1200]
            return ""
    except json.JSONDecodeError as xato:
        return "JSON XATOSI — fayl buzuq holda saqlandi, DARROV tuzat: " + str(xato)[:400]
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""
    return ""


def _qator_farqi(eski, yangi):
    """Nechta qator qo'shildi va o'chirildi — interfeysdagi +12 −3 shundan."""
    farq = difflib.ndiff((eski or "").splitlines(), (yangi or "").splitlines())
    qoshildi = ochirildi = 0
    for qator in farq:
        if qator.startswith("+ "):
            qoshildi += 1
        elif qator.startswith("- "):
            ochirildi += 1
    return qoshildi, ochirildi


# Har bir vosita qaysi turkumga kiradi — interfeys qadamlarni shunga qarab
# guruhlaydi ("3 ta buyruq bajarildi, 2 ta fayl o'qildi").
QADAM_TURI = {
    "read_file": "oqish", "list_dir": "oqish",
    "search_code": "qidiruv", "fayl_qidirish": "qidiruv",
    "write_file": "yozish", "edit_file": "tahrir",
    "run_command": "buyruq",
    "web_olish": "web", "web_qidiruv": "web",
    "rasm_yaratish": "rasm", "reja_yozish": "reja",
    "yordamchi_agent": "yordamchi",
}


def _qadam_turi(nom):
    if nom in QADAM_TURI:
        return QADAM_TURI[nom]
    if nom.startswith("brauzer"):
        return "brauzer"
    if nom.startswith("ekran") or nom == "ilova_ochish":
        return "ekran"
    return "hisob"


def _sol_resolve(cwd, path):
    target = os.path.expanduser(str(path or "").strip())
    if not target:
        return cwd
    if not os.path.isabs(target):
        target = os.path.join(cwd, target)
    return os.path.abspath(target)


def _sol_clip(text, limit=SOL_TOOL_OUTPUT_LIMIT):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n… (%d belgi qisqartirildi)" % (len(text) - limit)


def _pul(qiymat):
    """150000 → '150 000' — o'zbekcha pul yozuvi."""
    try:
        son = float(qiymat)
    except (TypeError, ValueError):
        return str(qiymat)
    butun = int(round(son))
    return "{:,}".format(butun).replace(",", " ")


def _sol_qisqa_holat(holat):
    """Model uchun qisqa xulosa — har yozuvdan keyin qaytariladi."""
    return {
        "kassa": holat["kassa"],
        "ombor_qiymati": holat["ombor"]["jami_qiymat"],
        "qarzdorlar_jami": holat["qarzdorlar"]["jami"],
        "qarzlarim_jami": holat["qarzlarim"]["jami"],
        "sof_foyda": holat["foyda"]["sof"],
    }


def _sol_run_tool(name, args, cwd, on_proc=None, sink=None):
    """Vositani bajaradi → (qadam_yorlig'i, qisqa_izoh, model_uchun_natija).

    `sink` — yon kanal: vosita unga rasm, reja yoki brauzer holatini qo'yishi
    mumkin, chaqiruvchi esa ularni interfeysga va modelga uzatadi.
    """
    try:
        if name == "read_file":
            path = _sol_resolve(cwd, args.get("path"))
            if not os.path.isfile(path):
                return "📄 Fayl o'qildi · " + os.path.basename(path), "topilmadi", "XATO: fayl topilmadi — " + path
            offset = max(1, int(args.get("offset") or 1))
            limit = max(1, min(int(args.get("limit") or 400), 2000))
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            chunk = lines[offset - 1: offset - 1 + limit]
            body = "".join("%6d\t%s" % (offset + i, ln) for i, ln in enumerate(chunk))
            more = "" if offset - 1 + limit >= len(lines) else "\n… jami %d qator." % len(lines)
            return ("📄 Fayl o'qildi · " + os.path.basename(path),
                    "%d qator" % len(chunk),
                    _sol_clip(body + more) or "(fayl bo'sh)")

        if name == "list_dir":
            path = _sol_resolve(cwd, args.get("path"))
            if not os.path.isdir(path):
                return "📂 Papka ko'rildi", "topilmadi", "XATO: papka topilmadi — " + path
            rows = []
            for entry in sorted(os.listdir(path)):
                full = os.path.join(path, entry)
                if os.path.isdir(full):
                    rows.append("papka/  " + entry)
                else:
                    try:
                        rows.append("%8d  %s" % (os.path.getsize(full), entry))
                    except OSError:
                        rows.append("       ?  " + entry)
            return ("📂 Papka ko'rildi · " + os.path.basename(path.rstrip("/")),
                    "%d element" % len(rows),
                    _sol_clip(path + "\n" + "\n".join(rows)))

        if name == "search_code":
            pattern = str(args.get("pattern") or "")
            where = _sol_resolve(cwd, args.get("path"))
            glob_filter = str(args.get("glob") or "").strip()
            ripgrep = shutil.which("rg")
            if ripgrep:
                cmd = [ripgrep, "-n", "--no-heading", "-S", "-m", "40", pattern, where]
                if glob_filter:
                    cmd[1:1] = ["-g", glob_filter]
            else:
                cmd = ["grep", "-rn", "--binary-files=without-match"]
                if glob_filter:
                    cmd += ["--include", glob_filter]
                cmd += [pattern, where]
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            out = (done.stdout or "").strip()
            hits = len(out.splitlines()) if out else 0
            return ("🔎 Qidirildi · " + pattern[:60],
                    "%d moslik" % hits,
                    _sol_clip(out) if out else "Moslik topilmadi.")

        if name == "write_file":
            path = _sol_resolve(cwd, args.get("path"))
            content = args.get("content") or ""
            bor_edi = os.path.isfile(path)
            eski = ""
            if bor_edi:
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        eski = f.read()
                except OSError:
                    bor_edi = False
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            qoshildi, ochirildi = _qator_farqi(eski, content)
            if sink is not None:
                sink["fayl"] = {"nom": os.path.basename(path),
                                "amal": "tahrirlandi" if bor_edi else "yaratildi",
                                "qoshildi": qoshildi, "ochirildi": ochirildi}
            nosozlik = _fayl_tekshir(path)
            return (("✍️ Fayl tahrirlandi · " if bor_edi else "✍️ Fayl yaratildi · ")
                    + os.path.basename(path),
                    ("⚠️ sintaksis xatosi" if nosozlik else "+%d −%d" % (qoshildi, ochirildi)),
                    "Yozildi: %s (%d belgi, +%d −%d qator)%s"
                    % (path, len(content), qoshildi, ochirildi,
                       "\n\n" + nosozlik if nosozlik else "\nSintaksis tekshiruvi o'tdi."))

        if name == "edit_file":
            path = _sol_resolve(cwd, args.get("path"))
            old_text = args.get("old_text") or ""
            new_text = args.get("new_text") or ""
            if not os.path.isfile(path):
                return "✏️ Fayl tahrirlandi", "topilmadi", "XATO: fayl topilmadi — " + path
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            found = source.count(old_text)
            if found == 0:
                return ("✏️ Fayl tahrirlandi · " + os.path.basename(path), "moslik yo'q",
                        "XATO: old_text faylda topilmadi. Avval read_file bilan aniq matnni o'qi.")
            if found > 1:
                return ("✏️ Fayl tahrirlandi · " + os.path.basename(path), "%d marta uchradi" % found,
                        "XATO: old_text faylda %d marta uchradi. Atrofidagi qatorlarni qo'shib yagona qilib ber." % found)
            with open(path, "w", encoding="utf-8") as f:
                f.write(source.replace(old_text, new_text, 1))
            qoshildi, ochirildi = _qator_farqi(old_text, new_text)
            if sink is not None:
                sink["fayl"] = {"nom": os.path.basename(path), "amal": "tahrirlandi",
                                "qoshildi": qoshildi, "ochirildi": ochirildi}
            nosozlik = _fayl_tekshir(path)
            return ("✏️ Fayl tahrirlandi · " + os.path.basename(path),
                    ("⚠️ sintaksis xatosi" if nosozlik else "+%d −%d" % (qoshildi, ochirildi)),
                    "Tahrirlandi: %s (+%d −%d qator)%s"
                    % (path, qoshildi, ochirildi,
                       "\n\n" + nosozlik if nosozlik else "\nSintaksis tekshiruvi o'tdi."))

        # ── Hisob-kitob vositalari ────────────────────────────────────
        if name == "amal_yozish":
            amal = hisob.amal_qoshish(**args)
            holat = hisob.hisobot()
            nomi = hisob.TUR_NOMI.get(amal["tur"], amal["tur"])
            bolaklar = [nomi]
            if amal["kim"]:
                bolaklar.append(amal["kim"])
            if amal["tovar"]:
                bolaklar.append("%s %g %s" % (amal["tovar"], amal["miqdor"], amal["birlik"]))
            if amal["summa"]:
                bolaklar.append(_pul(amal["summa"]))
            return ("🧾 " + " · ".join(bolaklar),
                    "kassa " + _pul(holat["kassa"]),
                    json.dumps({"yozildi": amal, "yangi_holat": _sol_qisqa_holat(holat)},
                               ensure_ascii=False))

        if name == "hisobot_olish":
            holat = hisob.hisobot()
            return ("📊 Hisobot olindi",
                    "kassa " + _pul(holat["kassa"]),
                    json.dumps(holat, ensure_ascii=False))

        if name == "amallar_royxati":
            royxat = hisob.amallar(
                limit=args.get("limit") or 20,
                kim=args.get("kim") or "",
                tur=args.get("tur") or "",
                tovar=args.get("tovar") or "",
            )
            return ("📜 Amallar tarixi", "%d ta" % len(royxat),
                    json.dumps(royxat, ensure_ascii=False))

        if name == "amal_ochirish":
            ochirildi = hisob.amal_ochirish(args.get("id"))
            holat = hisob.hisobot()
            return ("🗑️ Amal o'chirildi" if ochirildi else "🗑️ Amal topilmadi",
                    "kassa " + _pul(holat["kassa"]),
                    json.dumps({"ochirildi": ochirildi, "yangi_holat": _sol_qisqa_holat(holat)},
                               ensure_ascii=False))

        if name == "biznes_sozlama":
            biznes = hisob.sozlama(nom=args.get("nom"), valyuta=args.get("valyuta"))
            return ("⚙️ Biznes sozlandi · " + (biznes.get("nom") or "nomsiz"),
                    biznes.get("valyuta", ""), json.dumps(biznes, ensure_ascii=False))

        if name == "kassa_ochish":
            yangi = hisob.kassa_ochish(args.get("nom"), args.get("valyuta"))
            return ("🏦 Yangi kassa · " + yangi["nom"] + " (" + yangi["valyuta"] + ")",
                    "jami %d kassa" % len(yangi["kassalar"]),
                    json.dumps(yangi, ensure_ascii=False))

        if name == "barkod_biriktirish":
            r = hisob.barkod_biriktirish(args.get("tovar"), args.get("barkod") or "")
            return ("🏷️ Barkod · " + r["tovar"] + " → " + r["barkod"],
                    ("avtomatik" if r["avto"] else "qo'lda") + (" · EAN-13" if r["ean13"] else ""),
                    json.dumps(r, ensure_ascii=False))

        if name == "tovar_rasm":
            r = hisob.rasm_biriktirish(args.get("tovar"), args.get("rasm"))
            return ("🖼️ Rasm · " + r["tovar"], r["rasm"][:60],
                    json.dumps(r, ensure_ascii=False))

        if name == "rasmsiz_tovarlar":
            royxat = hisob.rasmsiz_tovarlar()
            return ("🖼️ Rasmsiz tovarlar · %d ta" % len(royxat),
                    ", ".join(royxat[:6]) or "yo'q",
                    json.dumps({"tovarlar": royxat}, ensure_ascii=False))

        if name == "barkod_topish":
            r = hisob.barkod_topish(args.get("barkod"))
            if not r["topildi"]:
                return ("🔍 Barkod topilmadi · " + str(args.get("barkod")), "yo'q",
                        json.dumps(r, ensure_ascii=False))
            o = r["ombor"]
            return ("🔍 " + r["tovar"] + " · " + str(o["miqdor"]) + " " + o["birlik"],
                    "barkod " + r["barkod"], json.dumps(r, ensure_ascii=False))

        if name == "pul_otkazish":
            amal = hisob.otkazma(args.get("chiqim_kassa"), args.get("kirim_kassa"),
                                 args.get("chiqim_summa"), args.get("kirim_summa"),
                                 izoh=args.get("izoh") or "")
            holat = hisob.hisobot()
            return ("🔁 O'tkazma · %s → %s" % (amal["kassa_nomi"], amal["kirim_kassa"]),
                    "%s %s → %s %s" % (_pul(amal["summa"]), amal["valyuta"],
                                       _pul(amal["kirim_summa"]), amal["kirim_valyuta"]),
                    json.dumps({"yozildi": amal,
                                "yangi_holat": _sol_qisqa_holat(holat),
                                "kassalar": holat.get("kassalar") or []},
                               ensure_ascii=False))

        if name == "kassa_nomlash":
            n = hisob.kassa_nomlash(args.get("eski_nom"), args.get("yangi_nom"))
            return ("🏷️ Kassa nomlandi · " + n["eski"] + " → " + n["yangi"],
                    "%d ta amal ko'chdi" % n["kochirilgan_amallar"],
                    json.dumps(n, ensure_ascii=False))

        if name == "kassa_ochirish":
            ok = hisob.kassa_ochirish(args.get("nom"))
            return ("🗑️ Kassa o'chirildi · " + str(args.get("nom")),
                    "bajarildi" if ok else "topilmadi",
                    json.dumps({"ochirildi": bool(ok)}, ensure_ascii=False))

        if name == "kassalar_royxati":
            holat = hisob.hisobot()
            royxat = holat.get("kassalar") or []
            return ("🏦 Kassalar · %d ta" % len(royxat),
                    ", ".join(k["nom"] for k in royxat),
                    json.dumps({"kassalar": royxat,
                                "valyutalar": holat.get("valyutalar") or []},
                               ensure_ascii=False))

        if name == "run_command":
            command = str(args.get("command") or "").strip()
            if not command:
                return "⌨️ Buyruq bajarildi", "bo'sh", "XATO: buyruq bo'sh."
            timeout = max(5, min(int(args.get("timeout") or 120), 900))
            process = subprocess.Popen(
                command, shell=True, cwd=cwd, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
            )
            if on_proc:
                on_proc(process)
            try:
                out = process.communicate(timeout=timeout)[0] or ""
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    process.kill()
                out = process.communicate()[0] or ""
                return ("⌨️ $ " + command[:70], "vaqt tugadi",
                        _sol_clip("VAQT TUGADI (%ds). Qisman natija:\n%s" % (timeout, out)))
            code = process.returncode
            return ("⌨️ $ " + command[:70],
                    "kod %d" % code,
                    _sol_clip("exit=%d\n%s" % (code, out.strip() or "(chiqish bo'sh)")))

        # Brauzer, ekran, reja, web, rasm — alohida modulda.
        qoshimcha = vositalar.ishlat(name, args, cwd, sink=sink, on_proc=on_proc)
        if qoshimcha is not None:
            return qoshimcha

        return "🛠️ " + name, "noma'lum", "XATO: bunday vosita yo'q — " + name
    except subprocess.TimeoutExpired:
        return "🛠️ " + name, "vaqt tugadi", "XATO: vosita vaqt chegarasidan oshdi."
    except Exception as exc:
        return "🛠️ " + name, "xato", "XATO: " + str(exc)[:400]


def _sol_trim(history):
    """Tarixni qisqartiradi, lekin function_call ↔ function_call_output juftini buzmaydi."""
    if len(history) <= SOL_HISTORY_LIMIT:
        return history
    trimmed = history[-SOL_HISTORY_LIMIT:]
    open_calls = {item.get("call_id") for item in trimmed if item.get("type") == "function_call"}
    while trimmed and trimmed[0].get("type") == "function_call_output" and trimmed[0].get("call_id") not in open_calls:
        trimmed.pop(0)
    return trimmed


IXCHAM_CHEGARA = int(os.environ.get("OPENAI_CHAT_COMPACT_AT", "120"))
IXCHAM_BELGISI = "[oldingi ishning qisqacha bayoni]"


def _sol_ixchamlash(history):
    """Tarix uzayib ketganda eskisini xulosaga aylantiradi.

    `_sol_trim` eski qadamlarni shunchaki kesib tashlaydi — uzun vazifada
    agent nima qilganini unutib, ishni boshidan boshlab yuborishi mumkin.
    Bu yerda esa eski qism xulosa qilinadi va xulosa tarixda qoladi.
    """
    if len(history) <= IXCHAM_CHEGARA:
        return history
    # Oxirgi uchdan birini o'z holicha qoldiramiz — yaqin kontekst aniq kerak.
    saqlanadi = max(20, IXCHAM_CHEGARA // 3)
    eski, yangi = history[:-saqlanadi], history[-saqlanadi:]
    if not eski:
        return history

    xom = []
    for element in eski:
        if not isinstance(element, dict):
            continue
        tur = element.get("type") or element.get("role") or ""
        if tur == "function_call":
            xom.append("VOSITA " + str(element.get("name")) + " " + str(element.get("arguments"))[:220])
        elif tur == "function_call_output":
            xom.append("NATIJA " + str(element.get("output"))[:400])
        else:
            tana = element.get("content")
            if isinstance(tana, list):
                tana = " ".join(str(x.get("text", "")) for x in tana if isinstance(x, dict))
            xom.append(str(tur).upper() + ": " + str(tana)[:600])
    tavsif = "\n".join(xom)[-40000:]

    payload = {
        "model": SOL_MODEL,
        "instructions": (
            "Quyida agentning shu vazifa ustidagi ishi yozilgan. Uni davom "
            "ettirish uchun kerak bo'ladigan hamma narsani saqlab, qisqa bayon "
            "qil. Majburiy bandlar: (1) foydalanuvchi nima so'ragan, (2) qaysi "
            "fayllar o'zgartirildi va nima qilindi, (3) qanday qaror va "
            "cheklovlar qabul qilindi, (4) nima hali bajarilmagan, (5) uchragan "
            "xatolar va ularning sababi. Aniq fayl yo'llari, raqamlar va nomlarni "
            "tashlab yuborma. Muqaddimasiz, faqat bayon."),
        "input": [{"role": "user", "content": tavsif}],
        "store": False,
        "stream": False,
    }
    try:
        so_rov = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + _openai_api_key(),
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(so_rov, timeout=180) as javob:
            natija = json.loads(javob.read().decode("utf-8"))
        xulosa = ""
        for element in natija.get("output") or []:
            for bolak in element.get("content") or []:
                if bolak.get("type") == "output_text":
                    xulosa += bolak.get("text") or ""
    except Exception:
        return _sol_trim(history)          # xulosa chiqmasa eski yo'l bilan kesamiz
    if not xulosa.strip():
        return _sol_trim(history)

    yangi = list(yangi)
    while yangi and isinstance(yangi[0], dict) and yangi[0].get("type") == "function_call_output":
        yangi.pop(0)                       # juftsiz natija qolmasin
    return [{"role": "user", "content": IXCHAM_BELGISI + "\n" + xulosa.strip()}] + yangi


RASM_BELGISI = "[ko'rilgan-rasm]"


def _sol_rasm_url(path):
    """Interfeys uchun: diskdagi rasmni brauzer ocha oladigan manzilga aylantiradi."""
    return "/api/file?path=" + urllib.parse.quote(path) + "&t=" + str(int(time.time() * 1000))


def _sol_rasm_xabari(path, tool_name):
    """Skrinshotni modelga ko'rsatadigan xabar. Rasm matn natijaga sig'maydi."""
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    izoh = ("Brauzer sahifasining hozirgi ko'rinishi."
            if tool_name.startswith("brauzer") else
            "Mac ekranining hozirgi ko'rinishi. Bosish koordinatasini shu rasmdan ol.")
    return {"role": "user", "content": [
        {"type": "input_text", "text": RASM_BELGISI + " " + izoh},
        {"type": "input_image", "image_url": "data:%s;base64,%s" % (mime, encoded)},
    ]}


def _sol_rasmlarni_yengillashtir(history, saqlanadi=2):
    """Eski skrinshotlarni tarixdan olib tashlaydi — faqat oxirgilari qoladi.

    Har qadamda rasm yig'ilib borsa suhbat tez orada kontekstga sig'may qoladi;
    modelga esa faqat oxirgi ko'rinish kerak.
    """
    indekslar = [i for i, item in enumerate(history)
                 if isinstance(item, dict) and item.get("role") == "user"
                 and isinstance(item.get("content"), list)
                 and any(isinstance(c, dict) and c.get("type") == "input_text"
                         and str(c.get("text", "")).startswith(RASM_BELGISI)
                         for c in item["content"])]
    for i in indekslar[:-saqlanadi] if saqlanadi else indekslar:
        matn = next((c.get("text", "") for c in history[i]["content"]
                     if isinstance(c, dict) and c.get("type") == "input_text"), "")
        history[i] = {"role": "user",
                      "content": matn + " (rasm eskirdi — kerak bo'lsa qaytadan ko'r)"}
    return history


def _sol_user_content(prompt, attachment_path):
    if not attachment_path or not os.path.isfile(attachment_path):
        return prompt
    try:
        with open(attachment_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        mime = mimetypes.guess_type(attachment_path)[0] or "image/png"
        return [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": "data:%s;base64,%s" % (mime, encoded)},
        ]
    except Exception:
        return prompt + "\n\n(Biriktirilgan rasmni o'qib bo'lmadi: " + attachment_path + ")"


def _sol_stream_once(payload, timeout=900, urinishlar=3):
    """Oqimni ochadi. Vaqtinchalik xatoda (429, 5xx, tarmoq) qayta uriniladi —
    bitta tasodifiy uzilish uzun vazifani bekor qilib yubormasin."""
    oxirgi = None
    for urinish in range(urinishlar):
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": "Bearer " + _openai_api_key(),
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as xato:
            oxirgi = xato
            if xato.code not in (408, 409, 429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, OSError) as xato:
            oxirgi = xato
        if urinish < urinishlar - 1:
            time.sleep(1.5 * (2 ** urinish))
    raise oxirgi


AGENTS_CHEGARA = 14000


def _loyiha_qoidalari(cwd):
    """Ish papkasi va loyiha ildizidagi AGENTS.md ni o'qiydi.

    Ilgari ko'rsatmada "AGENTS.md dagi qoidalar majburiy" deb yozilgan edi-yu,
    fayl hech qachon o'qilmasdi — agent qoidalarni o'zi topib olishiga
    tashlab qo'yilgandi. Endi ular har suhbatda ko'rsatmaga qo'shiladi.
    """
    korilgan, bolaklar = set(), []
    for papka in (cwd, PROJECT_ROOT):
        yol = os.path.join(papka or "", "AGENTS.md")
        haqiqiy = os.path.realpath(yol)
        if haqiqiy in korilgan or not os.path.isfile(haqiqiy):
            continue
        korilgan.add(haqiqiy)
        try:
            with open(haqiqiy, "r", encoding="utf-8", errors="replace") as f:
                matn = f.read(AGENTS_CHEGARA * 2)
        except OSError:
            continue
        if len(matn) > AGENTS_CHEGARA:
            matn = matn[:AGENTS_CHEGARA] + "\n… (qoidalar uzun — qolganini kerak bo'lsa o'qi)"
        bolaklar.append("### " + haqiqiy + "\n\n" + matn.strip())
    if not bolaklar:
        return ""
    return ("\n\n## LOYIHA QOIDALARI — MAJBURIY\n"
            "Quyidagilar shu loyihaning AGENTS.md fayllaridan olindi. Ular sening\n"
            "umumiy odatlaringdan USTUN turadi. Biror ish shu qoidaga zid bo'lsa —\n"
            "qoidaga amal qil va foydalanuvchiga sababini ayt.\n\n"
            + "\n\n".join(bolaklar))


def _git_konteksti(cwd):
    """Qaysi tarmoqda va nima o'zgargani — kod ustida ishlashda asosiy kontekst."""
    if not cwd or not os.path.isdir(cwd):
        return ""
    try:
        ildiz = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                               capture_output=True, text=True, timeout=6)
        if ildiz.returncode != 0:
            return ""
        tarmoq = subprocess.run(["git", "branch", "--show-current"], cwd=cwd,
                                capture_output=True, text=True, timeout=6).stdout.strip()
        holat = subprocess.run(["git", "status", "--short"], cwd=cwd,
                               capture_output=True, text=True, timeout=8).stdout.strip()
    except Exception:
        return ""
    qatorlar = holat.splitlines()
    ozgargan = ("\n".join(qatorlar[:25]) +
                ("\n… yana %d fayl" % (len(qatorlar) - 25) if len(qatorlar) > 25 else "")
                ) if qatorlar else "(o'zgarish yo'q)"
    return ("\n\n## Git holati\n- Ildiz: %s\n- Tarmoq: %s\n- O'zgargan fayllar:\n%s\n"
            % (ildiz.stdout.strip(), tarmoq or "(ajratilgan HEAD)", ozgargan))


def stream_sol_chat(prompt, cwd, session, cont, on_proc=None, attachment_path="",
                    visual=False, true_motion=False, cancel=None):
    """ChatGPT Sol bilan oqimli suhbat: matn token-token, vositalar jonli ko'rinadi."""
    try:
        _openai_api_key()
    except ValueError as exc:
        yield {"done": True, "error": str(exc)}
        return

    with SOL_SESSIONS_LOCK:
        history = list(SOL_SESSIONS.get(session, [])) if (cont and session) else []

    system_text = SOL_SYSTEM.format(cwd=cwd, root=PROJECT_ROOT, today=time.strftime("%Y-%m-%d"))
    if visual:
        system_text += VISUAL_PRODUCTION_INSTRUCTIONS
    if true_motion:
        system_text += TRUE_HUMAN_MOTION_INSTRUCTIONS
    # Loyiha qoidalari va git holati har suhbatda ko'rsatmaga qo'shiladi —
    # agent ularni qidirib topishiga tashlab qo'yilmaydi.
    system_text += _git_konteksti(cwd)
    system_text += _loyiha_qoidalari(cwd)

    history.append({"role": "user", "content": _sol_user_content(prompt, attachment_path)})

    yield {"action": "⚡ ChatGPT Sol · " + SOL_MODEL}
    yield {"action": "📂 papka: " + cwd}

    answer = ""
    for step in range(SOL_MAX_STEPS):
        if cancel is not None and cancel.is_set():
            yield {"done": True, "text": answer.strip() or "⏹ To'xtatildi."}
            return

        # Tarix haddan oshsa xulosaga aylantiramiz — uzun vazifa yarmida
        # kontekst tugab, agent nima qilganini unutib qo'ymasin.
        if len(history) > IXCHAM_CHEGARA:
            yield {"action": "🧠 Suhbat xulosalanmoqda", "detail": "%d qadam" % len(history),
                   "tur": "qadam"}
            history = _sol_ixchamlash(history)

        payload = {
            "model": SOL_MODEL,
            "instructions": system_text,
            "input": _sol_rasmlarni_yengillashtir(_sol_trim(history)),
            "tools": SOL_TOOLS,
            # Bir qadamda bir nechta vosita chaqirilishi mumkin (masalan ikki faylni
            # birdan o'qish). Bajarilishi baribir ketma-ket — tartib buzilmaydi.
            "parallel_tool_calls": True,
            "store": False,
            "stream": True,
        }
        try:
            stream = _sol_stream_once(payload)
        except urllib.error.HTTPError as error:
            yield {"done": True, "error": _openai_error_message(error)}
            return
        except Exception as error:
            yield {"done": True, "error": "OpenAI ga ulanib bo'lmadi: " + str(error)[:220]}
            return

        calls = []
        output_items = []
        failed = ""
        try:
            for raw in stream:
                if cancel is not None and cancel.is_set():
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                kind = event.get("type") or ""
                if kind == "response.output_text.delta":
                    piece = event.get("delta") or ""
                    if piece:
                        answer += piece
                        yield {"delta": piece}
                elif kind == "response.reasoning_summary_text.delta":
                    piece = event.get("delta") or ""
                    if piece:
                        yield {"reason": piece}
                elif kind == "response.completed":
                    output_items = ((event.get("response") or {}).get("output")) or []
                elif kind in ("response.failed", "response.incomplete", "error"):
                    detail = event.get("response") or event
                    failed = str((detail.get("error") or {}).get("message")
                                 or detail.get("message") or "Sol javobi uzildi.")
        finally:
            try:
                stream.close()
            except Exception:
                pass

        if failed:
            yield {"done": True, "error": _openai_xato_matni(failed)}
            return
        if cancel is not None and cancel.is_set():
            yield {"done": True, "text": answer.strip() or "⏹ To'xtatildi."}
            return

        for item in output_items:
            history.append(item)
            if item.get("type") == "function_call":
                calls.append(item)

        if not calls:
            with SOL_SESSIONS_LOCK:
                SOL_SESSIONS[session or "_"] = _sol_rasmlarni_yengillashtir(_sol_trim(history), saqlanadi=1)
            yield {"done": True, "text": answer.strip() or "(javob bo'sh)"}
            return

        # Vosita chaqirilyapti → shu bosqichdagi matn yakuniy javob emas, balki
        # "hozir nima qilmoqchiman" izohi. Uni qadamlar ro'yxatiga o'tkazamiz va
        # javob oynasini tozalaymiz — aks holda izohlar javobga yopishib ketadi.
        narration = answer.strip()
        answer = ""
        yield {"reset": True, "note": narration}

        for call in calls:
            if cancel is not None and cancel.is_set():
                break
            try:
                call_args = json.loads(call.get("arguments") or "{}")
            except ValueError:
                call_args = {}
            tool_name = call.get("name") or ""
            sink = {}
            label, note, result = _sol_run_tool(tool_name, call_args, cwd,
                                                on_proc=on_proc, sink=sink)
            event = {"action": label, "detail": note, "tur": _qadam_turi(tool_name)}
            if sink.get("fayl"):
                event["fayl"] = sink["fayl"]
            # Daftarga yozilgan amal — brauzer buni CHEK ko'rinishida chizadi
            if tool_name in ("amal_yozish", "pul_otkazish"):
                try:
                    yozuv = json.loads(result)
                    event["chek"] = {"amal": yozuv.get("yozildi"),
                                     "holat": yozuv.get("yangi_holat"),
                                     "kassalar": yozuv.get("kassalar"),
                                     "valyuta": hisob.sozlama().get("valyuta", "")}
                except Exception:
                    pass
            if sink.get("reja"):
                event["reja"] = sink["reja"]
            if sink.get("brauzer"):
                event["brauzer"] = sink["brauzer"]
            if sink.get("login"):
                event["login"] = sink["login"]
            if sink.get("jadval"):
                event["jadval"] = sink["jadval"]
            if sink.get("videolar"):
                event["videolar"] = sink["videolar"]
            if sink.get("image"):
                event["rasm"] = _sol_rasm_url(sink["image"])
            yield event
            history.append({
                "type": "function_call_output",
                "call_id": call.get("call_id"),
                "output": result,
            })
            # Ekran/brauzer skrini — natija matn bo'lgani uchun rasmni alohida
            # xabar bilan qo'shamiz, aks holda model uni ko'rmaydi.
            if sink.get("image"):
                korish = _sol_rasm_xabari(sink["image"], tool_name)
                if korish:
                    history.append(korish)

    with SOL_SESSIONS_LOCK:
        SOL_SESSIONS[session or "_"] = _sol_rasmlarni_yengillashtir(_sol_trim(history), saqlanadi=1)
    yield {"done": True, "text": (answer.strip() or "") +
           "\n\n⚠️ Qadamlar chegarasi (%d) tugadi — vazifani bo'lib qayta yuboring." % SOL_MAX_STEPS}


YORDAMCHI_TOOLS = [t for t in SOL_TOOLS if t.get("name") in (
    "read_file", "list_dir", "search_code", "fayl_qidirish",
    "run_command", "web_olish", "web_qidiruv", "hisobot_olish", "amallar_royxati",
)]
YORDAMCHI_SYSTEM = """Sen — izlanish yordamchisisan. Senga bitta mustaqil vazifa berildi.

- Vazifani vositalar bilan haqiqatan tekshirib bajar, taxmin qilma.
- Fayl o'zgartirmaysan, hech narsa yozmaysan — faqat o'qiysan, qidirasan, tekshirasan.
- Javobing to'g'ridan-to'g'ri asosiy agentga boradi, odamga emas. Shuning uchun
  muqaddima va xushmuomalalik kerak emas: faqat topilgan aniq ma'lumot.
- Fayl yo'li, qator raqami va aniq qiymatlarni to'liq yoz.
- Topa olmasang — nimani qayerda qidirganingni va nima topilmaganini ayt.

Ish papkasi: {cwd}
"""


def _sol_yordamchi(vazifa, cwd, qadam_chegara=14):
    """Yordamchi agent: alohida kontekstda izlanadi va faqat xulosani qaytaradi."""
    try:
        _openai_api_key()
    except ValueError as exc:
        return "XATO: " + str(exc)
    history = [{"role": "user", "content": vazifa}]
    javob = ""
    for _ in range(qadam_chegara):
        payload = {
            "model": SOL_MODEL,
            "instructions": YORDAMCHI_SYSTEM.format(cwd=cwd),
            "input": _sol_trim(history),
            "tools": YORDAMCHI_TOOLS,
            "parallel_tool_calls": True,
            "store": False,
            "stream": False,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + _openai_api_key(),
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=600) as stream:
                data = json.loads(stream.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return "XATO: " + _openai_error_message(error)
        except Exception as error:
            return "XATO: yordamchi ulanolmadi — " + str(error)[:200]

        calls = []
        for item in data.get("output") or []:
            history.append(item)
            if item.get("type") == "function_call":
                calls.append(item)
            elif item.get("type") == "message":
                for bolak in item.get("content") or []:
                    if bolak.get("type") == "output_text":
                        javob += bolak.get("text") or ""
        if not calls:
            return javob.strip() or "(yordamchi javob qaytarmadi)"
        for call in calls:
            try:
                call_args = json.loads(call.get("arguments") or "{}")
            except ValueError:
                call_args = {}
            _, _, natija = _sol_run_tool(call.get("name") or "", call_args, cwd)
            history.append({"type": "function_call_output",
                            "call_id": call.get("call_id"), "output": natija})
        javob = ""
    return javob.strip() or "Yordamchi qadamlar chegarasiga yetdi, aniq xulosa chiqmadi."


def _login_kutish(soniya, izoh=""):
    """Agent kirishni kutadi. Panel "Davom etish" ni bosgach True qaytadi.

    So'rov SSE bilan emas, holat orqali uzatiladi: vosita bu yerda bloklanib
    turadi, shuning uchun hodisa oqimi bu paytda to'xtab qoladi. Panel esa
    `/api/brauzer/holat` ni so'rab turadi va so'rovni darrov ko'radi.
    """
    LOGIN_KUTISH.clear()
    LOGIN_SO_ROV.update({"faol": True, "izoh": izoh, "boshlandi": time.time(),
                         "soniya": soniya})
    try:
        return LOGIN_KUTISH.wait(timeout=soniya)
    finally:
        LOGIN_SO_ROV.update({"faol": False, "izoh": ""})
        LOGIN_KUTISH.clear()


# Aylanma importdan qochish uchun bog'lanish shu yerda beriladi.
vositalar.KALIT = _openai_api_key
vositalar.YORDAMCHI = _sol_yordamchi
vositalar.KUTISH = _login_kutish
vositalar.TEKSHIR = _fayl_tekshir
vositalar.QATOR_FARQI = _qator_farqi


# Bu vositalar faqat Sol yo'lida bor. CLI modellari (Composer/agy, Codex) ularni
# ko'rmaydi — foydalanuvchi buni bilmasa, agent 10-15 qadam behuda urinib xato
# beradi. Shuning uchun so'rovni oldindan tekshiramiz.
VOSITA_KERAK_RE = re.compile(
    r"\bsheets?\b|docs\.google\.com/spreadsheets|spreadsheet|\bexcel\b"
    r"|jadval(ga|dan|ni|da)?\b"
    r"|telegram|\bsms\b|qo'?ng'?iroq|qongiroq|pochta\s*yubor|email\s*yubor|xat\s*yubor"
    r"|chop\s*et|printer|chek\s*chiqar|televizor\b|\btv\b"
    r"|youtube|brauzer|saytga\s*kir|instagram"
    r"|\bkurs(i|ini|im|da|ga|lar|lari|larini)?\b|markaziy\s*bank|kalendar|eslatma\s*qo'?sh",
    re.IGNORECASE)


def _vosita_kerakmi(prompt):
    return bool(VOSITA_KERAK_RE.search(prompt or ""))


def stream_chat(prompt, model, cont, folder, session="", on_proc=None, visual=False,
                true_motion=False, attachment_path="", cancel=None):
    folder = os.path.expanduser(folder or "")
    if folder and os.path.isfile(folder):
        folder = os.path.dirname(folder)
    cwd = folder if folder and os.path.isdir(folder) else HOME
    if model == SOL_MODEL_ID:
        yield from stream_sol_chat(
            prompt,
            cwd,
            session,
            cont,
            on_proc=on_proc,
            attachment_path=attachment_path,
            visual=visual,
            true_motion=true_motion,
            cancel=cancel,
        )
        return
    if model == CODEX_CHATGPT_MODEL:
        yield from stream_codex_chat(
            prompt,
            cont,
            cwd,
            session,
            on_proc=on_proc,
            visual=visual,
            true_motion=true_motion,
        )
        return
    selected_model = select_composer_model(prompt, model, visual)
    args = [AGY, "-p", composer_prompt(prompt, visual, true_motion), "--output-format", "stream-json", "--dangerously-skip-permissions",
            "--print-timeout", PRINT_TIMEOUT, "--add-dir", cwd]
    # Loyiha ildizi doim qo'shiladi — aks holda boshqa papka tanlanganda
    # AGENTS.md (loyiha qoidalari) va video/ quvuri agentga ko'rinmaydi.
    if os.path.isdir(PROJECT_ROOT) and os.path.abspath(cwd) != PROJECT_ROOT:
        args += ["--add-dir", PROJECT_ROOT]
    if selected_model: args += ["--model", selected_model]
    if cont: args.append("--continue")
    model_label = selected_model or "avtomatik model"
    yield {"action": "🧠 Composer rejimi · " + model_label}
    if visual:
        yield {"action": "🎨 Visual Studio · rasm/video ishlab chiqarish rejimi"}
    if true_motion:
        yield {"action": "🎞️ Haqiqiy inson motion rejimi · eski video va 2D hiyla rad etiladi"}
    yield {"action": "📂 papka: " + cwd}
    # start_new_session → agent ishga tushirgan buyruqlar ham bitta guruhda bo'ladi,
    # shuning uchun to'xtatganda butun daraxt birga to'xtaydi.
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         bufsize=1, cwd=cwd, start_new_session=True)
    if on_proc:
        on_proc(p)
    result_out = ""
    result_err = ""

    # Chiziqlarni alohida oqimda o'qiymiz — shunda uzoq "o'ylash" paytida ham
    # har 2 soniyada yurak urishi (ping) yuborib turamiz va UI tirikligini ko'rsatadi.
    q = queue.Queue()

    def _pump():
        try:
            for ln in p.stdout:
                q.put(ln)
        except Exception:
            pass
        finally:
            q.put(None)

    threading.Thread(target=_pump, daemon=True).start()

    while True:
        try:
            line = q.get(timeout=2.0)
        except queue.Empty:
            yield {"ping": True}
            continue
        if line is None:
            break
        line = line.strip()
        if not line.startswith("{"): continue
        try: ev = json.loads(line)
        except Exception: continue
        if ev.get("event") == "step_update":
            su = ev.get("step_update", {})
            st, state = su.get("step_type"), su.get("state")
            if st == "tool" and state == "ACTIVE":
                yield {"action": _tool_label(su.get("tool_name",""), (su.get("tool_info") or {}).get("parameters"))}
        elif ev.get("event") == "result":
            res = ev.get("result", {})
            result_err = res.get("error") or ""
            result_out = res.get("response") or ""
    p.wait()
    if result_err:
        yield {"done": True, "error": _cli_xatosini_ochib_ber(result_err, result_out)}
    else:
        yield {"done": True, "text": result_out.strip() or "(javob bo'sh)"}


# agy CLI o'z ichidagi nosozlikni xom holda qaytaradi ("cascade step",
# "CORTEX_STEP_TYPE_..."). Bunday matn foydalanuvchiga hech narsa aytmaydi —
# uni nima bo'lgani va nima qilish kerakligi bilan almashtiramiz.
CLI_ICHKI_XATO = re.compile(
    r"cascade step|CORTEX_STEP_TYPE|cannot kill task|task is not running", re.IGNORECASE)


def _cli_xatosini_ochib_ber(xato, qisman=""):
    matn = str(xato or "").strip()
    if not CLI_ICHKI_XATO.search(matn):
        return matn
    javob = ("Composer (agy) ichki nosozligi — vazifa emas, CLI ning o'zi uzildi.\n\n"
             "Nima qilish kerak:\n"
             "1. Xabarni bir marta qayta yuborib ko'ring yoki boshqa modelni tanlang.\n"
             "2. Takrorlansa bir marta qayta yuborib ko'ring — bu odatda vaqtinchalik.\n\n"
             "Texnik matn: " + matn[:200])
    if qisman.strip():
        javob += "\n\nUzilgunicha yozilgani:\n" + qisman.strip()[:1500]
    return javob


def run_chat(prompt, model, cont, folder):
    folder = os.path.expanduser(folder or "")
    if folder and os.path.isfile(folder):
        folder = os.path.dirname(folder)
    cwd = folder if folder and os.path.isdir(folder) else HOME
    args = [AGY, "-p", prompt, "--output-format", "text", "--dangerously-skip-permissions", "--add-dir", cwd]
    if model:
        args += ["--model", model]
    if cont:
        args.append("--continue")
    r = subprocess.run(args, capture_output=True, text=True, timeout=900, cwd=cwd)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if not out and err:
        return {"error": err[:1000]}
    if r.returncode != 0 and not out:
        return {"error": (err or "xato")[:1000]}
    return {"text": out or "(bo'sh javob)"}


# ══════════════════════════════════════════════════════════════════
#  ULASHILGAN SESSIYALAR — suhbatni boshqa qurilma/odam bilan ulash.
#  Ma'lumot loyiha papkasidagi shared_sessions.json faylda saqlanadi.
#  Har bir ulashilgan sessiya o'z qisqa ID'siga ega va ChatGPT Sol
#  rejimida davom ettirish mumkin.
# ══════════════════════════════════════════════════════════════════
SHARED_SESSIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_sessions.json")
SHARED_SESSIONS_LOCK = threading.Lock()


def _load_shared_sessions():
    """Fayldan ulashilgan sessiyalar ro'yxatini o'qish."""
    try:
        with open(SHARED_SESSIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_shared_sessions(data):
    """Ulashilgan sessiyalar ro'yxatini faylga yozish."""
    with open(SHARED_SESSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def share_session(session_data):
    """Sessiyani ulashish — qisqa ID yaratib, serverda saqlaydi.
    session_data: { title, messages: [{role, text, timestamp}], model? }
    Qaytaradi: { id, url }
    """
    share_id = "sh_" + str(int(time.time())) + "_" + os.urandom(4).hex()
    shared = {
        "id": share_id,
        "title": (session_data.get("title") or "Suhbat")[:160],
        "messages": (session_data.get("messages") or [])[:80],
        "model": session_data.get("model") or SOL_MODEL_ID,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "active": True,
    }
    with SHARED_SESSIONS_LOCK:
        all_shared = _load_shared_sessions()
        all_shared[share_id] = shared
        _save_shared_sessions(all_shared)
    return {"id": share_id, "url": "/shared/" + share_id}


def get_shared_session(share_id):
    """Ulashilgan sessiyani ID bo'yicha olish."""
    with SHARED_SESSIONS_LOCK:
        all_shared = _load_shared_sessions()
        return all_shared.get(share_id)


def list_shared_sessions():
    """Barcha ulashilgan sessiyalar ro'yxati."""
    with SHARED_SESSIONS_LOCK:
        all_shared = _load_shared_sessions()
        result = []
        for sid, s in sorted(all_shared.items(), key=lambda kv: kv[1].get("created", ""), reverse=True):
            result.append({
                "id": s["id"],
                "title": s.get("title", "Suhbat"),
                "created": s.get("created", ""),
                "messageCount": len(s.get("messages", [])),
                "active": s.get("active", True),
            })
        return result


def delete_shared_session(share_id):
    """Ulashilgan sessiyani o'chirish."""
    with SHARED_SESSIONS_LOCK:
        all_shared = _load_shared_sessions()
        if share_id in all_shared:
            del all_shared[share_id]
            _save_shared_sessions(all_shared)
            return True
        return False


def update_shared_session_messages(share_id, messages):
    """Ulashilgan sessiya xabarlarini yangilash (chat davom etganda)."""
    with SHARED_SESSIONS_LOCK:
        all_shared = _load_shared_sessions()
        if share_id in all_shared:
            all_shared[share_id]["messages"] = messages[:80]
            _save_shared_sessions(all_shared)
            return True
        return False


# ══════════════════════════════════════════════════════════════════
#  JOB REGISTRI — ish brauzer so'rovidan mustaqil davom etadi.
#  Sahifa yangilansa yoki boshqa suhbatga o'tilsa ham ish to'xtamaydi;
#  mijoz istalgan payt qayta ulanib, boshidan barcha qadamlarni oladi.
# ══════════════════════════════════════════════════════════════════
JOBS = {}
JOBS_LOCK = threading.Lock()
_JOB_N = 0


def _prune_jobs():
    now = time.time()
    with JOBS_LOCK:
        for jid in [k for k, j in JOBS.items()
                    if j["state"] != "running" and now - j.get("ended", j["started"]) > 3600]:
            JOBS.pop(jid, None)
        while len(JOBS) > 40:
            done = [(k, j) for k, j in JOBS.items() if j["state"] != "running"]
            if not done:
                break
            JOBS.pop(min(done, key=lambda kv: kv[1]["started"])[0], None)


def start_job(prompt, model, cont, folder, session, attachment_path=""):
    global _JOB_N
    _prune_jobs()
    with JOBS_LOCK:
        _JOB_N += 1
        jid = "j%d_%d" % (int(time.time()), _JOB_N)
        job = {
            "id": jid, "session": session or "", "prompt": prompt, "folder": folder,
            "started": time.time(), "state": "running", "events": [],
            "visual": is_visual_request(prompt, bool(attachment_path)),
            "trueMotion": is_true_human_motion_request(prompt),
            "cv": threading.Condition(),
            "cancel": threading.Event(),
        }
        JOBS[jid] = job

    def _work():
        try:
            agent_prompt = prompt
            # Sol rasmni to'g'ridan-to'g'ri ko'radi (vision), CLI agentlariga esa
            # faqat fayl yo'lini aytish mumkin.
            if attachment_path and model != SOL_MODEL_ID:
                agent_prompt += (
                    "\n\nREFERENCE IMAGE ATTACHED BY USER: " + attachment_path +
                    "\nYou must inspect this exact image before responding or editing it."
                )
            if job["trueMotion"]:
                events = stream_true_human_motion(
                    prompt,
                    attachment_path,
                    on_proc=lambda pr: job.__setitem__("proc", pr),
                )
            else:
                events = stream_chat(
                    agent_prompt,
                    model,
                    cont,
                    folder,
                    session,
                    on_proc=lambda pr: job.__setitem__("proc", pr),
                    visual=job["visual"],
                    true_motion=job["trueMotion"],
                    attachment_path=attachment_path,
                    cancel=job["cancel"],
                )
            for ev in events:
                if ev.get("ping"):
                    continue            # pingni saqlamaymiz, kuzatuvchi o'zi yuboradi
                if ev.get("done") and job.get("stopping"):
                    # Yozilib ulgurgan matn yo'qolmasin — ustiga belgi qo'yamiz.
                    partial = (ev.get("text") or "").strip()
                    if partial and not partial.startswith("⏹"):
                        ev = {"done": True, "text": partial + "\n\n⏹ To'xtatildi."}
                    else:
                        ev = {"done": True, "text": "⏹ To'xtatildi."}
                with job["cv"]:
                    job["events"].append(ev)
                    job["cv"].notify_all()
        except Exception as e:
            with job["cv"]:
                job["events"].append({"done": True, "error": str(e)})
                job["cv"].notify_all()
        finally:
            with job["cv"]:
                if not any(e.get("done") for e in job["events"]):
                    job["events"].append({"done": True,
                                          "text": "⏹ To'xtatildi." if job.get("stopping") else "(javob bo'sh)"})
                if job.get("stopping"):
                    job["state"] = "stopped"
                else:
                    job["state"] = "error" if any(e.get("error") for e in job["events"]) else "done"
                job["ended"] = time.time()
                job["cv"].notify_all()

    threading.Thread(target=_work, daemon=True).start()
    return job


def stop_job(jid):
    """Ishni to'xtatadi: agent va u ishga tushirgan buyruqlar birga o'ldiriladi."""
    with JOBS_LOCK:
        job = JOBS.get(jid)
    if not job or job["state"] != "running":
        return False
    job["stopping"] = True
    if job.get("cancel"):
        job["cancel"].set()          # Sol bulut oqimi jarayonsiz — bayroq bilan to'xtaydi
    p = job.get("proc")
    if p and p.poll() is None:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass

        def _hard():
            time.sleep(3)
            if p.poll() is None:               # yaxshilikcha to'xtamasa — majburan
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
        threading.Thread(target=_hard, daemon=True).start()
    with job["cv"]:
        job["cv"].notify_all()
    return True


def follow_job(job, start=0):
    """Job hodisalarini `start` indeksdan boshlab uzatadi; jim paytda ping yuboradi."""
    idx = max(0, int(start or 0))
    yield {"job": job["id"], "started": job["started"], "state": job["state"],
           "prompt": job["prompt"], "folder": job["folder"], "session": job["session"],
           "visual": job.get("visual", False), "trueMotion": job.get("trueMotion", False)}
    while True:
        with job["cv"]:
            if idx >= len(job["events"]):
                if job["state"] != "running":
                    break
                job["cv"].wait(timeout=2.0)
            evs = job["events"][idx:]
            idx += len(evs)
            running = job["state"] == "running"
        if evs:
            for ev in evs:
                yield ev
        elif running:
            yield {"ping": True}
        else:
            break


PAGE = r"""<!doctype html>
<html lang="uz" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MUHASIB Antigravity UI</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
  
  /* ——— Antigravity Light (default - Google Pure White) ——— */
  :root, :root[data-theme=light] {
    --bg: #ffffff;
    --bg-soft: #f8f9fa;
    --panel: #ffffff;
    --panel-solid: #ffffff;
    --border: #dadce0;
    --border-strong: #bdc1c6;
    --border-hover: #1a73e8;
    --text: #202124;
    --ink: #1f1f1f;
    --muted: #5f6368;
    --user: #1a73e8;
    --accent: #188038;
    --code-bg: #f8f9fa;
    --card-shadow: 0 1px 3px rgba(60,64,67,0.12), 0 8px 24px rgba(60,64,67,0.06);
    --card-shadow-lift: 0 4px 12px rgba(60,64,67,0.15), 0 16px 36px rgba(60,64,67,0.1);
    --user-bubble: #e8f0fe;
    --user-text: #174ea6;
    --glass-blur: blur(16px);
    --glow-blue: rgba(26, 115, 232, 0.2);
    --field: #f1f3f4;
    --field-hover: #e8eaed;
    --ease: cubic-bezier(0.22, 1, 0.36, 1);
    --aurora-a: rgba(66,133,244,.12);
    --aurora-b: rgba(161,66,244,.10);
    --aurora-c: rgba(251,188,5,.08);
    --aurora-d: rgba(52,168,83,.09);
  }

  /* ——— Antigravity Dark ——— */
  :root[data-theme=dark] {
    --bg: #0a0d14;
    --bg-soft: #10141d;
    --panel: rgba(22, 27, 36, 0.66);
    --panel-solid: #141922;
    --border: rgba(255, 255, 255, 0.09);
    --border-strong: rgba(255, 255, 255, 0.16);
    --border-hover: rgba(66, 133, 244, 0.45);
    --text: #dfe6ef;
    --ink: #ffffff;
    --muted: #8e99a8;
    --user: #4285f4;
    --accent: #34a853;
    --code-bg: #080b11;
    --card-shadow: 0 1px 2px rgba(0,0,0,.3), 0 16px 40px rgba(0,0,0,.45);
    --card-shadow-lift: 0 2px 6px rgba(0,0,0,.35), 0 24px 60px rgba(0,0,0,.55);
    --user-bubble: #17335e;
    --user-text: #eaf1ff;
    --glass-blur: blur(20px) saturate(160%);
    --glow-blue: rgba(66, 133, 244, 0.32);
    --field: rgba(255, 255, 255, 0.06);
    --field-hover: rgba(255, 255, 255, 0.1);
    --ease: cubic-bezier(0.22, 1, 0.36, 1);
    --aurora-a: rgba(66,133,244,.26);
    --aurora-b: rgba(161,66,244,.22);
    --aurora-c: rgba(251,188,5,.14);
    --aurora-d: rgba(52,168,83,.16);
  }
  
  * { box-sizing: border-box; }

  body {
    margin: 0;
    font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100dvh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    letter-spacing: -0.01em;
    transition: background .45s var(--ease), color .45s var(--ease);
  }

  /* ——— Aurora mesh: yumshoq suzuvchi rang doglari (Antigravity uslubi) ——— */
  #aurora {
    position: fixed;
    inset: -25vmax;
    z-index: 0;
    pointer-events: none;
    filter: blur(90px);
    opacity: .95;
    transition: opacity .5s var(--ease);
  }
  #aurora i {
    position: absolute;
    display: block;
    border-radius: 50%;
    mix-blend-mode: normal;
    will-change: transform;
  }
  #aurora .a1 { width: 46vmax; height: 46vmax; left: 4%;  top: 2%;   background: radial-gradient(circle at 30% 30%, var(--aurora-a), transparent 68%); animation: drift1 26s ease-in-out infinite alternate; }
  #aurora .a2 { width: 40vmax; height: 40vmax; right: 3%; top: 6%;   background: radial-gradient(circle at 65% 35%, var(--aurora-b), transparent 68%); animation: drift2 32s ease-in-out infinite alternate; }
  #aurora .a3 { width: 44vmax; height: 44vmax; left: 22%; bottom: 0%; background: radial-gradient(circle at 40% 60%, var(--aurora-c), transparent 68%); animation: drift3 29s ease-in-out infinite alternate; }
  #aurora .a4 { width: 36vmax; height: 36vmax; right: 16%; bottom: 4%; background: radial-gradient(circle at 55% 45%, var(--aurora-d), transparent 68%); animation: drift4 35s ease-in-out infinite alternate; }

  @keyframes drift1 { 0% { transform: translate3d(0,0,0) scale(1); } 50% { transform: translate3d(6vw,4vh,0) scale(1.12); } 100% { transform: translate3d(-3vw,7vh,0) scale(.95); } }
  @keyframes drift2 { 0% { transform: translate3d(0,0,0) scale(1.05); } 50% { transform: translate3d(-7vw,5vh,0) scale(.92); } 100% { transform: translate3d(4vw,-4vh,0) scale(1.1); } }
  @keyframes drift3 { 0% { transform: translate3d(0,0,0) scale(.98); } 50% { transform: translate3d(5vw,-6vh,0) scale(1.14); } 100% { transform: translate3d(-6vw,-2vh,0) scale(1); } }
  @keyframes drift4 { 0% { transform: translate3d(0,0,0) scale(1.08); } 50% { transform: translate3d(-5vw,-5vh,0) scale(.94); } 100% { transform: translate3d(6vw,3vh,0) scale(1.06); } }

  /* nozik grid — chuqurlik hissi uchun */
  #grid-veil {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image:
      linear-gradient(to right, var(--border) 1px, transparent 1px),
      linear-gradient(to bottom, var(--border) 1px, transparent 1px);
    background-size: 64px 64px;
    mask-image: radial-gradient(ellipse 80% 60% at 50% 40%, #000 20%, transparent 78%);
    -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 40%, #000 20%, transparent 78%);
    opacity: .55;
  }

  #agCanvas {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    width: 100%;
    height: 100%;
  }

  #confetti { position: fixed; inset: 0; pointer-events: none; z-index: 60; overflow: hidden; }
  #confetti i {
    position: absolute; width: 9px; height: 5px; border-radius: 2px; opacity: 0;
    animation: confettiFly 2.2s cubic-bezier(.15,.7,.3,1) forwards;
  }
  @keyframes confettiFly {
    0%   { opacity: 1; transform: translate3d(0,0,0) rotate(0deg); }
    100% { opacity: 0; transform: translate3d(var(--dx,0), var(--dy,-40vh), 0) rotate(var(--rot,360deg)); }
  }

  #antigravity-bg {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    opacity: 0.14;
    user-select: none;
    transition: transform 0.2s cubic-bezier(0.1, 0.8, 0.3, 1), opacity 0.3s ease;
    overflow: hidden;
    perspective: 1000px;
  }
  :root[data-theme=light] #antigravity-bg { opacity: 0.10; }
  :root[data-theme=dark] #antigravity-bg { opacity: 0.15; }
  
  .ag-line {
    font-family: 'Google Sans', -apple-system, sans-serif;
    font-weight: 800;
    letter-spacing: 8px;
    text-transform: uppercase;
    display: flex;
    gap: 6px;
    line-height: 1.05;
    filter: drop-shadow(0 0 25px rgba(66,133,244,0.4));
  }
  .ag-line.word-1 {
    font-size: clamp(3.2rem, 9vw, 7.5rem);
    animation: agFloat1 7s ease-in-out infinite alternate;
  }
  .ag-line.word-2 {
    font-size: clamp(1.8rem, 5vw, 4.2rem);
    letter-spacing: 14px;
    margin-top: 8px;
    animation: agFloat2 8s ease-in-out infinite alternate;
  }
  .ag-line span {
    display: inline-block;
    transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    cursor: default;
    pointer-events: auto;
  }
  .ag-line span:hover {
    transform: translateY(-20px) scale(1.3) rotate(10deg);
    text-shadow: 0 0 30px currentColor;
  }

  .c-blue   { color: #4285f4; text-shadow: 0 0 20px rgba(66,133,244,.6); }
  .c-red    { color: #ea4335; text-shadow: 0 0 20px rgba(234,67,53,.6); }
  .c-yellow { color: #fbbc05; text-shadow: 0 0 20px rgba(251,188,5,.6); }
  .c-green  { color: #34a853; text-shadow: 0 0 20px rgba(52,168,83,.6); }
  .c-purple { color: #a142f4; text-shadow: 0 0 20px rgba(161,66,244,.6); }

  @keyframes agFloat1 {
    0%   { transform: translateY(0) rotate(0deg) scale(1); }
    50%  { transform: translateY(-16px) rotate(1.2deg) scale(1.02); }
    100% { transform: translateY(10px) rotate(-0.8deg) scale(0.99); }
  }
  @keyframes agFloat2 {
    0%   { transform: translateY(0) rotate(0deg) scale(1); }
    50%  { transform: translateY(14px) rotate(-1.5deg) scale(0.98); }
    100% { transform: translateY(-12px) rotate(1deg) scale(1.01); }
  }

  body.zero-g-active .ag-line span {
    animation: zeroGFloat 4s ease-in-out infinite alternate !important;
  }
  body.zero-g-active .card, body.zero-g-active .quick-card {
    animation: zeroGCardFloat 5s ease-in-out infinite alternate !important;
  }
  @keyframes zeroGFloat {
    0% { transform: translateY(-40px) rotate(-15deg) scale(1.1); }
    50% { transform: translateY(30px) rotate(20deg) scale(0.9); }
    100% { transform: translateY(-20px) rotate(-8deg) scale(1.05); }
  }
  @keyframes zeroGCardFloat {
    0% { transform: translateY(-8px) rotate(-1deg); }
    50% { transform: translateY(12px) rotate(1.5deg); }
    100% { transform: translateY(-10px) rotate(-1deg); }
  }

  /* Top Glass Navbar - Clean & Framed Container */
  header {
    position: relative;
    z-index: 10;
    margin: 12px 20px 6px 20px;
    padding: 10px 20px;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: var(--panel-solid);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.03);
    animation: hdrIn .6s var(--ease) both;
    transition: border-color .25s var(--ease), box-shadow .25s var(--ease);
  }
  header:hover {
    border-color: var(--border-hover);
    box-shadow: 0 6px 28px rgba(0, 0, 0, 0.08);
  }
  @keyframes hdrIn { from { opacity: 0; transform: translateY(-14px); } to { opacity: 1; transform: none; } }
  
  .hdr-left, .hdr-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .hdr-left  { flex: 0 0 auto; min-width: 0; }
  .hdr-right { flex: 0 0 auto; justify-content: flex-end; }
  header .ghost, header .full-access-btn { padding: 7px 14px; font-size: 12.5px; white-space: nowrap; }
  /* keng ekranlarda — qat'iy bitta qator */
  @media (min-width: 981px) {
    header, .hdr-right, .hdr-left { flex-wrap: nowrap; }
  }
  @media (max-width: 1560px) { .prof .who { display: none !important; } }
  @media (max-width: 1360px) { .port-badge { display: none !important; } }
  @media (max-width: 1280px) { .zerog-btn { display: none !important; } }
  
  /* RAMKASIZ (BORDERLESS / FRAME-LESS) HEADER INPUTS & DROPDOWNS */
  header input, header select, #historySearch {
    border: 1px solid var(--border) !important;
    outline: none !important;
    background: var(--field) !important;
    color: var(--text) !important;
    border-radius: 999px;
    padding: 8px 16px;
    font-size: 13.5px;
    font-family: inherit;
    transition: background .22s var(--ease), box-shadow .22s var(--ease), border-color .22s var(--ease);
  }
  header input:hover, header select:hover, #historySearch:hover {
    background: var(--field-hover) !important;
    border-color: var(--border-hover) !important;
  }
  header input:focus, header select:focus, #historySearch:focus {
    background: var(--field-hover) !important;
    box-shadow: 0 0 0 3px var(--glow-blue) !important;
  }
  header select option {
    background: var(--panel-solid);
    color: var(--text);
  }
  
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.2px;
  }
  .brand b {
    font-weight: 800;
    background: linear-gradient(100deg, #4285f4, #a142f4, #ea4335, #fbbc05, #34a853, #4285f4);
    background-size: 260% 100%;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: brandShimmer 9s linear infinite;
  }
  @keyframes brandShimmer { to { background-position: 260% 0; } }
  .logomark { transition: transform .5s var(--ease); }
  .brand:hover .logomark { transform: rotate(-12deg) scale(1.1); }
  .port-badge {
    font-size: 10.5px;
    padding: 3px 10px;
    border-radius: 999px;
    background: rgba(26, 115, 232, 0.1);
    color: #1a73e8;
    border: 1px solid rgba(26, 115, 232, 0.22);
    font-weight: 700;
    letter-spacing: 0.3px;
  }
  :root[data-theme=dark] .port-badge { background: rgba(66,133,244,.16); color: #7aa9f7; border-color: rgba(66,133,244,.3); }

  .folder {
    display: flex;
    align-items: center;
    gap: 6px;
    background: transparent !important;
    border: none !important;
    padding: 0;
  }
  .folder input {
    width: 168px;
  }

  select, button {
    background: var(--user);
    color: #fff;
    border: none;
    border-radius: 999px;
    padding: 9px 18px;
    font-size: 13px;
    cursor: pointer;
    font-weight: 600;
    font-family: inherit;
    letter-spacing: -0.01em;
    transition: transform .24s var(--ease), box-shadow .24s var(--ease), background .24s var(--ease), color .24s var(--ease);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 1px 2px rgba(16,24,40,.08), 0 4px 12px rgba(26,115,232,.18);
  }
  select:hover, button:hover {
    transform: translateY(-2px);
    box-shadow: 0 2px 4px rgba(16,24,40,.08), 0 10px 24px rgba(26,115,232,.28);
  }
  button:active { transform: translateY(0) scale(.985); transition-duration: .08s; }
  button:focus-visible, a.btn:focus-visible, input:focus-visible, textarea:focus-visible {
    outline: none; box-shadow: 0 0 0 3px var(--glow-blue), 0 0 0 1px var(--user);
  }
  button.ghost {
    background: var(--field);
    color: var(--text);
    border: none;
    box-shadow: none;
  }
  button.ghost:hover {
    background: var(--field-hover);
    color: var(--ink);
    box-shadow: 0 4px 14px rgba(16,24,40,.08);
  }

  /* Zero-G Physics Toggle Button */
  .zerog-btn {
    background: transparent !important;
    border: 1px solid rgba(161,66,244,0.28) !important;
    color: #8b3fd6 !important;
    font-weight: 600;
  }
  .zerog-btn:hover { background: rgba(161,66,244,0.08) !important; border-color: rgba(161,66,244,0.45) !important; }
  .zerog-btn.active {
    background: linear-gradient(135deg, #7c3aed, #4285f4) !important;
    border-color: transparent !important;
    color: #ffffff !important;
    box-shadow: 0 2px 6px rgba(124,58,237,.24), 0 10px 24px rgba(124,58,237,.26) !important;
  }
  :root[data-theme=dark] .zerog-btn { color: #c79bf5 !important; }

  /* Chat History Sidebar Drawer */
  #sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 300px;
    background: var(--panel-solid);
    border-right: 1px solid var(--border);
    z-index: 100;
    display: flex;
    flex-direction: column;
    transform: translateX(-100%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 10px 0 35px rgba(0,0,0,0.4);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
  }
  #sidebar.open {
    transform: translateX(0);
  }
  #sidebarOverlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 99;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
    backdrop-filter: blur(4px);
  }
  #sidebarOverlay.visible {
    opacity: 1;
    pointer-events: auto;
  }
  .sb-head {
    padding: 18px 20px 14px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  /* Sidebar Tabs & Tree View */
  .sb-tabs {
    display: flex;
    gap: 4px;
    background: var(--field);
    padding: 3px;
    border-radius: 999px;
    border: 1px solid var(--border);
  }
  .sb-tab {
    background: transparent;
    color: var(--muted);
    border: none;
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: none;
    transition: all .2s var(--ease);
  }
  .sb-tab.active {
    background: var(--panel-solid);
    color: var(--ink);
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }
  .sb-tab-content {
    display: none;
    flex: 1;
    flex-direction: column;
    overflow: hidden;
  }
  .sb-tab-content.active {
    display: flex;
  }
  .tree-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }
  .tree-item {
    transition: background 0.15s, transform 0.15s;
  }
  .tree-item:hover {
    background: var(--field) !important;
    color: var(--ink);
  }
  .tree-item.is-dir { font-weight: 600; }

  /* Professional Explorer workspace */
  #sidebar { width: 338px; padding: 12px; background: color-mix(in srgb, var(--panel-solid) 92%, transparent); box-shadow: 18px 0 50px rgba(18, 29, 51, .16); }
  .sb-head { padding: 10px 8px 16px; border: 0; }
  .sb-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .sb-title-mark { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 10px; color: #fff; font-size: 14px; background: linear-gradient(135deg, #4285f4, #7c3aed 54%, #ea4335); box-shadow: 0 5px 15px rgba(66, 133, 244, .25); }
  .sb-title-copy { display: flex; flex-direction: column; line-height: 1.15; }
  .sb-title-copy strong { color: var(--ink); font-size: 14px; letter-spacing: -.01em; }
  .sb-title-copy small { color: var(--muted); font-size: 11px; margin-top: 3px; }
  .sb-close { width: 32px; height: 32px; padding: 0; border-radius: 10px; color: var(--muted); background: transparent; border: 1px solid transparent; box-shadow: none; }
  .sb-close:hover { color: var(--ink); background: var(--field); border-color: var(--border); }
  .sb-new-btn { margin: 0 4px 14px; width: calc(100% - 8px); min-height: 42px; border: 1px solid rgba(66, 133, 244, .2); border-radius: 13px; color: #fff; font-weight: 700; text-align: left; padding: 0 15px; background: linear-gradient(135deg, #1a73e8, #4285f4); box-shadow: 0 8px 18px rgba(26, 115, 232, .2); }
  .sb-tabs { display: grid; grid-template-columns: 1fr; gap: 3px; padding: 0 4px 12px; border: 0; border-radius: 0; background: transparent; }
  .sb-tab { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 38px; padding: 0 12px; border-radius: 10px; text-align: left; font-size: 13px; font-weight: 600; }
  .sb-tab.active { background: rgba(66, 133, 244, .12); color: #1a73e8; box-shadow: none; }
  :root[data-theme=dark] .sb-tab.active { color: #8ab4f8; background: rgba(138, 180, 248, .13); }
  .sb-section-label { margin: 4px 16px 8px; color: var(--muted); font-size: 10.5px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
  .sb-workspace-card { margin: 0 4px 12px; padding: 12px; border: 1px solid var(--border); border-radius: 13px; background: color-mix(in srgb, var(--field) 58%, transparent); }
  .sb-workspace-card b { display: block; color: var(--ink); font-size: 12.5px; }
  .sb-workspace-card small { display: block; margin-top: 5px; color: var(--muted); font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sb-tab-content { min-height: 0; }
  .sb-search-box { padding: 0 4px 10px; }
  .sb-search-box input, #fileSearch { min-height: 38px; border-radius: 10px !important; font-size: 12.5px !important; }
  .history-list, .tree-list { padding: 4px; gap: 4px; }
  .history-item { border-radius: 10px; padding: 10px 11px; }
  .tree-item { border-radius: 9px !important; }

  /* Professional, product-grade application header */
  header { margin: 10px 16px 4px; min-height: 56px; padding: 6px 14px; border-radius: 16px; backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); }
  .hdr-left, .hdr-right { gap: 8px; align-items: center; }
  .app-explorer-btn { display: inline-flex; align-items: center; gap: 7px; min-height: 36px; padding: 0 12px !important; border-radius: 11px !important; font-weight: 700; border: 1px solid var(--border); background: var(--field); color: var(--text); transition: all .2s var(--ease); }
  .app-explorer-btn:hover { background: var(--field-hover); border-color: var(--border-hover); transform: translateY(-1px); }
  .app-explorer-btn .hamburger { color: #4285f4; font-size: 15px; }
  .brand { display: flex; align-items: center; gap: 9px; }
  .brand .logomark { width: 30px; height: 30px; filter: drop-shadow(0 2px 5px rgba(66, 133, 244, .25)); }
  .brand-title { font-size: 13.5px; font-weight: 800; color: var(--ink); letter-spacing: -0.01em; }
  .brand-subtitle { font-size: 11.5px; font-weight: 600; color: #4285f4; background: linear-gradient(135deg, #4285f4, #a142f4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .port-badge { display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 8px; background: rgba(66, 133, 244, .09); color: #4285f4; border: 1px solid rgba(66, 133, 244, .22); font: 11px 'JetBrains Mono', monospace; font-weight: 600; }
  .header-workspace { display: flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 999px; background: var(--field); border: 1px solid var(--border); color: var(--muted); font-size: 12px; font-weight: 600; margin: 0 auto; max-width: 260px; overflow: hidden; }
  .header-workspace i { width: 7px; height: 7px; border-radius: 50%; background: #34a853; box-shadow: 0 0 0 3px rgba(52, 168, 83, .16); flex-shrink: 0; }
  .header-workspace span { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hdr-btn { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 12px; border-radius: 11px; border: 1px solid var(--border); background: var(--field); color: var(--text); font-size: 12.5px; font-weight: 600; cursor: pointer; transition: all .2s var(--ease); text-decoration: none; white-space: nowrap; }
  .hdr-btn:hover { background: var(--field-hover); border-color: var(--border-hover); transform: translateY(-1px); }
  .hdr-dash-btn { background: rgba(16, 185, 129, 0.1); color: #10b981; border-color: rgba(16, 185, 129, 0.3); font-weight: 700; }
  .hdr-dash-btn:hover { background: rgba(16, 185, 129, 0.18); border-color: #10b981; box-shadow: 0 2px 10px rgba(16, 185, 129, 0.18); }
  .cmd-btn { min-height: 36px; border-radius: 11px !important; color: var(--muted) !important; font-weight: 600; }
  .full-access-btn { display: inline-flex; align-items: center; gap: 5px; min-height: 36px; padding: 0 12px !important; border-radius: 11px !important; background: rgba(245, 158, 11, 0.09); color: #d97706; border: 1px solid rgba(245, 158, 11, 0.28); font-size: 12px; font-weight: 700; transition: all .2s var(--ease); }
  .full-access-btn.on { background: rgba(52, 168, 83, 0.1); color: #34a853; border-color: rgba(52, 168, 83, 0.35); }
  .zerog-btn { display: inline-flex; align-items: center; gap: 5px; min-height: 36px; padding: 0 11px; border-radius: 11px; border: 1px solid var(--border); background: var(--field); color: var(--muted); font-size: 12px; font-weight: 600; transition: all .2s var(--ease); }
  .zerog-btn.active { background: rgba(161, 66, 244, 0.14); color: #a142f4; border-color: rgba(161, 66, 244, 0.4); box-shadow: 0 0 10px rgba(161, 66, 244, 0.2); }
  #theme { width: 36px; min-height: 36px; padding: 0 !important; border-radius: 11px !important; display: inline-grid; place-items: center; font-size: 14px; }
  @media (max-width: 1180px) { .header-workspace { display: none; } }
  @media (max-width: 860px) { .zg-text, .brand-subtitle, .port-badge { display: none !important; } }
  @media (max-width: 760px) { .cmd-btn span, .hdr-dash-btn span:last-child { display: none; } header { margin: 8px 10px 3px; padding: 6px 10px; } #sidebar { width: min(338px, 92vw); } }

  /* Signed-in Google identity — always visible when AGY authentication succeeds */
  #prof:not(.hidden) { display: flex; }
  #prof {
    min-height: 38px;
    padding: 3px 5px 3px 3px;
    gap: 8px;
    border: 1px solid var(--border-strong);
    border-radius: 12px;
    background: var(--field);
    box-shadow: 0 1px 0 rgba(255, 255, 255, .05) inset;
  }
  #prof .profile-avatar-frame {
    width: 34px; height: 34px; padding: 2px; flex: 0 0 auto; border-radius: 50%;
    background: conic-gradient(#4285f4 0 25%, #34a853 0 50%, #fbbc05 0 75%, #ea4335 0);
    box-shadow: 0 0 0 1px rgba(255, 255, 255, .12), 0 2px 7px rgba(0, 0, 0, .18);
  }
  #prof .ava { width: 30px; height: 30px; font-size: 12px; box-shadow: none; overflow: hidden; background: var(--panel-solid); }
  #prof .ava img { display: block; width: 100%; height: 100%; object-fit: cover; }
  #prof .who { display: flex !important; min-width: 0; }
  #prof .who b { display: flex; align-items: center; gap: 5px; max-width: 260px; font-size: 11.5px; }
  #prof .who b > span:not(.chip) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #prof .who small { font-size: 10px; }
  .google-account-mark { color: #4285f4; font-size: 13px; font-weight: 800; font-family: Arial, sans-serif; }
  .profile-account-chip { background: #1a73e8; }
  .profile-switch { width: 28px; height: 28px; padding: 0 !important; border-radius: 8px !important; color: var(--muted) !important; }
  .profile-switch:hover { color: var(--ink) !important; background: var(--field-hover) !important; }

  .clean-nav-header {
    position: relative;
    z-index: 80;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 16px;
    min-height: 60px;
    margin: 0;
    padding: 0 20px;
    border: 0;
    border-bottom: 1px solid var(--border);
    border-radius: 0;
    background: color-mix(in srgb, var(--panel-solid) 96%, transparent);
    box-shadow: none;
    backdrop-filter: blur(22px);
    -webkit-backdrop-filter: blur(22px);
  }
  .clean-nav-header:hover { border-color: var(--border); box-shadow: none; }
  .clean-nav-brand { display: flex; align-items: center; min-width: 0; gap: 9px; color: var(--ink); font-family: 'Google Sans', sans-serif; font-size: 16.5px; font-weight: 600; letter-spacing: -.02em; white-space: nowrap; }
  .clean-nav-brand b { font-weight: 700; background: linear-gradient(100deg, #4285f4, #a142f4 40%, #ea4335 72%, #fbbc05); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent; }
  .clean-nav-brand .logomark { width: 26px; height: 26px; }
  .clean-port-badge { display: none !important; }

  /* Markazdagi ish indikatori — bo'sh bo'lsa joy egallamaydi */
  .hdr-live { display: flex; align-items: center; justify-content: center; gap: 8px; min-width: 0; }

  /* O'ng tomon: uch belgili tugma, ortiqcha menyu va hisob */
  .hdr-actions { display: flex; align-items: center; justify-content: flex-end; gap: 2px; min-width: 0; }
  .hdr-icon {
    display: grid; place-items: center; width: 34px; height: 34px; flex: 0 0 34px;
    padding: 0; border: 0; border-radius: 9px; background: transparent;
    color: var(--muted); box-shadow: none; cursor: pointer;
    transition: background .16s var(--ease), color .16s var(--ease);
  }
  .hdr-icon:hover { background: var(--field); color: var(--ink); transform: none; box-shadow: none; }
  .hdr-icon svg { width: 18px; height: 18px; fill: none; stroke: currentColor;
    stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; }
  .hdr-icon.job-stop { color: #ea4335; }
  .hdr-icon.job-stop svg { fill: currentColor; stroke: none; }
  .hdr-icon.job-stop:hover { background: rgba(234,67,53,.12); }

  .clean-nav-menu { position: relative; display: flex; align-items: center; }
  .clean-nav-trigger[aria-expanded="true"] { background: var(--field); color: var(--ink); }
  .clean-nav-dropdown {
    position: absolute;
    top: calc(100% - 4px);
    left: 50%;
    width: 318px;
    display: none;
    padding: 7px;
    border: 1px solid color-mix(in srgb, var(--border-strong) 72%, transparent);
    border-radius: 18px;
    background: color-mix(in srgb, var(--panel-solid) 94%, transparent);
    box-shadow: 0 24px 60px rgba(0,0,0,.20), 0 5px 14px rgba(0,0,0,.10), 0 1px 0 rgba(255,255,255,.1) inset;
    backdrop-filter: blur(22px) saturate(135%);
    -webkit-backdrop-filter: blur(22px) saturate(135%);
    transform: translateX(-50%);
  }
  .clean-nav-dropdown.open { display: grid; gap: 3px; animation: cleanMenuIn .16s var(--ease) both; }
  @keyframes cleanMenuIn { from { opacity: 0; transform: translateX(-50%) translateY(-6px) scale(.98); } to { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); } }
  .clean-nav-item {
    width: 100%;
    min-height: 56px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 10px;
    border: 1px solid transparent;
    border-radius: 12px;
    background: transparent;
    box-shadow: none;
    color: var(--text);
    text-align: left;
    text-decoration: none;
    font-size: 16px;
  }
  .clean-nav-item:hover { border-color: transparent; background: color-mix(in srgb, var(--field-hover) 86%, #4285f4 14%); box-shadow: none; color: var(--ink); transform: none; }
  .nav-icon { width: 34px; height: 34px; display: grid; place-items: center; flex: 0 0 auto; border: 1px solid color-mix(in srgb, var(--border) 78%, transparent); border-radius: 10px; background: color-mix(in srgb, var(--field) 84%, transparent); color: #5f83cc; }
  .nav-icon svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; }
  .nav-icon-command { font-family: 'JetBrains Mono', monospace; font-size: 17px; font-weight: 600; }
  .clean-nav-item:hover .nav-icon { border-color: rgba(66,133,244,.26); background: rgba(66,133,244,.12); color: #4285f4; }
  .clean-nav-item > .nav-copy { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .clean-nav-item b { color: var(--ink); font-size: 13px; font-weight: 650; letter-spacing: -.012em; }
  .clean-nav-item small { overflow: hidden; color: var(--muted); font-size: 11px; font-weight: 450; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
  .clean-nav-divider { height: 1px; margin: 5px 6px; background: color-mix(in srgb, var(--border) 82%, transparent); }
  .clean-nav-item.full-access-btn, .clean-nav-item.full-access-btn.on { min-height: 56px; padding: 9px 10px !important; border: 1px solid transparent; border-radius: 12px !important; background: transparent; box-shadow: none; }
  .clean-nav-item.full-access-btn:hover { background: var(--field-hover); border-color: transparent; }
  .clean-nav-item.full-access-btn.on { color: #34a853; }
  .clean-nav-item#theme { width: 100%; min-height: 56px; display: flex; padding: 9px 10px !important; border-radius: 12px !important; justify-content: flex-start; font-size: 16px; }
  .clean-nav-item#zeroGBtn.active { border-color: transparent; background: var(--field-hover); box-shadow: none; color: #a142f4; }
  .clean-nav-profile { min-width: 0; display: flex; align-items: center; justify-content: flex-end; margin-left: 6px; }
  .clean-nav-profile #prof { flex: 0 1 auto; }
  /* Hisob chipi: faqat avatar va pochta. Tarif/plan qatori olib tashlandi —
     u hech qachon o'zgarmaydi va sarlavhani og'irlashtiradi. */
  .clean-nav-profile .ava { width: 28px; height: 28px; font-size: 12px; box-shadow: none; }
  .clean-nav-profile .who small,
  .clean-nav-profile .profile-account-chip,
  .clean-nav-profile .google-account-mark { display: none !important; }
  .clean-nav-profile .who b { font-size: 12.5px; font-weight: 500; color: var(--muted); }
  .clean-nav-profile .profile-switch { width: 26px; height: 26px; padding: 0; font-size: 12px; }
  @media (max-width: 1050px) {
    .clean-nav-profile #prof .who { display: none !important; }
  }
  @media (max-width: 680px) {
    .clean-nav-header { min-height: 54px; padding: 0 10px; }
    .clean-nav-brand { font-size: 15px; }
    .clean-nav-dropdown { left: auto; right: 0; transform: none; width: min(294px, calc(100vw - 24px)); }
    .clean-nav-dropdown.open { animation-name: cleanMenuInMobile; }
    @keyframes cleanMenuInMobile { from { opacity: 0; transform: translateY(-6px) scale(.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
  }
  .history-share {
    opacity: 0;
    background: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 13px;
    color: var(--muted);
    border-radius: 8px;
    box-shadow: none;
    transition: all 0.2s;
    cursor: pointer;
  }
  .history-item:hover .history-share {
    opacity: 1;
  }
  .history-share:hover {
    color: #1a73e8;
    background: rgba(26, 115, 232, 0.15);
  }
  .history-actions {
    display: flex;
    gap: 2px;
    align-items: center;
    flex-shrink: 0;
  }

  /* Ulashilgan sessiyalar */
  .shared-sessions-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
  }
  .shared-session-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-radius: 14px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text);
    transition: all 0.2s;
    background: rgba(26, 115, 232, 0.04);
    border: 1px solid rgba(26, 115, 232, 0.12);
  }
  .shared-session-card:hover {
    background: rgba(26, 115, 232, 0.1);
    border-color: rgba(26, 115, 232, 0.3);
    transform: translateX(3px);
  }
  .shared-session-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow: hidden;
    flex: 1;
  }
  .shared-session-title {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 13px;
    font-weight: 500;
  }
  .shared-session-meta {
    font-size: 11px;
    color: var(--muted);
  }
  .shared-session-actions {
    display: flex;
    gap: 4px;
    align-items: center;
    flex-shrink: 0;
  }
  .shared-session-actions button {
    background: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 13px;
    color: var(--muted);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: none;
  }
  .shared-session-actions button:hover {
    color: var(--ink);
    background: var(--field);
  }
  .shared-session-actions .shared-del:hover {
    color: #ea4335;
    background: rgba(234, 67, 53, 0.15);
  }
  .shared-session-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 10.5px;
    font-weight: 600;
    background: linear-gradient(135deg, rgba(26,115,232,.15), rgba(124,58,237,.12));
    color: #7c8db5;
    letter-spacing: .3px;
  }

  /* Share toast */
  .share-toast {
    position: fixed;
    bottom: 80px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: rgba(26, 115, 232, 0.95);
    color: #fff;
    padding: 10px 24px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 500;
    z-index: 10000;
    opacity: 0;
    transition: all 0.3s ease;
    pointer-events: none;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 32px rgba(26, 115, 232, 0.3);
  }
  .share-toast.visible {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }

  /* Calm graphite dark theme: no cartoon glow, particles, or moving gradients */
  :root[data-theme=dark] {
    --bg: #111214;
    --bg-soft: #17181b;
    --panel: rgba(24, 25, 28, .94);
    --panel-solid: #1a1b1f;
    --border: rgba(255, 255, 255, .10);
    --border-strong: rgba(255, 255, 255, .18);
    --field: #202126;
    --field-hover: #292b30;
    --aurora-a: rgba(66, 133, 244, .04);
    --aurora-b: rgba(161, 66, 244, .025);
    --aurora-c: transparent;
    --aurora-d: transparent;
  }
  :root[data-theme=dark] #aurora { opacity: .18; filter: blur(120px); }
  :root[data-theme=dark] #aurora i { animation: none; }
  :root[data-theme=dark] #grid-veil { opacity: .13; }
  :root[data-theme=dark] #agCanvas { display: none; }
  :root[data-theme=dark] header { box-shadow: 0 4px 18px rgba(0, 0, 0, .22); }
  @media (max-width: 980px) { #prof .who { display: none !important; } #prof { padding-right: 3px; } }

  .sb-search-box {
    padding: 0 16px 10px;
  }
  .sb-search-box input {
    width: 100%;
  }
  .history-list {
    flex: 1;
    overflow-y: auto;
    padding: 6px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .history-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-radius: 14px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text);
    transition: all 0.2s;
    background: transparent;
    border: 1px solid transparent;
  }
  .history-item:hover {
    background: var(--field);
    border-color: var(--border);
    color: var(--ink);
    transform: translateX(3px);
  }
  .history-item.active {
    background: rgba(26, 115, 232, 0.1);
    border-color: rgba(26, 115, 232, 0.3);
    color: var(--user);
    font-weight: 600;
  }
  .history-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow: hidden;
    flex: 1;
  }
  .history-title {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 13px;
  }
  .history-date {
    font-size: 11px;
    color: var(--muted);
  }
  .history-del {
    opacity: 0;
    background: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 13px;
    color: var(--muted);
    border-radius: 8px;
    box-shadow: none;
    transition: all 0.2s;
  }
  .history-item:hover .history-del {
    opacity: 1;
  }
  .history-del:hover {
    color: #ea4335;
    background: rgba(234, 67, 53, 0.15);
  }

  .prof { display: flex; align-items: center; gap: 10px; }
  .ava {
    width: 36px; height: 36px; border-radius: 50%;
    display: grid; place-items: center; color: #fff; font-weight: 700; font-size: 14px;
    background: linear-gradient(135deg, #4285f4, #1a73e8);
    box-shadow: 0 2px 10px rgba(66,133,244,0.3);
  }
  .ava.pro {
    background: conic-gradient(from 0.25turn, #4285f4, #ea4335, #fbbc05, #34a853, #4285f4);
    padding: 2px;
  }
  .ava.pro span {
    width: 100%; height: 100%; border-radius: 50%;
    background: var(--panel-solid); color: var(--ink); display: grid; place-items: center;
  }
  .who { display: flex; flex-direction: column; line-height: 1.2; }
  .who b { font-size: 13px; color: var(--ink); }
  .who small { font-size: 11px; color: var(--muted); }
  .chip {
    font-size: 9px; font-weight: 800; letter-spacing: 0.5px;
    color: #fff; background: linear-gradient(90deg, #4285f4, #34a853);
    border-radius: 8px; padding: 2px 6px; margin-left: 4px;
  }

  main {
    position: relative;
    z-index: 1;
    flex: 1;
    overflow-y: auto;
    padding: 24px 16px;
    scroll-behavior: smooth;
  }
  .wrap { max-width: 900px; margin: 0 auto; min-height: 100%; display: flex; flex-direction: column; gap: 20px; }
  /* Bo'sh holatda salomlashuv qolgan bo'sh joyning o'rtasida turadi — aks
     holda u tepaga yopishib, ostida katta quruq maydon qolardi. Hisob
     chizig'i baribir tepada qoladi, chunki u alohida element. */
  #welcomeBox { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  #welcomeBox.hidden { display: none; }

  .hero { text-align: center; margin-top: 2vh; animation: fadeInDown .6s var(--ease) both; }
  @keyframes fadeInDown { from { opacity: 0; transform: translateY(-15px); } to { opacity: 1; transform: translateY(0); } }
  .hero .logo {
    font-size: clamp(30px, 5vw, 42px); font-weight: 700; color: var(--ink);
    display: flex; gap: 14px; justify-content: center; align-items: center;
    letter-spacing: -0.03em;
  }
  .hero p { color: var(--muted); margin: 12px 0 26px; font-size: 15.5px; line-height: 1.6; }

  .hero-title {
    margin: 6px 0 0;
    font-size: clamp(30px, 4.4vw, 46px);
    font-weight: 700;
    letter-spacing: -0.035em;
    line-height: 1.12;
    color: var(--ink);
  }
  .hero-title em {
    font-style: normal;
    background: linear-gradient(100deg, #1a73e8, #7c3aed 45%, #ea4335 75%, #fbbc05);
    background-size: 220% 100%;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: brandShimmer 11s linear infinite;
  }
  /* Bo'sh oyna: savol va tushuntirish matni o'rniga yagona brend belgisi.
     Nima qilish kerakligini pastdagi to'rt yo'l va yozuv maydoni aytadi. */
  .bosh-brend {
    display: flex; align-items: center; justify-content: center; gap: 13px;
    margin: 0 0 4px; animation: cardIn .5s var(--ease) both;
  }
  .bosh-brend svg { width: 40px; height: 40px; }
  /* Birinchi so'z oddiy rangda, ikkinchisi rangli — avvalgi ko'rinishdagidek */
  .bosh-brend span {
    font-size: clamp(28px, 3.2vw, 36px); font-weight: 700; letter-spacing: -.035em;
    color: var(--ink);
  }
  .bosh-brend b {
    font-weight: 700;
    background: linear-gradient(100deg, #4285f4, #a142f4 40%, #ea4335 72%, #fbbc05);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent; color: transparent;
  }
  .hero-sub {
    margin: 10px auto 0; max-width: 620px;
    color: var(--muted); font-size: 14.5px; line-height: 1.55;
  }
  .hero-sub b { font-weight: 550; color: var(--text); }

  .quick-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
    margin: 22px 0 0;
  }
  /* ——— HISOB PANELI: doim ko'rinib turadigan biznes ko'rsatkichlari ——— */
  /* Hisob holati — karta emas, ingichka holat chizig'i. Bitta qatorga
     joylashadi: raqamlar chapda, ikkita belgili tugma o'ngda. */
  .hisob-bar {
    position: sticky; top: 0; z-index: 30;
    display: flex; flex-direction: row; align-items: center; gap: 4px;
    margin: 0 0 8px; padding: 5px 6px;
    border: 1px solid var(--border); border-radius: 14px;
    background: var(--panel-solid); box-shadow: none;
    backdrop-filter: var(--glass-blur);
  }
  .hisob-head { order: 2; display: flex; align-items: center; gap: 2px; flex: 0 0 auto; }
  .hisob-title { display: none; }
  /* Qisqa xulosa faqat panel yig'ilganda kerak — ochiq turganda raqamlar
     baribir ko'rinib turibdi va takror bo'lib qoladi. */
  .hisob-brief { display: none; }
  .hisob-bar.yigilgan .hisob-brief {
    display: block; order: 1; flex: 1; min-width: 0; padding-left: 8px;
    font-size: 12px; color: var(--muted);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .hisob-toggle {
    display: grid; place-items: center; width: 30px; height: 30px; padding: 0;
    border: 0; border-radius: 9px; cursor: pointer;
    background: transparent; color: var(--muted);
    font-family: inherit; font-size: 13px; line-height: 1;
    transition: background .16s var(--ease), color .16s var(--ease);
  }
  .hisob-toggle:hover { background: var(--field-hover); color: var(--ink); }
  .hisob-toggle span:not(.hisob-chev) { display: none; }
  .hisob-chev { display: inline-block; transition: transform .22s var(--ease);
                font-size: 13px; line-height: 1; }
  .hisob-bar.yigilgan .hisob-chev { transform: rotate(-90deg); }

  .hisob-cells {
    order: 1; flex: 1; min-width: 0;
    display: flex; flex-wrap: nowrap; gap: 2px; align-items: stretch;
    overflow: hidden; transition: max-height .26s var(--ease), opacity .2s var(--ease);
    max-height: 200px; opacity: 1;
  }
  .hisob-bar.yigilgan .hisob-cells { max-height: 0; opacity: 0; flex: 0 0 0; }
  .hisob-cell {
    flex: 1 1 0; min-width: 0;
    display: flex; flex-direction: column; gap: 1px; align-items: flex-start;
    padding: 5px 10px; border: 1px solid transparent; border-radius: 9px;
    background: transparent; color: var(--text); cursor: pointer;
    font-family: inherit; text-align: left; transition: all .16s var(--ease);
  }
  .hisob-cell:hover { background: var(--field-hover); border-color: var(--border-hover); }
  .hisob-cell .hc-label {
    font-size: 10px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase;
    color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 100%;
  }
  .hisob-cell .hc-value {
    font-size: 15px; font-weight: 650; letter-spacing: -.02em; color: var(--ink);
    font-variant-numeric: tabular-nums; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; max-width: 100%;
  }
  /* Ikkilamchi izoh ("0 xil tovar", "savdo 0") — panelni ikki barobar
     baland qiladi, lekin yangilik bermaydi. Tafsilot kerak bo'lsa katak
     bosiladi va to'liq bo'lim ochiladi. */
  .hisob-cell .hc-sub { display: none; }
  /* Qo'shimcha valyutalar: asosiysi tepada katta, qolganlari ostida mayda
     ustun bo'lib tushadi — bir qatorga tiqilib ustma-ust tushmaydi. */
  .hisob-cell .hc-extra { display: none; flex-direction: column; gap: 1px; width: 100%; }
  .hisob-cell .hc-extra.on { display: flex; }
  .hisob-cell .hc-extra span {
    font-size: 12px; font-weight: 650; color: var(--text);
    font-variant-numeric: tabular-nums; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }
  .hisob-cell[data-bolim="kassa"] { min-width: 132px; }
  .hisob-cell.ok    .hc-value { color: #188038; }
  .hisob-cell.ogoh  .hc-value { color: #d93025; }
  .hisob-cell.active { border-color: var(--border-hover); background: var(--field-hover); }
  :root[data-theme=dark] .hisob-cell.ok   .hc-value { color: #4ade80; }
  :root[data-theme=dark] .hisob-cell.ogoh .hc-value { color: #f87171; }

  .hisob-detail {
    margin: -6px 0 14px; padding: 14px 16px;
    border: 1px solid var(--border); border-radius: 14px;
    background: var(--panel-solid); box-shadow: var(--card-shadow);
    font-size: 13px; max-height: 46vh; overflow-y: auto;
  }
  .hisob-detail h4 {
    margin: 0 0 8px; font-size: 11px; font-weight: 700; letter-spacing: .05em;
    text-transform: uppercase; color: var(--muted);
  }
  .hisob-detail table { width: 100%; border-collapse: collapse; }
  .kassa-jadval td { vertical-align: middle; }
  .kassa-jadval .kassa-son { text-align: right; font-variant-numeric: tabular-nums;
    font-weight: 650; white-space: nowrap; }
  .kassa-jadval .kassa-amal { text-align: right; white-space: nowrap; width: 1%; padding-left: 8px; }
  .kassa-btn { border: 1px solid var(--border); background: var(--field); color: var(--muted);
    border-radius: 8px; width: 26px; height: 26px; cursor: pointer; font-size: 12px;
    line-height: 1; margin-left: 4px; transition: all .15s var(--ease); }
  .kassa-btn:hover { background: var(--field-hover); color: var(--text);
                     border-color: var(--border-hover); }
  .kassa-btn.ochir:hover { color: #f87171; border-color: #f8717155; }
  .kassa-yangi { margin-top: 8px; width: 100%; padding: 8px; border-radius: 10px;
    border: 1px dashed var(--border); background: transparent; color: var(--muted);
    cursor: pointer; font-family: inherit; font-size: 12.5px; font-weight: 600;
    transition: all .15s var(--ease); }
  .kassa-yangi:hover { background: var(--field); color: var(--text);
                       border-color: var(--border-hover); }
  .hisob-detail td { padding: 6px 4px; border-bottom: 1px solid var(--border); }
  .hisob-detail td:last-child { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; color: var(--ink); }
  .hisob-detail tr:last-child td { border-bottom: 0; }
  .hisob-bosh { padding: 6px 2px; color: var(--muted); }
  .hisob-bosh code {
    padding: 1px 6px; border-radius: 5px; background: var(--code-bg);
    font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
  }

  @media (max-width: 640px) {
    .hisob-cell { flex: 1 1 44%; }
    .hisob-cell .hc-value { font-size: 14.5px; }
  }

  .quick-card {
    position: relative;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 13px 15px;
    text-align: left;
    cursor: pointer;
    overflow: hidden;
    box-shadow: none;
    font-family: inherit;
    transition: background .2s var(--ease), border-color .2s var(--ease);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 3px;
    animation: cardIn .55s var(--ease) both;
  }
  .quick-card:nth-child(1) { animation-delay: .05s; }
  .quick-card:nth-child(2) { animation-delay: .12s; }
  .quick-card:nth-child(3) { animation-delay: .19s; }
  .quick-card:nth-child(4) { animation-delay: .26s; }
  @keyframes cardIn { from { opacity: 0; transform: translateY(18px) scale(.97); } to { opacity: 1; transform: none; } }
  /* yuqoridan o'tuvchi yorug'lik chizig'i */
  .quick-card::before {
    content: ''; position: absolute; inset: 0 0 auto 0; height: 2px;
    background: linear-gradient(90deg, transparent, #4285f4, #a142f4, transparent);
    transform: translateX(-100%); transition: transform .7s var(--ease);
  }
  .quick-card::before { display: none; }
  .quick-card:hover {
    border-color: var(--border-hover);
    background: var(--field);
    transform: none;
    box-shadow: none;
  }
  .quick-card .q-title { font-weight: 550; font-size: 13.5px; color: var(--ink); }
  .quick-card .q-desc { font-size: 12px; color: var(--muted); line-height: 1.45; }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 26px;
    padding: 32px;
    box-shadow: var(--card-shadow);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    animation: cardIn .6s var(--ease) both;
  }
  .card h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; color: var(--ink); }
  .card p { margin: 6px 0; color: var(--muted); line-height: 1.6; }
  .step { display: flex; gap: 14px; align-items: flex-start; margin: 18px 0; }
  .num {
    flex: 0 0 32px; height: 32px; border-radius: 50%;
    background: linear-gradient(135deg, var(--user), #4285f4);
    color: #fff; display: grid; place-items: center; font-weight: 700; font-size: 14px;
    box-shadow: 0 4px 12px rgba(31,111,235,0.3);
  }
  a.btn {
    display: inline-block; text-decoration: none;
    background: linear-gradient(135deg, var(--user), #1a73e8);
    color: #fff; border-radius: 22px; padding: 11px 24px; font-weight: 600;
    box-shadow: 0 4px 14px rgba(31,111,235,0.3); transition: all 0.2s;
  }
  a.btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(31,111,235,0.4); }
  .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-top: 10px; }
  input[type=text] {
    flex: 1; min-width: 200px; background: var(--bg); color: var(--text);
    border: 1px solid var(--border); border-radius: 22px; padding: 10px 18px;
    font-size: 14px; font-family: inherit; outline: none; transition: border-color 0.2s;
  }
  input[type=text]:focus { border-color: var(--user); }
  .muted { color: var(--muted); font-size: 13px; }
  .err { color: #ea4335; font-weight: 600; }

  .msg { display: flex; gap: 14px; align-items: flex-start; animation: msgSlide 0.3s ease-out; }
  @keyframes msgSlide { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
  .av {
    width: 36px; height: 36px; border-radius: 50%; flex: 0 0 36px;
    display: grid; place-items: center; font-size: 15px; font-weight: 700; color: #fff;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }
  .msg.user .av { background: linear-gradient(135deg, #1f6feb, #4285f4); }
  .msg.model .av { background: conic-gradient(from 0.25turn, #4285f4, #ea4335, #fbbc05, #34a853, #4285f4); }
  
  .msg.user .bubble {
    background: var(--user-bubble); color: var(--user-text);
    border-color: transparent; border-bottom-right-radius: 4px;
    box-shadow: 0 4px 16px rgba(31,111,235,0.2);
  }
  .bubble {
    border: 1px solid var(--border); border-radius: 22px; padding: 16px 22px;
    line-height: 1.72; word-wrap: break-word; overflow-x: auto; min-width: 0; font-size: 15px;
    transition: box-shadow .3s var(--ease), transform .3s var(--ease);
  }
  /* Agent javobi — pufakcha emas, sahifadagi oddiy matn. Ramka va fon
     javobni og'irlashtiradi va ekranda ikkinchi qatlam hosil qiladi.
     Foydalanuvchi xabari pufakcha bo'lib qoladi: farqni shu ajratib turadi. */
  .msg.model .bubble {
    border: 0; border-radius: 0; padding: 2px 0 0;
    background: transparent; color: var(--text); box-shadow: none;
    /* Pufakcha bo'lmagach javob to'liq kenglikni egallaydi — video, jadval
       va kod bloklari siqilib qolmaydi. */
    flex: 1; min-width: 0;
  }
  .msg.model .bubble:hover { box-shadow: none; }
  /* Ovoz tugmasi — javobning bir qismi emas, qo'shimcha amal.
     Shuning uchun odatda ko'rinmaydi, xabar ustiga kelganda chiqadi. */
  .voice-replay-btn { opacity: 0; transition: opacity .18s var(--ease); }
  .msg:hover .voice-replay-btn, .voice-replay-btn:focus-visible { opacity: 1; }
  .bubble p { margin: 6px 0; }
  .bubble p:empty { display: none; }
  .bubble p:first-child { margin-top: 0; }
  .bubble p:last-child { margin-bottom: 0; }
  .bubble h1, .bubble h2, .bubble h3 { color: var(--ink); margin: 16px 0 8px; font-weight: 700; }
  .bubble ul, .bubble ol { margin: 8px 0; padding-left: 24px; }
  .bubble li { margin: 4px 0; }
  .bubble blockquote {
    border-left: 4px solid var(--user); margin: 12px 0; padding: 8px 16px;
    color: var(--muted); background: rgba(31, 111, 235, 0.08); border-radius: 0 10px 10px 0;
  }
  .bubble code {
    background: var(--code-bg); padding: 3px 8px; border-radius: 6px;
    font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13px; border: 1px solid var(--border);
  }
  
  .code-block {
    background: var(--code-bg); border: 1px solid var(--border); border-radius: 12px;
    margin: 14px 0; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.2);
  }
  .code-head {
    display: flex; justify-content: space-between; align-items: center;
    padding: 9px 16px; background: var(--field); border-bottom: 1px solid var(--border);
    font-size: 12px; color: var(--muted); font-family: 'JetBrains Mono', monospace; font-weight: 600;
  }
  .code-head button {
    padding: 4px 12px; font-size: 11px; border-radius: 14px;
    background: var(--bg); color: var(--text); border: 1px solid var(--border); box-shadow: none;
  }
  .code-block pre {
    margin: 0; padding: 16px; overflow-x: auto;
    font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 13.5px; line-height: 1.55;
  }
  .code-block pre code { background: none; padding: 0; border: none; }

  .desktop-live-btn { border-color: rgba(66,133,244,.42); background: rgba(66,133,244,.1); color: #8ab4f8; }
  .desktop-live-btn:hover { border-color: #4285f4; background: rgba(66,133,244,.18); }
  .desktop-live-overlay { position: fixed; inset: 0; z-index: 1200; display: grid; place-items: center; padding: 22px; background: rgba(4,8,15,.76); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); }
  .desktop-live-overlay.hidden { display: none !important; }
  .desktop-live-window { width: min(1500px, 96vw); height: min(900px, 91vh); display: flex; flex-direction: column; overflow: hidden; border: 1px solid rgba(138,180,248,.34); border-radius: 22px; background: #111722; color: #edf2ff; box-shadow: 0 32px 90px rgba(0,0,0,.56), 0 0 0 1px rgba(255,255,255,.04) inset; }
  .desktop-live-head { display: flex; align-items: center; gap: 12px; min-height: 62px; padding: 0 16px; border-bottom: 1px solid rgba(255,255,255,.1); background: linear-gradient(115deg, rgba(20,29,44,.98), rgba(16,23,35,.96)); }
  .desktop-live-mark { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 11px; color: #fff; background: linear-gradient(135deg, #4285f4, #7b61ff); box-shadow: 0 8px 18px rgba(66,133,244,.28); }
  .desktop-live-title { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 1px; }
  .desktop-live-title strong { font-size: 14px; letter-spacing: -.01em; }
  .desktop-live-title small { color: #9baac1; font-size: 11px; }
  .desktop-live-status { display: inline-flex; align-items: center; gap: 7px; color: #b9c7dd; font: 11px 'JetBrains Mono', monospace; }
  .desktop-live-status i { width: 8px; height: 8px; border-radius: 50%; background: #34a853; box-shadow: 0 0 0 4px rgba(52,168,83,.14); }
  .desktop-live-status.problem i { background: #ea4335; box-shadow: 0 0 0 4px rgba(234,67,53,.14); }
  .desktop-live-head button { min-height: 34px; padding: 0 10px; border: 1px solid rgba(255,255,255,.14); border-radius: 9px; background: rgba(255,255,255,.055); color: #dce7f8; font: 11px inherit; cursor: pointer; }
  .desktop-live-head button:hover { background: rgba(255,255,255,.12); }
  .desktop-live-close { width: 34px; padding: 0 !important; font-size: 16px !important; }
  .desktop-live-body { min-height: 0; flex: 1; display: grid; grid-template-columns: minmax(0, 1fr) 300px; }
  .desktop-live-stage { min-width: 0; min-height: 0; position: relative; display: grid; place-items: center; overflow: hidden; background: radial-gradient(circle at 50% 35%, #233551, #080d15 68%); }
  .desktop-live-stage::before { content: ''; position: absolute; inset: 0; opacity: .22; pointer-events: none; background-image: linear-gradient(rgba(255,255,255,.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.08) 1px, transparent 1px); background-size: 32px 32px; }
  #desktopLiveFrame { position: relative; z-index: 1; display: none; width: 100%; height: 100%; object-fit: contain; }
  .desktop-live-placeholder { position: relative; z-index: 2; max-width: 420px; padding: 30px; text-align: center; }
  .desktop-live-placeholder .desktop-glyph { display: grid; place-items: center; width: 64px; height: 64px; margin: 0 auto 15px; border: 1px solid rgba(138,180,248,.38); border-radius: 20px; background: rgba(66,133,244,.14); color: #a8c7fa; font-size: 29px; }
  .desktop-live-placeholder strong { display: block; font-size: 16px; }
  .desktop-live-placeholder p { margin: 8px 0 0; color: #aebbd0; font-size: 12px; line-height: 1.55; }
  .desktop-live-streaming { position: absolute; z-index: 3; left: 15px; bottom: 15px; display: inline-flex; align-items: center; gap: 8px; padding: 7px 10px; border: 1px solid rgba(255,255,255,.17); border-radius: 999px; background: rgba(8,13,21,.72); color: #e8efff; font: 10.5px 'JetBrains Mono', monospace; backdrop-filter: blur(8px); }
  .desktop-live-streaming i { width: 7px; height: 7px; border-radius: 50%; background: #34a853; box-shadow: 0 0 0 4px rgba(52,168,83,.16); animation: beatPing 1.45s ease infinite; }
  .desktop-live-side { min-height: 0; display: flex; flex-direction: column; border-left: 1px solid rgba(255,255,255,.1); background: #0c121c; }
  .desktop-live-side-head { display: flex; align-items: center; justify-content: space-between; padding: 15px 14px 11px; border-bottom: 1px solid rgba(255,255,255,.08); }
  .desktop-live-side-head strong { font-size: 12px; }
  .desktop-live-side-head span { color: #8ab4f8; font: 10px 'JetBrains Mono', monospace; }
  .desktop-live-actions { flex: 1; overflow-y: auto; padding: 8px; }
  .desktop-live-action { display: grid; grid-template-columns: 19px minmax(0,1fr); gap: 8px; align-items: start; padding: 9px 7px; color: #aebbd0; font-size: 11px; line-height: 1.45; border-bottom: 1px solid rgba(255,255,255,.06); }
  .desktop-live-action b { display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: rgba(138,180,248,.15); color: #a8c7fa; font: 9px 'JetBrains Mono', monospace; }
  .desktop-live-action.active { color: #f4f7ff; background: rgba(66,133,244,.1); border-radius: 9px; border-bottom-color: transparent; }
  .desktop-live-action.active b { background: #4285f4; color: #fff; box-shadow: 0 0 0 4px rgba(66,133,244,.12); }
  .desktop-live-empty { padding: 18px 12px; color: #8c9aaf; font-size: 11px; line-height: 1.5; }
  .desktop-live-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 48px; padding: 0 15px; border-top: 1px solid rgba(255,255,255,.1); background: #0e1520; color: #8c9aaf; font-size: 10.5px; }
  .desktop-live-foot code { color: #a8c7fa; font: 10px 'JetBrains Mono', monospace; }
  @media (max-width: 920px) {
    .desktop-live-body { grid-template-columns: 1fr; }
    .desktop-live-side { max-height: 190px; border-left: 0; border-top: 1px solid rgba(255,255,255,.1); }
    .desktop-live-status { display: none; }
    .desktop-live-btn span:last-child { display: none; }
  }

  /* ═══ Brauzer paneli — agent ochgan sayt shu yerda jonli ko'rinadi ═══ */
  .brauzer-url { display: flex; align-items: center; gap: 8px; padding: 9px 14px;
    border-bottom: 1px solid rgba(255,255,255,.1); background: #0d131e; }
  .brauzer-url input { flex: 1; min-width: 0; height: 32px; padding: 0 12px !important;
    border: 1px solid rgba(255,255,255,.14) !important; border-radius: 9px;
    background: rgba(255,255,255,.05) !important; color: #e8efff !important;
    font: 12px 'JetBrains Mono', monospace !important; }
  .brauzer-url input:focus { border-color: rgba(138,180,248,.6) !important; outline: none; }
  .brauzer-url button { height: 32px; padding: 0 13px; border: 1px solid rgba(255,255,255,.14);
    border-radius: 9px; background: rgba(255,255,255,.055); color: #dce7f8;
    font: 11.5px inherit; cursor: pointer; white-space: nowrap; }
  .brauzer-url button:hover { background: rgba(255,255,255,.12); }
  .brauzer-url button.asosiy { background: linear-gradient(135deg,#4285f4,#7b61ff);
    border-color: transparent; color: #fff; }
  .brauzer-eslatma { padding: 9px 15px; border-top: 1px solid rgba(255,255,255,.08);
    color: #9aa8bd; font-size: 10.5px; line-height: 1.5; background: #0c121c; }
  /* Panel jonli kadr emas, boshqariladigan oyna — kursor shuni bildiradi */
  #brauzerFrame { cursor: default; outline: none; }
  #brauzerFrame:focus-visible { box-shadow: inset 0 0 0 2px rgba(138,180,248,.7); }

  /* Kirish so'ralganda chiqadigan qatlam */
  .brauzer-login { position: absolute; z-index: 5; inset: auto 0 0 0; display: flex;
    justify-content: center; padding: 16px; pointer-events: none; }
  .brauzer-login.hidden { display: none !important; }
  .brauzer-login-ich { pointer-events: auto; max-width: 460px; padding: 15px 18px;
    border: 1px solid rgba(251,188,5,.42); border-radius: 15px;
    background: rgba(14,20,30,.96); backdrop-filter: blur(12px);
    box-shadow: 0 18px 44px rgba(0,0,0,.5); text-align: center; }
  .brauzer-login-ich b { display: block; font-size: 13.5px; color: #fbd34d; }
  .brauzer-login-ich p { margin: 6px 0 0; font-size: 12.5px; color: #e6edfb; line-height: 1.5; }
  .brauzer-login-ich small { display: block; margin-top: 5px; font-size: 11px; color: #97a5ba; }
  .brauzer-login-ich button { margin-top: 11px; padding: 8px 18px; border: 0;
    border-radius: 999px; background: linear-gradient(135deg,#4285f4,#7b61ff);
    color: #fff; font: 600 12.5px inherit; cursor: pointer; }
  .brauzer-login-ich button:hover { filter: brightness(1.1); }

  /* ═══ Jonli reja — agent qaysi qadamda ekani suhbat ichida ko'rinadi ═══ */
  .reja-panel { margin: 2px 0 12px; border: 1px solid var(--border); border-radius: 14px;
    background: var(--panel-solid); overflow: hidden; animation: rejaIn .35s var(--ease) both; }
  @keyframes rejaIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }
  .reja-bosh { display: flex; align-items: center; gap: 9px; padding: 10px 14px;
    border-bottom: 1px solid var(--border); background: var(--field); }
  .reja-bosh b { font-size: 12.5px; letter-spacing: -.01em; }
  .reja-bosh span { margin-left: auto; color: var(--muted);
    font: 10.5px 'JetBrains Mono', monospace; }
  .reja-qator { display: grid; grid-template-columns: 20px minmax(0,1fr); gap: 10px;
    align-items: start; padding: 9px 14px; font-size: 12.8px; line-height: 1.5;
    color: var(--muted); border-top: 1px solid var(--border); }
  .reja-qator:first-of-type { border-top: 0; }
  .reja-qator i { display: grid; place-items: center; width: 18px; height: 18px;
    margin-top: 1px; border-radius: 50%; border: 1.5px solid var(--border);
    font-size: 10px; font-style: normal; color: var(--muted); }
  .reja-qator.tayyor { color: var(--muted); }
  .reja-qator.tayyor span { text-decoration: line-through; opacity: .62; }
  .reja-qator.tayyor i { background: #34a853; border-color: #34a853; color: #fff; }
  .reja-qator.ishlanmoqda { color: var(--ink); font-weight: 500; }
  .reja-qator.ishlanmoqda i { border-color: #4285f4; color: #4285f4;
    animation: rejaPulse 1.5s ease infinite; }
  @keyframes rejaPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(66,133,244,.35); }
    50% { box-shadow: 0 0 0 5px rgba(66,133,244,0); } }

  /* ═══ Ulanishlar paneli ═══ */
  .ulanish-izoh { margin: 0 0 12px; font-size: 12.5px; color: var(--muted); line-height: 1.5; }
  .ulanish-royxat { display: flex; flex-direction: column; gap: 8px; }
  .ulanish-yuklanmoqda { padding: 14px; color: var(--muted); font-size: 12.5px; text-align: center; }
  .ulanish-karta { border: 1px solid var(--border); border-radius: 12px;
    background: var(--field); overflow: hidden; }
  /* Sarlavha ikki qatorli: nom va nishon tepada, tavsif ostida to'liq
     kenglikda. Yon panel tor, shuning uchun hammasi bir qatorga sig'maydi. */
  .ulanish-bosh { display: grid; grid-template-columns: 20px minmax(0,1fr) auto;
    grid-template-areas: "belgi nom nishon" ". izoh izoh";
    align-items: center; gap: 3px 9px; padding: 11px 13px 9px; }
  .ulanish-belgi { grid-area: belgi; font-size: 16px; line-height: 1; }
  .ulanish-nom { grid-area: nom; min-width: 0; }
  .ulanish-nom b { display: block; font-size: 13px; color: var(--ink); font-weight: 600;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  small.ulanish-nom { grid-area: izoh; display: block; margin-top: 2px; font-size: 11.5px;
    color: var(--muted); line-height: 1.5; }
  .ulanish-nishon { grid-area: nishon; align-self: start; padding: 3px 9px; border-radius: 999px;
    font: 600 10.5px 'JetBrains Mono', monospace; letter-spacing: .02em; white-space: nowrap; }
  .ulanish-nishon.ok { background: rgba(52,168,83,.16); color: #34a853; }
  .ulanish-nishon.yoq { background: rgba(255,255,255,.07); color: var(--muted); }
  .ulanish-tana { padding: 0 13px 12px; display: flex; flex-direction: column; gap: 8px; }
  .ulanish-tana.hidden { display: none; }
  .ulanish-qator { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .ulanish-tana input { flex: 1; min-width: 130px; height: 32px; padding: 0 11px !important;
    border: 1px solid var(--border) !important; border-radius: 9px;
    background: var(--panel-solid) !important; color: var(--ink) !important;
    font-size: 12.5px !important; }
  .ulanish-tana button { height: 32px; padding: 0 12px; border: 1px solid var(--border);
    border-radius: 9px; background: var(--panel-solid); color: var(--text);
    font: 12px inherit; cursor: pointer; white-space: nowrap; }
  .ulanish-tana button:hover { background: var(--field-hover); color: var(--ink); }
  .ulanish-tana button.asosiy { background: linear-gradient(135deg,#4285f4,#7b61ff);
    border-color: transparent; color: #fff; font-weight: 600; }
  .ulanish-yordam { font-size: 11.5px; color: var(--muted); line-height: 1.55; }
  .ulanish-yordam code { padding: 1px 5px; border-radius: 4px; background: var(--code-bg);
    font-family: 'JetBrains Mono', monospace; font-size: 10.5px; }
  .ulanish-natija { font-size: 11.5px; line-height: 1.5; }
  .ulanish-natija.ok { color: #34a853; }
  .ulanish-natija.xato { color: #ea4335; }
  .ulanish-yangila { width: 100%; margin-top: 10px; font-size: 12px; }
  .ulanish-qurilma { display: flex; align-items: center; gap: 8px; padding: 7px 9px;
    border: 1px solid var(--border); border-radius: 9px; font-size: 12px; }
  .ulanish-qurilma span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; }

  /* ═══ Jadval oynasi — suhbat burchagida, ish to'xtamaydi ═══ */
  .jadval-panel { position: fixed; right: 18px; bottom: 18px; z-index: 70;
    width: min(560px, calc(100vw - 36px)); max-height: min(62vh, 560px);
    display: flex; flex-direction: column; overflow: hidden;
    border: 1px solid var(--border); border-radius: 16px; background: var(--panel-solid);
    box-shadow: 0 20px 56px rgba(0,0,0,.42); animation: jadvalIn .28s var(--ease) both; }
  @keyframes jadvalIn { from { opacity: 0; transform: translateY(14px) scale(.985); }
    to { opacity: 1; transform: none; } }
  .jadval-panel.hidden { display: none !important; }
  .jadval-panel.yigik { max-height: 46px; }
  .jadval-bosh { display: flex; align-items: center; gap: 9px; padding: 12px 14px;
    border-bottom: 1px solid var(--border); background: var(--field); flex: 0 0 auto; }
  .jadval-bosh b { min-width: 0; flex: 1; font-size: 12.5px; color: var(--ink);
    font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .jadval-bosh a, .jadval-bosh button { flex: 0 0 auto; height: 26px; padding: 0 10px;
    display: inline-flex; align-items: center; border: 1px solid var(--border);
    border-radius: 8px; background: var(--panel-solid); color: var(--muted);
    font: 11.5px inherit; text-decoration: none; cursor: pointer; }
  .jadval-bosh a:hover, .jadval-bosh button:hover { color: var(--ink); background: var(--field-hover); }
  .jadval-bosh a.asosiy { background: #0f9d58; border-color: transparent; color: #fff; font-weight: 600; }
  .jadval-tana { flex: 1; min-height: 0; overflow: auto; }
  .jadval-panel.yigik .jadval-tana { display: none; }
  .jadval-tana table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
  .jadval-tana th, .jadval-tana td { padding: 6px 10px; border-bottom: 1px solid var(--border);
    border-right: 1px solid var(--border); text-align: left; white-space: nowrap;
    max-width: 240px; overflow: hidden; text-overflow: ellipsis; }
  .jadval-tana th { position: sticky; top: 0; background: var(--field); color: var(--ink);
    font-weight: 600; font-size: 11.5px; z-index: 1; }
  .jadval-tana td { color: var(--text); font-variant-numeric: tabular-nums; }
  .jadval-tana tr:hover td { background: var(--field); }
  .jadval-tana .qator-raqam { color: var(--muted); font-size: 10.5px; text-align: right;
    background: var(--panel-solid); }
  .jadval-foot { flex: 0 0 auto; padding: 7px 14px; border-top: 1px solid var(--border);
    color: var(--muted); font-size: 11px; background: var(--field); }
  @media (max-width: 768px) {
    .jadval-panel { right: 8px; left: 8px; bottom: 8px; width: auto; max-height: 52vh; }
  }

  /* ═══ YouTube ═══
     Pleyer darrov yuklanmaydi: avval yengil muqova (thumbnail) chiziladi,
     bosilgandagina iframe qo'yiladi. Shu sabab bir nechta video birga
     ko'rsatilganda sahifa sekinlashmaydi. */
  /* Yolg'iz video butun kenglikni egallamaydi — aks holda u javob emas,
     sahifaning o'zi bo'lib qoladi. Panjaradagi kartalarga bu cheklov tegmaydi. */
  .yt-karta { margin: 10px 0; max-width: 560px; border: 1px solid var(--border);
    border-radius: 14px; overflow: hidden; background: var(--panel-solid); }
  .yt-royxat .yt-karta { max-width: none; }
  /* `border-radius: 0` majburiy: sahifadagi umumiy `button` uslubi dumaloq
     radius beradi va keng-past quti oval bo'lib qoladi — muqova kesilib
     ketadi. `box-shadow: none` ham shu sababdan. */
  .yt-muqova { position: relative; display: block; width: 100%; aspect-ratio: 16 / 9;
    border: 0; border-radius: 0 !important; padding: 0; margin: 0; background: #000;
    cursor: pointer; overflow: hidden; box-shadow: none !important; }
  .yt-muqova:hover { transform: none; }
  .yt-muqova img { width: 100%; height: 100%; object-fit: cover; display: block;
    transition: transform .35s var(--ease), opacity .2s var(--ease); }
  .yt-muqova:hover img { transform: scale(1.03); opacity: .9; }
  .yt-play { position: absolute; inset: 0; display: grid; place-items: center; }
  .yt-play i { width: 58px; height: 40px; border-radius: 11px; background: rgba(0,0,0,.62);
    display: grid; place-items: center; transition: background .2s var(--ease), transform .2s var(--ease); }
  .yt-muqova:hover .yt-play i { background: #ff0033; transform: scale(1.06); }
  .yt-play svg { width: 20px; height: 20px; fill: #fff; }
  .yt-vaqt { position: absolute; right: 8px; bottom: 8px; padding: 2px 6px;
    border-radius: 5px; background: rgba(0,0,0,.78); color: #fff;
    font: 600 11px 'JetBrains Mono', monospace; letter-spacing: .02em; }
  .yt-ramka { display: block; width: 100%; aspect-ratio: 16 / 9; border: 0; background: #000; }
  .yt-meta { display: flex; align-items: flex-start; gap: 10px; padding: 10px 13px;
    border-top: 1px solid var(--border); }
  .yt-meta-matn { min-width: 0; flex: 1; }
  .yt-meta b { display: block; font-size: 13.5px; font-weight: 600; color: var(--ink);
    line-height: 1.4; }
  .yt-meta small { display: block; margin-top: 3px; font-size: 11.5px; color: var(--muted); }
  .yt-meta a { flex: 0 0 auto; padding: 4px 10px; border: 1px solid var(--border);
    border-radius: 8px; color: var(--muted); font-size: 11.5px; text-decoration: none;
    white-space: nowrap; }
  .yt-meta a:hover { color: var(--ink); background: var(--field); }

  /* Qidiruv natijalari — bir nechta video yonma-yon */
  .yt-royxat { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
    gap: 12px; margin: 10px 0; }
  .yt-royxat .yt-karta { margin: 0; }
  .yt-royxat .yt-meta b { font-size: 12.5px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; }

  /* Vosita qaytargan rasm (ekran yoki brauzer skrini) suhbatda ko'rinadi */
  .qadam-rasm { margin: 6px 0 10px; border: 1px solid var(--border); border-radius: 14px;
    overflow: hidden; background: var(--panel-solid); }
  /* Joy oldindan band qilinadi: rasm yuklanguncha quti balandligi ma'lum
     bo'ladi va sahifa yuklangan payt sakramaydi. */
  .qadam-rasm img { display: block; width: 100%; aspect-ratio: 16 / 10;
    max-height: 420px; object-fit: contain; background: #0b0f16; cursor: zoom-in; }
  .qadam-rasm figcaption { padding: 8px 13px; color: var(--muted); font-size: 11.5px;
    border-top: 1px solid var(--border); }

  /* ═══ Ish oqimi — agentning izohi va bajargan qadamlari ═══
     Xom qadamlarni ketma-ket to'kib tashlamaymiz: izoh alohida gap bo'lib
     turadi, uning ostidagi vositalar esa bitta yig'ma qatorga yig'iladi.
     Tafsilot kerak bo'lsa qator bosiladi. */
  .oqim { display: flex; flex-direction: column; margin: 0 0 6px; }
  /* Har bir yozuv o'z tugunida turadi — shu tufayli oqimni qismlab chizamiz
     va rasm/video elementlari qaytadan yaratilmaydi. `display: contents`
     ishlatib bo'lmaydi: unda figure flex elementga aylanib, kengligi
     rasmning yuklanishiga bog'lanib qoladi va quti yig'ilib qoladi. */
  .oqim-orin { display: block; width: 100%; min-width: 0; }
  .oqim-izoh { padding: 7px 0 3px; color: var(--ink); font-size: 14.5px; line-height: 1.62;
    animation: cardIn .3s var(--ease) both; }
  .oqim-guruh { display: flex; align-items: center; gap: 8px; padding: 5px 0;
    color: var(--muted); font-size: 13px; line-height: 1.5; cursor: pointer;
    background: none; border: 0; text-align: left; width: 100%;
    animation: cardIn .3s var(--ease) both; }
  .oqim-guruh:hover { color: var(--ink); }
  .oqim-xulosa { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; }
  .oqim-stat { flex: 0 0 auto; font: 11.5px 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums; }
  .oqim-stat b { color: #34a853; font-weight: 600; }
  .oqim-stat i { color: #ea4335; font-style: normal; margin-left: 5px; }
  .oqim-chev { flex: 0 0 auto; width: 13px; height: 13px; opacity: .55;
    transition: transform .18s var(--ease); }
  .oqim-chev path { fill: none; stroke: currentColor; stroke-width: 2;
    stroke-linecap: round; stroke-linejoin: round; }
  .oqim-guruh.ochiq .oqim-chev { transform: rotate(90deg); }
  .oqim-guruh.faol .oqim-xulosa { color: var(--ink); }
  .oqim-tafsilot { display: none; margin: 0 0 6px 4px; padding: 2px 0 2px 13px;
    border-left: 2px solid var(--border); }
  .oqim-tafsilot.on { display: block; animation: cardIn .22s var(--ease) both; }
  .oqim-qadam { display: flex; gap: 9px; padding: 4px 0; color: var(--muted);
    font-size: 12.5px; line-height: 1.5; }
  .oqim-qadam span { min-width: 0; flex: 1; overflow-wrap: anywhere; }
  .oqim-qadam em { flex: 0 0 auto; font-style: normal; opacity: .72;
    font-family: 'JetBrains Mono', monospace; font-size: 11px; }

  footer {
    position: relative; z-index: 10; border-top: none !important;
    background: transparent !important; backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
    padding: 16px 20px; box-shadow: none !important;
    animation: hdrIn .6s var(--ease) both;
  }
  .img-preview-bar {
    max-width: 900px; margin: 0 auto 10px auto; display: flex; align-items: center; gap: 10px;
    background: var(--field); padding: 8px 14px; border-radius: 16px; border: 1px solid var(--border);
    animation: cardIn .35s var(--ease) both;
  }
  .img-preview-bar.hidden { display: none !important; }
  .img-preview-bar img { max-height: 70px; border-radius: 8px; border: 1px solid var(--border); object-fit: contain; }
  .img-preview-bar .remove-btn { background: #ea4335; border: none; border-radius: 50%; width: 22px; height: 22px; padding: 0; display: grid; place-items: center; color: #fff; cursor: pointer; font-size: 12px; }
  .attach-btn { background: var(--panel-solid); border: 1px solid var(--border); color: var(--text); border-radius: 50%; width: 44px; height: 44px; padding: 0; display: grid; place-items: center; font-size: 18px; flex-shrink: 0; transition: all 0.2s; cursor: pointer; }
  .attach-btn:hover { border-color: var(--user); transform: scale(1.06); background: rgba(66, 133, 244, 0.15); }
  .chat-video { width: 100%; max-width: 100%; aspect-ratio: 16 / 9; border-radius: 12px;
    margin: 10px 0; display: block; border: 1px solid var(--border);
    box-shadow: 0 6px 20px rgba(0,0,0,0.25); background: #000; }
  /* Rasm yuklanguncha quti yig'ilib qolmasin — aks holda matn sakrab tushadi */
  .chat-img { max-width: 100%; max-height: 320px; min-height: 90px; border-radius: 12px;
    margin-bottom: 10px; display: block; background: var(--field);
    border: 1px solid var(--border); box-shadow: 0 4px 16px rgba(0,0,0,0.2); }
  /* ═══ Rasm/video tayyorlanmoqda ═══
     Ilgari bu quti to'q ko'k gradient, konus nurli o'tish va katak to'r
     bilan chizilardi — ish oynasiga emas, ekran lavhasiga o'xshardi. Endi
     u oddiy skeleton: kutilayotgan rasmning o'rnini egallab turadi va
     ustidan bir marta mayin yorug'lik o'tadi. */
  .visual-progress-card { overflow: hidden; margin: 2px 0 14px; border: 1px solid var(--border);
    border-radius: 14px; background: var(--panel-solid); }
  /* To'liq kenglik, o'lchovli balandlik: `aspect-ratio` + `max-height` birga
     ishlatilsa brauzer kenglikni qisqartiradi va quti kartaga to'lmay qoladi. */
  .visual-progress-preview { position: relative; width: 100%; height: 200px;
    overflow: hidden; background: var(--field); }
  .visual-progress-source { position: absolute; inset: 0; width: 100%; height: 100%;
    object-fit: cover; opacity: .35; filter: saturate(.7); }
  /* Yorug'lik chizig'i — skeletonlarda odatdagi, ko'zni charchatmaydigan usul */
  .visual-progress-preview::before { content: ''; position: absolute; inset: 0;
    background: linear-gradient(100deg, transparent 28%,
      color-mix(in srgb, var(--ink) 9%, transparent) 46%, transparent 64%);
    background-size: 260% 100%; animation: visualSweep 1.7s linear infinite; }
  .visual-progress-icon { position: absolute; z-index: 1; inset: 0; display: grid;
    place-items: center; color: var(--muted); font-size: 22px; opacity: .5;
    animation: visualPulse 2s ease-in-out infinite; }
  .visual-progress-meta { display: flex; align-items: center; gap: 10px; padding: 11px 14px;
    border-top: 1px solid var(--border); }
  .visual-progress-dot { width: 7px; height: 7px; flex: 0 0 auto; border-radius: 50%;
    background: #4285f4; animation: visualPulse 1.4s ease-in-out infinite; }
  .visual-progress-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .visual-progress-copy strong { color: var(--ink); font-size: 12.5px; font-weight: 600; }
  .visual-progress-copy span { color: var(--muted); font-size: 11.5px; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; }
  .visual-progress-card.done .visual-progress-dot { background: #34a853; box-shadow: 0 0 0 4px rgba(52,168,83,.12); animation: none; }
  .visual-progress-card.done .visual-progress-preview::before { animation: none; opacity: .2; }
  /* Yorug'lik chizig'i chapdan o'ngga suriladi (aylanmaydi) */
  @keyframes visualSweep { from { background-position: 160% 0; } to { background-position: -60% 0; } }
  @keyframes visualPulse { 50% { transform: scale(1.12); opacity: .72; } }
  /* Table & File Link Styling */
  .chat-table-wrapper {
    overflow: hidden;
    margin: 14px 0;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--card-bg, var(--panel-solid));
    box-shadow: 0 4px 14px rgba(0,0,0,0.06);
  }
  .chat-table-head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: var(--field, rgba(0,0,0,0.03));
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    font-size: 13.5px;
    color: var(--ink);
  }
  .chat-table-icon {
    font-size: 15px;
  }
  .chat-table-title {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .chat-table-scroll {
    overflow-x: auto;
    max-height: 480px;
    overflow-y: auto;
  }
  .chat-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    text-align: left;
    white-space: nowrap;
  }
  .chat-table th {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--field);
    color: var(--ink);
    font-weight: 600;
    padding: 10px 14px;
    border-bottom: 2px solid var(--border);
  }
  .chat-table td {
    padding: 9px 14px;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }
  .chat-table tr:last-child td {
    border-bottom: none;
  }
  .chat-table tr:nth-child(even) td {
    background: rgba(0, 0, 0, 0.02);
  }
  :root[data-theme=dark] .chat-table tr:nth-child(even) td {
    background: rgba(255, 255, 255, 0.025);
  }
  .chat-file-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    margin: 6px 0;
    background: var(--user-bubble);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--user-text);
    text-decoration: none;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .chat-file-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(26,115,232,0.2);
    filter: brightness(1.05);
  }
  /* ——— Interactive Excel Widget in Chat ——— */
  .chat-excel-container {
    margin: 14px 0;
    border-radius: 12px;
    border: 1px solid var(--border-strong);
    background: var(--panel-solid);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 100%;
  }
  .excel-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    background: #107c41;
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
  }
  .excel-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .excel-icon-badge {
    background: #ffffff;
    color: #107c41;
    font-weight: 800;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.5px;
  }
  .excel-filename {
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
  }
  .excel-download-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff !important;
    border-radius: 6px;
    text-decoration: none;
    font-size: 12px;
    font-weight: 500;
    transition: background 0.2s;
    border: 1px solid rgba(255, 255, 255, 0.3);
  }
  .excel-download-btn:hover {
    background: rgba(255, 255, 255, 0.35);
  }
  .excel-fx-bar {
    display: flex;
    align-items: center;
    padding: 5px 10px;
    background: var(--field);
    border-bottom: 1px solid var(--border);
    gap: 8px;
    font-size: 12px;
  }
  .excel-cell-id {
    font-weight: 700;
    color: #107c41;
    min-width: 34px;
    text-align: center;
    background: var(--panel-solid);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px 4px;
    font-family: 'JetBrains Mono', monospace;
  }
  .excel-fx-symbol {
    font-style: italic;
    font-weight: bold;
    color: var(--muted);
  }
  .excel-fx-input {
    flex: 1;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 12px;
    background: var(--panel-solid);
    color: var(--text);
    outline: none;
    font-family: 'JetBrains Mono', monospace;
  }
  .excel-fx-input:focus {
    border-color: #107c41;
  }
  .excel-grid-viewport {
    max-height: 280px;
    overflow: auto;
    position: relative;
    background: var(--bg);
  }
  .excel-interactive-table {
    border-collapse: collapse;
    width: 100%;
    font-size: 12.5px;
    user-select: text;
  }
  .excel-interactive-table th {
    background: var(--field);
    color: var(--muted);
    font-weight: 600;
    text-align: center;
    padding: 4px 8px;
    border: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 2;
    font-size: 11px;
  }
  .excel-interactive-table th.row-hdr {
    left: 0;
    z-index: 3;
    width: 36px;
    min-width: 36px;
  }
  .excel-interactive-table td {
    border: 1px solid var(--border);
    padding: 5px 8px;
    color: var(--text);
    background: var(--panel-solid);
    min-width: 90px;
    outline: none;
    white-space: nowrap;
    transition: background 0.15s;
  }
  .excel-interactive-table td:focus, .excel-interactive-table td.selected {
    outline: 2px solid #107c41 !important;
    outline-offset: -2px;
    background: rgba(16, 124, 65, 0.08) !important;
  }
  .excel-interactive-table tr:nth-child(even) td {
    background: rgba(0, 0, 0, 0.015);
  }
  :root[data-theme=dark] .excel-interactive-table tr:nth-child(even) td {
    background: rgba(255, 255, 255, 0.02);
  }
  .excel-bottom-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 12px;
    background: var(--field);
    border-top: 1px solid var(--border);
    font-size: 11.5px;
    color: var(--muted);
  }
  .excel-sheet-tab {
    padding: 2px 10px;
    background: var(--panel-solid);
    border-radius: 4px 4px 0 0;
    border: 1px solid var(--border);
    border-bottom: 2px solid #107c41;
    color: #107c41;
    font-weight: 600;
  }
  /* Google Antigravity Agent Input Design from Screenshot */
  .ag-workspace-selector {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .ag-ws-btn {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    max-width: 190px;
    border-radius: 999px;
    box-shadow: none;
    transition: background 0.2s, color 0.2s, border-color 0.2s;
  }
  .ag-ws-btn span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ag-ws-icon { width: 14px; height: 14px; flex: 0 0 14px; fill: none;
    stroke: currentColor; stroke-width: 1.7; stroke-linejoin: round; }
  .ag-ws-btn:hover {
    background: var(--field-hover);
    color: var(--ink);
  }
  .ag-ws-chevron {
    font-size: 12px;
    color: var(--muted);
  }

  /* Glowing Antigravity Input Box */
  /* Kompozitor kengligi suhbat kengligi bilan bir xil — ilgari 720px edi va
     900px lik suhbatga nisbatan siljib turardi. Ko'p rangli neon soya ham
     olib tashlandi: u ish oynasini o'yinchoqqa o'xshatib qo'yardi. */
  .ag-input-card {
    position: relative;
    max-width: 900px;
    margin: 0 auto;
    background: var(--panel-solid);
    border-radius: 18px;
    padding: 14px 16px 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,.14), 0 10px 34px rgba(0,0,0,.10);
    border: 1px solid var(--border);
    background-clip: padding-box;
    transition: border-color .2s var(--ease), box-shadow .2s var(--ease);
  }
  .ag-input-card:focus-within { border-color: var(--border-hover); }
  /* Rangli chegara faqat fokusda va juda mayin ko'rinadi — doim yonib
     turgan kamalak ramka ish oynasida chalg'itadi. */
  .ag-input-card::before {
    content: '';
    position: absolute;
    inset: -1px;
    border-radius: 19px;
    padding: 1px;
    background: linear-gradient(135deg, #4285f4 0%, #a142f4 35%, #ea4335 70%, #fbbc05 100%);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
    opacity: 0;
    transition: opacity .25s var(--ease);
  }
  .ag-input-card:focus-within::before { opacity: .55; }

  .business-mode-hint {
    display: flex;
    align-items: center;
    gap: 7px;
    margin: -2px 4px 9px;
    color: #0b8043;
    font-size: 11.5px;
    font-weight: 650;
  }
  .business-mode-hint span:last-child { color: var(--muted); font-weight: 500; }
  :root[data-theme=dark] .business-mode-hint { color: #81c995; }

  #input {
    width: 100%;
    resize: none;
    background: transparent;
    color: var(--text);
    border: none;
    outline: none;
    font-size: 15.5px;
    font-family: inherit;
    line-height: 1.5;
    min-height: 48px;
    max-height: 160px;
    padding: 0 4px 10px 4px;
    box-shadow: none !important;
  }
  #input::placeholder {
    color: var(--muted);
    opacity: 0.7;
    font-size: 15.5px;
  }

  .ag-input-footer-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 4px;
  }
  .ag-input-left-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .ag-tool-btn {
    background: transparent;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    box-shadow: none;
    transition: background 0.2s, border-color 0.2s, color 0.2s;
  }
  .ag-tool-btn:hover {
    background: var(--field-hover);
    border-color: var(--border-hover);
    color: var(--ink);
  }
  .ag-plus-btn {
    width: 28px;
    height: 28px;
    padding: 0;
    display: grid;
    place-items: center;
    font-size: 18px;
    font-weight: 400;
    border-radius: 50%;
    border: none;
    color: var(--muted);
  }
  .ag-plus-btn:hover {
    color: var(--ink);
    background: var(--field-hover);
  }

  .ag-model-select-wrap {
    position: relative;
    display: inline-flex;
    align-items: center;
  }
  .ag-model-select-wrap .ag-model-chevron {
    position: absolute;
    left: 10px;
    font-size: 11px;
    color: var(--muted);
    pointer-events: none;
  }
  .ag-model-select {
    appearance: none;
    -webkit-appearance: none;
    background: transparent !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 999px;
    padding: 5px 12px 5px 22px;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    outline: none;
    box-shadow: none !important;
    transition: background 0.2s, border-color 0.2s, color 0.2s;
  }
  .ag-model-select:hover {
    background: var(--field-hover) !important;
    border-color: var(--border-hover) !important;
  }
  .ag-model-select option {
    background: var(--panel-solid);
    color: var(--text);
  }

  .ag-send-circle-btn {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: #0084ff;
    color: #ffffff;
    border: none;
    display: grid;
    place-items: center;
    cursor: pointer;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 132, 255, 0.35);
    transition: transform 0.2s, background 0.2s, box-shadow 0.2s;
  }
  .ag-send-circle-btn:hover {
    background: #0073e6;
    transform: scale(1.06);
    box-shadow: 0 4px 14px rgba(0, 132, 255, 0.45);
  }
  .ag-send-circle-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
  }
  .hidden { display: none !important; }
  .hint { color: var(--muted); font-size: 12px; text-align: center; margin-top: 8px; }
  
  .spinner {
    display: inline-block; width: 14px; height: 14px;
    border: 2px solid rgba(255,255,255,.3); border-radius: 50%;
    border-top-color: #fff; animation: spin .8s linear infinite; margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .full-access-btn {
    background: transparent;
    color: #b45309; border: 1px solid rgba(217,119,6,.3); border-radius: 999px; padding: 8px 16px;
    font-size: 12.5px; font-weight: 600; cursor: pointer; font-family: inherit;
    position: relative; overflow: hidden; box-shadow: none;
    letter-spacing: -0.01em;
    transition: background .25s var(--ease), border-color .25s var(--ease), transform .25s var(--ease), box-shadow .25s var(--ease);
  }
  .full-access-btn:hover {
    background: rgba(217,119,6,.08); border-color: rgba(217,119,6,.5);
    transform: translateY(-2px); box-shadow: 0 6px 18px rgba(217,119,6,.16);
  }
  .full-access-btn.on {
    background: linear-gradient(135deg, #f59e0b, #10b981);
    color: #08301f; border-color: transparent; font-weight: 700;
    box-shadow: 0 2px 6px rgba(16,185,129,.24), 0 10px 24px rgba(16,185,129,.24);
  }
  :root[data-theme=dark] .full-access-btn { color: #fbbf24; border-color: rgba(251,191,36,.32); }
  :root[data-theme=dark] .full-access-btn:hover { background: rgba(251,191,36,.1); }

  .fa-overlay {
    position: fixed; inset: 0; z-index: 110; background: rgba(10,15,28,.42);
    display: grid; place-items: center; backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%); animation: fadeIn .25s ease;
  }
  :root[data-theme=dark] .fa-overlay { background: rgba(0,0,0,.62); }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  .fa-modal {
    background: var(--panel-solid); border: 1px solid var(--border); border-radius: 28px;
    width: min(740px, 94vw); max-height: 88vh; display: flex; flex-direction: column;
    box-shadow: 0 25px 60px rgba(0,0,0,.5), 0 0 80px rgba(66,133,244,.2); animation: modalSlideIn .3s ease;
  }
  @keyframes modalSlideIn { from { opacity: 0; transform: translateY(30px) scale(.95); } to { opacity: 1; transform: translateY(0) scale(1); } }
  .fa-header { padding: 24px 28px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 14px; }
  .fa-header-icon {
    width: 50px; height: 50px; border-radius: 16px;
    background: linear-gradient(135deg, #ff6b35, #f7c948, #38ef7d);
    display: grid; place-items: center; font-size: 26px; box-shadow: 0 4px 16px rgba(255,107,53,.3);
  }
  .fa-header-text h2 { margin: 0; font-size: 21px; color: var(--ink); font-weight: 700; }
  .fa-header-text p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
  .fa-close { margin-left: auto; background: var(--bg); border: 1px solid var(--border); width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; cursor: pointer; font-size: 16px; color: var(--text); }
  .fa-close:hover { background: var(--border); transform: rotate(90deg); }
  .fa-body { padding: 24px 28px; overflow-y: auto; display: flex; flex-direction: column; gap: 20px; }
  .fa-section { background: var(--bg); border: 1px solid var(--border); border-radius: 18px; padding: 20px; }
  .fa-section h3 { margin: 0 0 10px; font-size: 16px; color: var(--ink); display: flex; align-items: center; gap: 10px; }
  .fa-section h3 .fa-icon { width: 30px; height: 30px; border-radius: 10px; display: grid; place-items: center; font-size: 15px; flex: 0 0 30px; }
  .fa-section p, .fa-section li { color: var(--text); font-size: 14px; line-height: 1.7; margin: 4px 0; }
  .fa-section ul { padding-left: 20px; margin: 8px 0; }
  .fa-section code { background: var(--code-bg); padding: 2px 8px; border-radius: 6px; font-size: 12.5px; border: 1px solid var(--border); font-family: 'JetBrains Mono', monospace; color: #38ef7d; }
  .fa-cmd { background: var(--code-bg); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; margin: 10px 0; font-family: 'JetBrains Mono', monospace; font-size: 13px; line-height: 1.6; overflow-x: auto; position: relative; white-space: pre-wrap; color: var(--text); }
  .fa-cmd .copy-btn { position: absolute; top: 8px; right: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 4px 10px; font-size: 11px; cursor: pointer; color: var(--muted); }
  .fa-badge { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; font-weight: 800; letter-spacing: .6px; text-transform: uppercase; padding: 3px 10px; border-radius: 8px; margin-left: 6px; }
  .fa-badge.danger { background: rgba(234,67,53,.15); color: #ea4335; }
  .fa-badge.safe { background: rgba(52,168,83,.15); color: #34a853; }
  .fa-badge.info { background: rgba(66,133,244,.15); color: #4285f4; }
  .fa-toggle-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: var(--panel-solid); border: 1px solid var(--border); border-radius: 12px; margin: 8px 0; }
  .fa-toggle-row span { font-size: 14px; font-weight: 600; color: var(--ink); }
  .fa-toggle { position: relative; width: 48px; height: 26px; cursor: pointer; }
  .fa-toggle input { opacity: 0; width: 0; height: 0; }
  .fa-toggle .slider { position: absolute; inset: 0; background: var(--border); border-radius: 26px; transition: .3s; }
  .fa-toggle .slider::before { content: ''; position: absolute; width: 20px; height: 20px; border-radius: 50%; background: #fff; bottom: 3px; left: 3px; transition: .3s; }
  .fa-toggle input:checked+.slider { background: linear-gradient(135deg, #ff6b35, #38ef7d); }
  .fa-toggle input:checked+.slider::before { transform: translateX(22px); }
  .fa-footer { padding: 16px 28px; border-top: 1px solid var(--border); display: flex; gap: 10px; justify-content: flex-end; }
  .fa-footer button { border-radius: 22px; padding: 10px 24px; font-weight: 700; font-size: 14px; }
  .fa-footer .fa-apply { background: linear-gradient(135deg, #ff6b35, #38ef7d); color: #0d1117; border: none; box-shadow: 0 4px 16px rgba(56,239,125,.3); }
  .fa-footer .fa-cancel { background: var(--bg); color: var(--text); border: 1px solid var(--border); }

  .video-config-status { display: flex; align-items: flex-start; gap: 8px; margin: 10px 0 12px; padding: 10px 11px; border-radius: 11px; background: var(--field); border: 1px solid var(--border); color: var(--muted); font-size: 12px; line-height: 1.45; }
  .video-config-status.ready { color: #188038; border-color: rgba(52,168,83,.35); background: rgba(52,168,83,.08); }
  .video-config-status.problem { color: #c5221f; border-color: rgba(234,67,53,.34); background: rgba(234,67,53,.08); }
  .video-key-label { display: block; margin: 0 0 7px; color: var(--ink); font-size: 12px; font-weight: 700; }
  .video-key-row { display: flex; align-items: center; gap: 7px; }
  .video-key-input { min-width: 0; flex: 1; min-height: 38px; padding: 0 11px; border: 1px solid var(--border); border-radius: 10px; background: var(--panel-solid); color: var(--ink); font: 12px 'JetBrains Mono', monospace; }
  .video-key-input:focus { outline: none; border-color: #4285f4; box-shadow: 0 0 0 3px rgba(66,133,244,.14); }
  .video-config-actions { display: flex; gap: 8px; margin-top: 11px; }
  .video-config-actions button { min-height: 36px; padding: 0 11px; border-radius: 10px; font-size: 12px; font-weight: 700; }
  .video-config-save { background: #1a73e8; color: #fff; border-color: #1a73e8; }
  .video-config-clear { background: transparent; color: var(--muted); border-color: var(--border); }
  .video-config-note { margin: 10px 0 0; color: var(--muted); font-size: 11px; line-height: 1.5; }
  .video-config-note a { color: #1a73e8; }
  .voice-option-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 11px; padding: 10px 11px; border: 1px solid var(--border); border-radius: 11px; background: var(--field); }
  .voice-option-row label { color: var(--ink); font-size: 12px; font-weight: 700; }
  .voice-option-row select { min-width: 118px; min-height: 32px; padding: 0 8px; border: 1px solid var(--border); border-radius: 8px; background: var(--panel-solid); color: var(--ink); font: 12px inherit; }
  .voice-switch { position: relative; display: inline-flex; align-items: center; gap: 8px; color: var(--muted); font-size: 11px; cursor: pointer; }
  .voice-switch input { width: 34px; height: 20px; margin: 0; accent-color: #1a73e8; cursor: pointer; }
  .voice-input-btn.recording { background: rgba(234,67,53,.13); border-color: rgba(234,67,53,.55); color: #d93025; animation: voiceRecordPulse 1.2s ease-in-out infinite; }
  .voice-input-btn:disabled { opacity: .45; cursor: not-allowed; }
  .voice-replay-btn { display: inline-flex; align-items: center; gap: 6px; margin: 10px 0 0; padding: 5px 9px; border: 1px solid var(--border); border-radius: 9px; background: var(--field); color: var(--muted); font: 11px inherit; cursor: pointer; }
  .voice-replay-btn:hover { color: var(--ink); border-color: rgba(66,133,244,.42); background: var(--field-hover); }
  @keyframes voiceRecordPulse { 50% { box-shadow: 0 0 0 6px rgba(234,67,53,0); } }

  /* ══ Ish jarayoni indikatori — lipillovchi Gemini yulduzchasi ══ */
  .thinking {
    display: flex; align-items: center; gap: 11px; user-select: none;
    padding: 2px 0; animation: cardIn .3s var(--ease) both;
  }
  .gem-spark {
    width: 22px; height: 22px; flex: 0 0 22px; display: block;
    transform-origin: 50% 50%;
    animation: gemPulse 1.6s var(--ease) infinite;
    filter: drop-shadow(0 0 6px rgba(66,133,244,.5));
  }
  @keyframes gemPulse {
    0%   { transform: scale(.78) rotate(0deg);   opacity: .5; }
    50%  { transform: scale(1.14) rotate(90deg); opacity: 1; }
    100% { transform: scale(.78) rotate(180deg); opacity: .5; }
  }
  .think-label {
    font-size: 14px; font-weight: 600; letter-spacing: -0.01em; white-space: nowrap;
    background: linear-gradient(90deg, var(--muted) 0%, var(--muted) 34%, #4285f4 47%, #9b72cb 55%, #d96570 62%, var(--muted) 76%, var(--muted) 100%);
    background-size: 280% 100%;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent; color: transparent;
    animation: shimmerText 2.4s linear infinite;
  }
  @keyframes shimmerText { from { background-position: 150% 0; } to { background-position: -150% 0; } }
  .think-time {
    font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: var(--muted);
    background: var(--field); border: 1px solid var(--border); border-radius: 999px;
    padding: 2px 9px; min-width: 44px; text-align: center; font-variant-numeric: tabular-nums;
  }
  .think-beat {
    width: 7px; height: 7px; border-radius: 50%; background: #34a853; flex: 0 0 7px;
    transition: background .3s var(--ease);
  }
  .think-beat.hit { animation: beatPing .9s var(--ease); }
  @keyframes beatPing {
    0%   { transform: scale(1);   box-shadow: 0 0 0 0 rgba(52,168,83,.55); }
    60%  { transform: scale(1.5); box-shadow: 0 0 0 8px rgba(52,168,83,0); }
    100% { transform: scale(1);   box-shadow: 0 0 0 0 rgba(52,168,83,0); }
  }
  .think-beat.stale { background: #fbbc05; }

  /* ishlayotgan javobda avatar ham nafas oladi */
  .msg.model.working .av { animation: avHalo 1.7s var(--ease) infinite; }
  @keyframes avHalo {
    0%, 100% { box-shadow: 0 0 0 0 rgba(66,133,244,.5), 0 4px 12px rgba(0,0,0,.15); }
    55%      { box-shadow: 0 0 0 8px rgba(66,133,244,0), 0 4px 12px rgba(0,0,0,.15); }
  }
  .msg.model.working .bubble { border-color: rgba(66,133,244,.34); }

  /* sarlavhadagi umumiy "ish ketmoqda" tugmasi */
  .job-badge {
    display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
    background: rgba(66,133,244,.1); border: 1px solid rgba(66,133,244,.35);
    color: var(--ink); border-radius: 999px; padding: 6px 14px 6px 10px;
    font-family: inherit; font-size: 12.5px; font-weight: 600; letter-spacing: -0.01em;
    animation: cardIn .3s var(--ease) both;
    transition: background .25s var(--ease), transform .25s var(--ease), box-shadow .25s var(--ease);
  }
  .job-badge:hover { background: rgba(66,133,244,.18); transform: translateY(-1px); box-shadow: 0 6px 18px rgba(66,133,244,.22); }
  .job-badge .gem-spark { width: 16px; height: 16px; flex: 0 0 16px; }
  .job-badge .jb-time {
    font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .job-badge.hidden { display: none !important; }

  /* to'xtatish tugmalari */
  .think-stop {
    margin-left: 2px; background: rgba(234,67,53,.1); border: 1px solid rgba(234,67,53,.35);
    color: #ea4335; border-radius: 999px; padding: 3px 12px; font-family: inherit;
    font-size: 11.5px; font-weight: 700; cursor: pointer; letter-spacing: -0.01em;
    transition: background .2s var(--ease), transform .2s var(--ease);
  }
  .think-stop:hover { background: rgba(234,67,53,.18); transform: translateY(-1px); }
  .think-stop:disabled { opacity: .55; cursor: default; transform: none; }
  .job-stop {
    display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 50%;
    background: rgba(234,67,53,.12); border: 1px solid rgba(234,67,53,.4); color: #ea4335;
    font-size: 12px; font-family: inherit; cursor: pointer;
    transition: background .2s var(--ease), transform .2s var(--ease);
  }
  .job-stop:hover { background: rgba(234,67,53,.22); transform: translateY(-1px); }
  .job-stop.hidden { display: none !important; }

  /* tarix ro'yxatida ishlayotgan suhbat nuqtasi */
  .run-dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #34a853;
    margin-right: 7px; vertical-align: middle; animation: beatPing 1.5s var(--ease) infinite;
  }

  /* oxirgi amal qatori — jonli kursor bilan */
  .act-log .act-live { color: var(--ink); font-weight: 600; }
  .act-log .act-live::after {
    content: '▍'; margin-left: 2px; color: #4285f4; animation: caretBlink 1s steps(1) infinite;
  }
  @keyframes caretBlink { 50% { opacity: 0; } }

  /* nozik scrollbar */
  main::-webkit-scrollbar, .history-list::-webkit-scrollbar, .fa-body::-webkit-scrollbar, #pkList::-webkit-scrollbar { width: 10px; }
  main::-webkit-scrollbar-thumb, .history-list::-webkit-scrollbar-thumb, .fa-body::-webkit-scrollbar-thumb, #pkList::-webkit-scrollbar-thumb {
    background: var(--field-hover); border-radius: 999px; border: 3px solid transparent; background-clip: content-box;
  }
  main::-webkit-scrollbar-thumb:hover { background: var(--border-strong); background-clip: content-box; }
  main::-webkit-scrollbar-track { background: transparent; }

  /* Live Voice — suhbat ichidagi professional karta */
  .cgv-overlay {
    display: none;
    box-sizing: border-box;
    width: min(100%, 760px);
    margin: 2px auto 12px;
    padding: 16px;
    color: var(--ink);
    background: linear-gradient(145deg, var(--panel-solid), var(--panel));
    border: 1px solid var(--border-strong);
    border-radius: 22px;
    box-shadow: 0 18px 46px rgba(15, 23, 42, .13);
    font-family: inherit;
  }
  .cgv-overlay.active {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas: "top top" "main controls";
    gap: 14px 18px;
    animation: cgvCardIn .22s var(--ease) both;
  }
  @keyframes cgvCardIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .cgv-topbar {
    grid-area: top;
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 0;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
  }
  .cgv-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    margin-right: auto;
    color: var(--ink);
    font-size: 13px;
    font-weight: 750;
    letter-spacing: -.01em;
  }
  .cgv-badge small {
    color: var(--muted);
    font-size: 11px;
    font-weight: 600;
  }
  .cgv-dot {
    width: 8px;
    height: 8px;
    flex: 0 0 auto;
    border-radius: 50%;
    background: #34a853;
    box-shadow: 0 0 0 4px rgba(52, 168, 83, .13);
    animation: cgvPulseDot 1.8s ease-in-out infinite;
  }
  @keyframes cgvPulseDot {
    50% { box-shadow: 0 0 0 7px rgba(52, 168, 83, .04); }
  }
  #cgvVoiceSelect {
    max-width: 210px;
    min-height: 34px;
    padding: 0 30px 0 10px;
    color: var(--ink);
    background: var(--field);
    border: 1px solid var(--border);
    border-radius: 9px;
    font: 650 12px inherit;
    outline: none;
    cursor: pointer;
  }
  #cgvVoiceSelect:hover, #cgvVoiceSelect:focus { border-color: #4285f4; }
  .cgv-close-btn {
    width: 34px;
    height: 34px;
    padding: 0;
    border: 1px solid transparent;
    border-radius: 9px;
    color: var(--muted);
    background: transparent;
    font-size: 17px;
    line-height: 1;
    cursor: pointer;
    display: grid;
    place-items: center;
    transition: background .18s ease, color .18s ease, border-color .18s ease;
  }
  .cgv-close-btn:hover {
    color: var(--ink);
    background: var(--field-hover);
    border-color: var(--border);
  }
  .cgv-center {
    grid-area: main;
    display: grid;
    grid-template-columns: 124px minmax(0, 1fr);
    align-items: center;
    gap: 16px;
    min-width: 0;
  }
  .cgv-orb-wrapper {
    position: relative;
    width: 142px;
    height: 142px;
    display: grid;
    place-items: center;
  }
  .cgv-orb-glow {
    position: absolute;
    inset: -10px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(211, 202, 255, .46), rgba(180, 205, 255, .18) 54%, transparent 72%);
    filter: blur(11px);
    pointer-events: none;
  }
  #cgvOrbCanvas {
    width: 138px;
    height: 138px;
    border-radius: 50%;
    position: relative;
    z-index: 1;
  }
  .cgv-status {
    color: var(--ink);
    font-size: 15px;
    font-weight: 760;
    letter-spacing: -.015em;
  }
  .cgv-transcript {
    margin-top: 7px;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.55;
    min-height: 40px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .cgv-controls {
    grid-area: controls;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 9px;
    padding-left: 16px;
    border-left: 1px solid var(--border);
  }
  .cgv-ctrl-btn {
    width: 42px;
    height: 42px;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--field);
    color: var(--ink);
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: transform .18s ease, border-color .18s ease, background .18s ease;
  }
  .cgv-ctrl-btn:hover { transform: translateY(-1px); border-color: var(--border-strong); background: var(--field-hover); }
  .cgv-ctrl-btn.active {
    color: #fff;
    background: #1a73e8;
    border-color: #1a73e8;
    box-shadow: 0 5px 14px rgba(26, 115, 232, .25);
  }
  .cgv-float-widget {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 99999;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 12px 6px 8px;
    background: rgba(18, 20, 29, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 40px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35), 0 0 20px rgba(66, 133, 244, 0.25);
    cursor: pointer;
    transition: transform 0.22s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.22s ease, background 0.22s ease;
    user-select: none;
  }
  .cgv-float-widget:hover {
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 16px 44px rgba(0, 0, 0, 0.45), 0 0 28px rgba(66, 133, 244, 0.4);
    border-color: rgba(255, 255, 255, 0.28);
  }
  .cgv-float-orb-wrap {
    position: relative;
    width: 48px;
    height: 48px;
    display: grid;
    place-items: center;
    border-radius: 50%;
  }
  .cgv-float-orb-glow {
    position: absolute;
    inset: -6px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(94, 162, 255, 0.65), rgba(162, 89, 255, 0.35) 60%, transparent 80%);
    filter: blur(8px);
    animation: cgvPulse 2.4s ease-in-out infinite alternate;
  }
  @keyframes cgvPulse {
    0% { transform: scale(0.92); opacity: 0.6; }
    100% { transform: scale(1.12); opacity: 1; }
  }
  #cgvFloatOrbCanvas {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    position: relative;
    z-index: 2;
  }
  .cgv-float-controls {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.1);
    padding: 4px;
    border-radius: 30px;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
  .cgv-float-btn-icon {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.9);
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .cgv-float-btn-icon:hover {
    background: rgba(255, 255, 255, 0.22);
    color: #fff;
    transform: scale(1.08);
  }
  .cgv-float-btn-icon.active {
    background: #1a73e8;
    color: #fff;
    box-shadow: 0 2px 8px rgba(26, 115, 232, 0.45);
  }
  :root[data-theme="dark"] .cgv-overlay { box-shadow: 0 20px 48px rgba(0, 0, 0, .30); }
  :root[data-theme="dark"] .cgv-dot { background: #5bb974; box-shadow: 0 0 0 4px rgba(91, 185, 116, .12); }
  @media (max-width: 580px) {
    .cgv-overlay { padding: 14px; border-radius: 18px; }
    .cgv-overlay.active { grid-template-columns: 1fr; grid-template-areas: "top" "main" "controls"; }
    .cgv-topbar { flex-wrap: wrap; }
    #cgvVoiceSelect { max-width: calc(100% - 42px); }
    .cgv-center { grid-template-columns: 94px minmax(0, 1fr); gap: 11px; }
    .cgv-orb-wrapper { width: 90px; height: 90px; }
    #cgvOrbCanvas { width: 86px; height: 86px; }
    .cgv-controls { flex-direction: row; padding: 12px 0 0; border-left: 0; border-top: 1px solid var(--border); }
  }

  /* Voice paytida chat oqimida faqat Linda orb ko'rinadi. */
  .cgv-overlay {
    width: 100%;
    margin: 12px auto 4px;
    padding: 0;
    min-height: 0;
    background: transparent !important;
    border: 0 !important;
    border-radius: 0;
    box-shadow: none !important;
  }
  .cgv-overlay.active {
    display: block;
    padding: 0 !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    animation: cgvOrbIn .2s var(--ease) both;
  }
  @keyframes cgvOrbIn {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
  }
  /* Ilgari bu yerda hammasi display:none edi — shuning uchun gapirayotgan
     matn ham, tanlagichlar ham ko'rinmasdi. Endi sfera ostida ixcham
     ustun: holat, jonli matn, boshqaruv va sozlamalar. */
  .cgv-topbar { display: none !important; }
  .cgv-status {
    display: block !important;
    margin-top: 9px; text-align: center;
    font-size: 12.5px; font-weight: 650; color: var(--muted);
  }
  .cgv-transcript {
    display: -webkit-box !important;
    -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
    max-width: 620px; margin: 6px auto 0; padding: 0 12px;
    text-align: center; font-size: 15px; line-height: 1.5;
    color: var(--ink); min-height: 23px;
  }
  .cgv-controls {
    display: flex !important;
    flex-direction: row !important; gap: 10px;
    justify-content: center; align-items: center; margin-top: 11px;
  }
  .cgv-tune {
    display: flex; flex-wrap: wrap; gap: 8px;
    justify-content: center; margin-top: 12px;
  }
  .cgv-tune select {
    background: rgba(255,255,255,.07); color: var(--ink);
    border: 1px solid rgba(255,255,255,.16); border-radius: 999px;
    padding: 5px 11px; font-size: 11.5px; max-width: 190px; cursor: pointer;
    backdrop-filter: blur(6px);
  }
  .cgv-tune select:hover { border-color: rgba(120,150,255,.55); }
  .cgv-tune select option { background: #1b1f27; color: #e6e8ee; }
  .cgv-tune-note { width: 100%; text-align: center; font-size: 10.5px;
    color: var(--muted); margin-top: 3px; }
  .cgv-center {
    display: flex;
    flex-direction: column;
    width: 100%;
    align-items: center;
    justify-content: center;
    min-width: 0;
  }
  .cgv-orb-wrapper { width: 142px; height: 142px; }
  #cgvOrbCanvas { width: 138px; height: 138px; }
  @media (max-width: 580px) {
    .cgv-orb-wrapper { width: 118px; height: 118px; }
    #cgvOrbCanvas { width: 114px; height: 114px; }
  }

  /* ══ MOBILE ULTRA-PROFESSIONAL RESPONSIVE DESIGN SYSTEM ══════════════ */
  .mobile-nav-toggle-btn {
    display: none;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--field);
    color: var(--text);
    padding: 0;
    cursor: pointer;
    transition: all 0.2s var(--ease);
    margin-right: 4px;
    flex-shrink: 0;
  }
  .mobile-nav-toggle-btn:active {
    transform: scale(0.92);
    background: var(--field-hover);
  }

  @media (max-width: 768px) {
    /* Prevent iOS Safari input auto-zoom */
    input[type=text], textarea, select {
      font-size: 16px !important;
    }

    body {
      height: 100dvh;
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
    }

    .mobile-nav-toggle-btn {
      display: inline-flex;
    }

    /* Mobile Header Layout */
    .clean-nav-header {
      min-height: 54px;
      padding: 0 10px;
      gap: 6px;
      grid-template-columns: auto 1fr auto;
      border-bottom: 1px solid var(--border);
      background: color-mix(in srgb, var(--panel-solid) 94%, transparent);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
    }
    .clean-nav-brand {
      font-size: 16px;
      font-weight: 700;
      gap: 5px;
    }
    .clean-nav-brand .logomark {
      width: 26px;
      height: 26px;
    }
    .clean-nav-menus {
      height: 54px;
      gap: 2px;
      justify-content: flex-end;
    }
    .clean-nav-trigger {
      min-height: 54px;
      padding: 0 7px;
      font-size: 13px;
      font-weight: 600;
    }
    .clean-nav-trigger svg {
      width: 13px;
      height: 13px;
    }
    .clean-nav-dropdown {
      position: fixed;
      top: 56px;
      left: 8px;
      right: 8px;
      width: calc(100vw - 16px) !important;
      max-width: 360px;
      margin: 0 auto;
      transform: none !important;
      border-radius: 18px;
      padding: 6px;
      box-shadow: 0 16px 48px rgba(0,0,0,0.38);
      z-index: 999;
    }

    /* Mobile Container & Wrap */
    main {
      padding: 0 6px;
    }
    .wrap {
      max-width: 100%;
    }

    /* Completely hide ChatGPT Voice panel/button & top Hisob Holati summary cards on mobile */
    #cgptVoiceBtn, #cgptPanel, .cgpt-panel, .cgv-overlay, #cgvOverlay {
      display: none !important;
    }

    /* Hisob chizig'i telefonda ham kerak — kassa va qarzlar asosiy narsa.
       Ilgari u butunlay yashirilardi, chunki panel ikki qatorli va baland
       edi. Endi u bitta ingichka qator, shuning uchun yon tomonga suriladi. */
    .hisob-bar {
      margin-bottom: 6px;
      padding: 4px;
      border-radius: 12px;
    }
    .hisob-cells {
      overflow-x: auto;
      scrollbar-width: none;
      -webkit-overflow-scrolling: touch;
    }
    .hisob-cells::-webkit-scrollbar { display: none; }
    .hisob-cell {
      flex: 0 0 auto;
      min-width: 84px;
      padding: 5px 11px;
      scroll-snap-align: start;
    }
    .hisob-cell .hc-value { font-size: 14.5px; }

    /* ☰ tugmasi Explorer'ni ochadi va unda "Yangi suhbat" bor — shuning
       uchun bu ikki belgi telefonda takror bo'lib qoladi. */
    #newChat, #toggleSidebar { display: none !important; }

    /* Welcome Hero & Quick Action Cards on Mobile */
    #welcomeBox .hero {
      padding: 14px 10px 8px;
      text-align: center;
    }
    #welcomeBox .hero-title {
      font-size: 18px;
    }
    #welcomeBox .hero-sub {
      font-size: 12.5px;
      line-height: 1.45;
    }
    .quick-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      padding: 2px;
    }
    .quick-card {
      padding: 12px 10px;
      border-radius: 14px;
      gap: 3px;
    }
    .quick-card:active {
      transform: scale(0.96);
      background: var(--field-hover);
    }
    .quick-card .q-icon {
      font-size: 20px;
    }
    .quick-card .q-title {
      font-size: 12.5px;
      font-weight: 700;
    }
    .quick-card .q-desc {
      font-size: 10.5px;
      line-height: 1.3;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    /* Chat Messages & Bubbles on Mobile */
    #chatArea {
      padding: 2px;
      gap: 12px !important;
    }
    .msg {
      gap: 8px;
    }
    .av {
      width: 30px;
      height: 30px;
      flex: 0 0 30px;
      font-size: 12px;
    }
    .bubble {
      padding: 10px 14px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      max-width: 96%;
    }
    .code-block {
      margin: 8px 0;
      border-radius: 10px;
    }
    .code-block pre {
      padding: 10px;
      font-size: 11.5px;
    }

    /* Bottom Input Card on Mobile - Ultra Compact & Sleek Capsule */
    footer {
      padding: 3px 6px max(6px, env(safe-area-inset-bottom));
      background: color-mix(in srgb, var(--bg) 95%, transparent) !important;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
    }

    footer .hint {
      display: none !important;
    }

    .ag-workspace-selector {
      font-size: 11px;
      margin-bottom: 2px;
      gap: 4px;
    }

    .ag-input-card {
      position: relative;
      padding: 8px 10px 6px;
      border-radius: 16px;
      border: 1px solid var(--border);
      background-clip: padding-box;
      background: var(--panel-solid);
      box-shadow: 0 1px 3px rgba(0,0,0,.14), 0 8px 24px rgba(0,0,0,.10);
      transition: border-color .2s var(--ease);
    }
    .ag-input-card::before { border-radius: 17px; }

    #input {
      min-height: 28px;
      max-height: 90px;
      font-size: 16px !important; /* Stops iOS Safari auto-zoom */
      line-height: 1.35;
      padding: 2px 4px;
      color: var(--ink);
    }

    #input::placeholder {
      font-size: 13.5px;
      opacity: 0.65;
    }

    #cgptVoiceBtn {
      display: none !important;
    }

    /* Chiplar bitta qatorda qolib yon tomonga suriladi — ikkinchi qatorga
       tushib ketsa yuborish tugmasi ustiga chiqib qolardi. */
    .ag-input-footer-row {
      gap: 6px;
      align-items: center;
      flex-wrap: nowrap;
      margin-top: 4px;
    }
    .ag-input-left-tools { min-width: 0; }
    .ag-tool-btn, .ag-ws-btn { flex: 0 0 auto; min-height: 32px; }
    .ag-ws-btn { max-width: 130px; }
    .ag-send-circle-btn { width: 34px; height: 34px; }
    /* Barmoq uchun yetarli nishon: belgili tugmalar 38px dan kichik bo'lmasin */
    .hdr-icon { width: 38px; height: 38px; flex-basis: 38px; }
    .mobile-nav-toggle-btn { min-width: 38px; min-height: 38px; }

    .ag-input-left-tools {
      gap: 6px;
      flex: 1;
      min-width: 0;
      max-width: none;
      flex-wrap: nowrap;
      overflow-x: auto;
      white-space: nowrap;
      padding-bottom: 1px;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
      /* O'ng chekkasi mayin so'nadi — bu yerda yana chip borligini bildiradi,
         aks holda kesilgan tugma buzuq bo'lib ko'rinadi. */
      -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 22px), transparent);
      mask-image: linear-gradient(90deg, #000 calc(100% - 22px), transparent);
    }

    .ag-input-left-tools::-webkit-scrollbar {
      display: none;
    }

    .ag-tool-btn {
      padding: 2px 8px;
      font-size: 11px;
      min-height: 28px;
      border-radius: 999px;
      background: var(--field);
      border: 1px solid var(--border);
      color: var(--text);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      font-weight: 500;
    }

    .ag-tool-btn:active {
      transform: scale(0.92);
      background: var(--field-hover);
    }

    .ag-plus-btn, .voice-input-btn {
      width: 28px;
      height: 28px;
      padding: 0;
      border-radius: 50%;
      font-size: 13px;
    }

    .ag-send-circle-btn {
      width: 30px;
      height: 30px;
      flex-shrink: 0;
      border-radius: 50%;
      background: linear-gradient(135deg, #1a73e8, #4285f4);
      color: #fff;
      border: none;
      box-shadow: 0 2px 8px rgba(26, 115, 232, 0.35);
      transition: transform 0.15s var(--ease);
    }

    .ag-send-circle-btn svg {
      width: 13px;
      height: 13px;
    }

    .ag-send-circle-btn:active {
      transform: scale(0.88);
    }

    /* Sidebar Mobile Drawer */
    #sidebar {
      width: min(310px, 86vw);
      border-radius: 0 20px 20px 0;
    }
    .sb-head {
      padding: 8px 6px 10px;
    }
    .sb-new-btn {
      min-height: 40px;
      font-size: 13.5px;
    }
    .sb-tab {
      min-height: 38px;
      font-size: 12.5px;
    }
  }

  @media (max-width: 480px) {
    .quick-grid {
      grid-template-columns: 1fr;
    }
    .hisob-cell {
      flex: 0 0 auto;
      min-width: 78px;
    }
    .ag-input-card {
      padding: 8px 10px 6px;
    }
  }
</style>
</head>
<body>
<div id="aurora"><i class="a1"></i><i class="a2"></i><i class="a3"></i><i class="a4"></i></div>
<div id="grid-veil"></div>
<canvas id="agCanvas"></canvas>
<div id="confetti"></div>
<div id="antigravity-bg" style="display:none;"></div>

<!-- Chat History & File Explorer Sidebar Drawer -->
<div id="sidebarOverlay"></div>
<div id="shareToast" class="share-toast"></div>
<div id="sidebar">
  <div class="sb-head">
    <div class="sb-title">
      <div class="sb-title-mark">✦</div>
      <div class="sb-title-copy">
        <strong>MUHASIB Explorer</strong>
        <small>Workspace navigator</small>
      </div>
    </div>
    <button class="sb-close" id="closeSidebar" title="Yopish">✕</button>
  </div>

  <button class="sb-new-btn" id="sbNewChatBtn">＋ Yangi suhbat</button>
  <div class="sb-section-label">Ish maydoni</div>
  <div class="sb-tabs">
    <button class="sb-tab active" data-tab="history">◷ <span>Suhbatlar</span></button>
    <button class="sb-tab" data-tab="files">▣ <span>Fayllar</span></button>
    <button class="sb-tab" data-tab="tools">⚙ <span>Sozlamalar</span></button>
  </div>
  <div class="sb-workspace-card">
    <b>Geminisdk loyihasi</b>
    <small>Agent shu workspace ichida ishlaydi</small>
  </div>
  
  <!-- Tab 1: History -->
  <div class="sb-tab-content active" id="tabHistory">
    <div class="sb-search-box">
      <input type="text" id="historySearch" placeholder="🔍 Suhbatlarni qidirish...">
    </div>
    <div class="history-list" id="historyList"></div>
  </div>

  <!-- Tab 2: Workspace Files -->
  <div class="sb-tab-content" id="tabFiles">
    <div class="sb-search-box" style="padding-top:10px">
      <input type="text" id="fileSearch" placeholder="🔍 Fayllarni qidirish...">
    </div>
    <div class="tree-list" id="fileTreeList">
      <div style="padding:16px;text-align:center;color:var(--muted);font-size:12.5px">Yuklanmoqda…</div>
    </div>
  </div>

  <!-- Tab 3: Tools & Config -->
  <div class="sb-tab-content" id="tabTools" style="padding:16px;overflow-y:auto">
    <!-- ══ ULANISHLAR: printer, TV, telefon, Telegram ══ -->
    <div class="fa-section ulanish-bolim" style="margin-bottom:12px">
      <h3>🔌 Ulanishlar</h3>
      <p class="ulanish-izoh">Qurilmalaringizni ulang — agent ularni suhbatning o‘zidan boshqaradi.</p>
      <div id="ulanishRoyxat" class="ulanish-royxat">
        <div class="ulanish-yuklanmoqda">Tekshirilmoqda…</div>
      </div>
      <button id="ulanishYangila" class="ghost ulanish-yangila" type="button">↻ Qayta tekshirish</button>
    </div>

    <div class="fa-section" style="margin-bottom:12px">
      <h3>🎞️ Gemini Veo Video</h3>
      <p style="font-size:12.5px;color:var(--muted)">Haqiqiy rasm→video uchun Google AI Studio API kalitingizni faqat shu kompyuterda saqlang.</p>
      <div id="geminiKeyStatus" class="video-config-status">Sozlama hali tekshirilmagan.</div>
      <label class="video-key-label" for="geminiApiKey">Gemini API key</label>
      <div class="video-key-row">
        <input id="geminiApiKey" class="video-key-input" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="AIza...">
        <button id="geminiKeyReveal" class="ghost" type="button" title="Kalitni ko'rsatish yoki yashirish">👁</button>
      </div>
      <div class="video-config-actions">
        <button id="geminiKeySave" class="video-config-save" type="button">Saqlash va tekshirish</button>
        <button id="geminiKeyClear" class="video-config-clear" type="button">Kalitni o‘chirish</button>
      </div>
      <p class="video-config-note">Kalit brauzerga qayta ko‘rsatilmaydi va faqat lokal <code>.env</code> faylida saqlanadi. <a href="https://aistudio.google.com/api-keys" target="_blank" rel="noopener">Google AI Studio’dan kalit olish ↗</a></p>
    </div>
    <div class="fa-section" style="margin-bottom:12px">
      <h3>🎙 Mikrofon (nutq → matn)</h3>
      <p style="font-size:12.5px;color:var(--muted)">Kalit mikrofonni matnga o‘girish uchun kerak. 8777 ovoz chiqarmaydi — gaplashish uchun yozuv qatoridagi <b>ChatGPT ovozi</b> tugmasidan foydalaning.</p>
      <div id="voiceKeyStatus" class="video-config-status">Sozlama tayyor.</div>

      <!-- Ovoz tanlash, "Tinglash" va Auto-Speak olib tashlandi:
           8777 da endi ovoz CHIQARILMAYDI. Mikrofon faqat nutqni matnga
           o'giradi (🎙 tugmasi). Gaplashish uchun "ChatGPT ovozi" tugmasi. -->

      <label class="video-key-label" for="openaiApiKey" style="margin-top:10px;display:block;font-size:12.5px">OpenAI API Key (ChatGPT ovozlari va Live Voice uchun)</label>
      <div class="video-key-row">
        <input id="openaiApiKey" class="video-key-input" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="sk-...">
        <button id="openaiKeyReveal" class="ghost" type="button" title="Kalitni ko‘rsatish yoki yashirish">👁</button>
      </div>
      <div class="video-config-actions" style="margin-top:8px">
        <button id="openaiKeySave" class="video-config-save" type="button">Saqlash</button>
        <button id="openaiKeyClear" class="video-config-clear" type="button">Kalitni o‘chirish</button>
      </div>
      <p class="video-config-note">O‘zbekcha Sardor va Madina ovozlari har doim ishlaydi. OpenAI kaliti bilan Live Voice real vaqt rejimida gapni eshitadi, sukutdan keyin javob beradi va yangi gap bilan javobni to‘xtatadi. API foydalanishi alohida hisoblanadi.</p>
    </div>
    <div class="fa-section" style="margin-bottom:12px">
      <h3>🔓 Full Access Status</h3>
      <p style="font-size:12.5px;color:var(--muted)">Agent cheklovsiz avto-tasdiqlash rejimida ishlaydi.</p>
      <button id="sidebarFaBtn" class="full-access-btn" style="width:100%;margin-top:8px">Full Access sozlash</button>
    </div>
    <div class="fa-section">
      <h3>🤖 Aktiv Model</h3>
      <select id="sidebarModelSel" class="ag-model-select" style="width:100%;margin-top:8px;padding:8px 12px;border-radius:12px">
        <option value="">Standart Model</option>
      </select>
    </div>
    <div class="fa-section" style="margin-top:12px">
      <h3>🔗 Ulashilgan Sessiyalar</h3>
      <p style="font-size:12.5px;color:var(--muted)">Suhbat sessiyalarini ulashing — tanlasangiz ChatGPT Sol dek ishlaydi.</p>
      <div id="sharedSessionsList" class="shared-sessions-list">
        <div style="text-align:center;padding:12px;color:var(--muted);font-size:12.5px">Yuklanmoqda…</div>
      </div>
      <button id="refreshSharedBtn" type="button" style="width:100%;margin-top:8px;padding:8px 12px;border-radius:10px;background:var(--field);color:var(--text);border:1px solid var(--border);font-size:12.5px;cursor:pointer;transition:all 0.2s" title="Ulashilgan sessiyalar ro'yxatini yangilash">🔄 Yangilash</button>
    </div>
  </div>
</div>

<!-- Main Top Header -->
<header class="app-header clean-nav-header">
  <div class="clean-nav-brand">
    <button id="mobileNavToggle" class="mobile-nav-toggle-btn" type="button" onclick="toggleSidebar()" title="Menyu (Explorer)">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
    </button>
    <svg class="logomark" width="30" height="30" viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <path d="M20 5 L33 33 L27 33 L20 17 L13 33 L7 33 Z" fill="#4285f4"/>
      <path d="M20 5 L26 18 L14 18 Z" fill="#ea4335"/>
      <path d="M16 24 L24 24 L27 33 L13 33 Z" fill="#fbbc05"/>
      <path d="M20 17 L24 26 L16 26 Z" fill="#34a853"/>
    </svg>
    <span>Muhasib<b>Pro</b></span>
    <span class="port-badge clean-port-badge hidden" id="portBadge">Port 8777</span>
  </div>

  <!-- Markazda faqat bitta narsa: ish ketayotganini bildiruvchi indikator.
       Ish yo'q paytda sarlavha butunlay bo'sh qoladi. -->
  <div class="hdr-live">
    <button id="jobBadge" class="job-badge hidden" type="button" onclick="goToLiveJob()" title="Ish davom etmoqda"></button>
    <button id="jobStop" class="hdr-icon job-stop hidden" type="button" onclick="stopLive()" title="Ishni to'xtatish (Esc)">
      <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="1.5"/></svg>
    </button>
  </div>

  <nav class="hdr-actions" aria-label="Asosiy menyu">
    <button id="newChat" class="hdr-icon hidden" type="button" title="Yangi suhbat">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
    </button>
    <button id="brauzerBtn" class="hdr-icon" type="button" title="Brauzer — agent saytlarda ishlaydi">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18"/></svg>
    </button>
    <button id="toggleSidebar" class="hdr-icon" type="button" title="Explorer — fayllar va suhbatlar">
      <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg>
    </button>

    <div class="clean-nav-menu">
      <button class="clean-nav-trigger hdr-icon" type="button" aria-haspopup="true"
              aria-expanded="false" aria-controls="mainMenu" title="Boshqa amallar">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>
      </button>
      <div id="mainMenu" class="clean-nav-dropdown" role="menu">
        <button id="dashBtn" class="clean-nav-item" type="button" role="menuitem">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M4 19V5M4 19h16M8 16v-5m4 5V7m4 9v-3"/></svg></span>
          <span class="nav-copy"><b>Hisob daftari</b><small>Kassa, ombor, qarzlar va yozuvlar</small></span>
        </button>
        <button id="desktopLiveBtn" class="clean-nav-item" type="button" role="menuitem">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/></svg></span>
          <span class="nav-copy"><b>Desktop Live</b><small>Mac ekranini jonli ko‘rish</small></span>
        </button>
        <button id="cmdPaletteBtn" class="clean-nav-item" type="button" role="menuitem">
          <span class="nav-icon nav-icon-command">⌘</span>
          <span class="nav-copy"><b>Buyruqlar</b><small>Tezkor buyruqlar palitrasi</small></span>
        </button>
        <div class="clean-nav-divider" role="separator"></div>
        <button id="fullAccessBtn" class="clean-nav-item full-access-btn" type="button" role="menuitem">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 3 5 6v5c0 4.5 2.9 8.5 7 10 4.1-1.5 7-5.5 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></svg></span>
          <span class="nav-copy"><b>Full Access</b><small>Agent ruxsatlarini sozlash</small></span>
        </button>
        <button id="zeroGBtn" class="clean-nav-item" type="button" role="menuitem">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 2c.6 5.4 4.6 9.4 10 10-5.4.6-9.4 4.6-10 10-.6-5.4-4.6-9.4-10-10 5.4-.6 9.4-4.6 10-10Z"/></svg></span>
          <span class="nav-copy"><b>Zero-G</b><small>Vizual ish rejimi</small></span>
        </button>
        <button id="theme" class="clean-nav-item" type="button" role="menuitem">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M21 13.2A8.2 8.2 0 0 1 10.8 3 8.5 8.5 0 1 0 21 13.2Z"/></svg></span>
          <span class="nav-copy"><b>Mavzu</b><small>Dark yoki light ko‘rinish</small></span>
        </button>
      </div>
    </div>

    <div class="clean-nav-profile">
      <div class="prof hidden" id="prof"></div>
    </div>
  </nav>
</header>

<div id="desktopLiveModal" class="desktop-live-overlay hidden" role="dialog" aria-modal="true" aria-labelledby="desktopLiveTitle">
  <section class="desktop-live-window">
    <div class="desktop-live-head">
      <div class="desktop-live-mark">▣</div>
      <div class="desktop-live-title">
        <strong id="desktopLiveTitle">Desktop Live</strong>
        <small>Mac ekrani va agentning jonli ish oqimi</small>
      </div>
      <div id="desktopLiveStatus" class="desktop-live-status"><i></i><span>Tayyor</span></div>
      <button id="desktopLiveAuto" type="button" title="Keyingi agent ishlarida oynani avtomatik ochish">Avto: YOQ</button>
      <button id="desktopLiveRefresh" type="button" title="Ekranni hozir yangilash">↻ Yangilash</button>
      <button id="desktopLiveClose" class="desktop-live-close" type="button" title="Yopish">✕</button>
    </div>
    <div class="desktop-live-body">
      <div class="desktop-live-stage">
        <img id="desktopLiveFrame" alt="Mac desktopining jonli ko'rinishi">
        <div id="desktopLivePlaceholder" class="desktop-live-placeholder">
          <div class="desktop-glyph">▣</div>
          <strong>Desktop Live tayyorlanmoqda</strong>
          <p>Bu panel Mac ekranining jonli kadrlarini faqat <code>localhost:8777</code> ichida ko‘rsatadi. Rasm diskda saqlanmaydi.</p>
        </div>
        <div class="desktop-live-streaming"><i></i><span id="desktopLiveFrameLabel">Jonli kadr kutilmoqda</span></div>
      </div>
      <aside class="desktop-live-side">
        <div class="desktop-live-side-head"><strong>Agent faoliyati</strong><span id="desktopLiveActionCount">0 qadam</span></div>
        <div id="desktopLiveActions" class="desktop-live-actions"></div>
      </aside>
    </div>
    <div class="desktop-live-foot">
      <span>🔒 Ekran kadri faqat shu Mac’da ko‘rsatiladi va server uni saqlamaydi.</span>
      <code id="desktopLiveClock">--:--:--</code>
    </div>
  </section>
</div>

<!-- Jadval oynasi: agent Google Sheets bilan ishlaganda burchakda ochiladi.
     Modal emas — suhbat ko'rinib turadi va ish davom etaveradi. -->
<div id="jadvalPanel" class="jadval-panel hidden" role="complementary" aria-label="Jadval">
  <div class="jadval-bosh">
    <b id="jadvalSarlavha">Jadval</b>
    <a id="jadvalHavola" href="#" target="_blank" rel="noopener" class="asosiy">Sheets’da ochish ↗</a>
    <button id="jadvalYig" type="button" title="Yig‘ish yoki ochish">⌄</button>
    <button id="jadvalYop" type="button" title="Yopish">✕</button>
  </div>
  <div class="jadval-tana" id="jadvalTana"></div>
  <div class="jadval-foot" id="jadvalFoot"></div>
</div>

<div id="brauzerModal" class="desktop-live-overlay hidden" role="dialog" aria-modal="true" aria-labelledby="brauzerTitle">
  <section class="desktop-live-window">
    <div class="desktop-live-head">
      <div class="desktop-live-mark">◍</div>
      <div class="desktop-live-title">
        <strong id="brauzerTitle">Brauzer</strong>
        <small id="brauzerSarlavha">Agent ochgan sahifa shu yerda jonli ko‘rinadi</small>
      </div>
      <div id="brauzerStatus" class="desktop-live-status"><i></i><span>Tayyor</span></div>
      <button id="brauzerRefresh" type="button" title="Kadrni hozir yangilash">↻ Yangilash</button>
      <button id="brauzerClose" class="desktop-live-close" type="button" title="Yopish">✕</button>
    </div>
    <div class="brauzer-url">
      <input id="brauzerUrl" type="text" placeholder="Manzil yozing va Enter bosing — masalan google.com" spellcheck="false">
      <button id="brauzerGo" class="asosiy" type="button">Ochish</button>
      <button id="brauzerBack" type="button" title="Orqaga">‹ Orqaga</button>
    </div>
    <div class="desktop-live-body">
      <div class="desktop-live-stage">
        <img id="brauzerFrame" alt="Brauzer sahifasining jonli ko‘rinishi" tabindex="0">
        <div id="brauzerLogin" class="brauzer-login hidden">
          <div class="brauzer-login-ich">
            <b>🔐 Kirish kerak</b>
            <p id="brauzerLoginIzoh">Agent kutib turibdi.</p>
            <small>Shu oynaning o‘zida bosib, yozib kiring — agent parolingizni ko‘rmaydi.</small>
            <button id="brauzerDavom" type="button">Kirdim — davom et</button>
          </div>
        </div>
        <div id="brauzerPlaceholder" class="desktop-live-placeholder">
          <div class="desktop-glyph">◍</div>
          <strong>Brauzer hali ochilmagan</strong>
          <p>Yuqoridagi manzil qatoriga sayt yozing yoki agentga <b>“falon saytga kirib shuni qil”</b> deb ayting — Chrome ochiladi va bu yerda jonli ko‘rinadi.</p>
        </div>
        <div class="desktop-live-streaming"><i></i><span id="brauzerFrameLabel">Kadr kutilmoqda</span></div>
      </div>
      <aside class="desktop-live-side">
        <div class="desktop-live-side-head"><strong>Brauzer qadamlari</strong><span id="brauzerQadamSoni">0 qadam</span></div>
        <div id="brauzerQadamlar" class="desktop-live-actions"></div>
      </aside>
    </div>
    <div class="brauzer-eslatma">🔐 Bu haqiqiy Chrome oynasi va u o‘z profilida yuradi — bir marta kirgan saytingizda kirgan holda qolasiz. Parol yoki karta ma’lumotini agent yozmaydi: kerak bo‘lsa Chrome oynasining o‘zida siz kiritasiz.</div>
  </section>
</div>

<!-- Code & Artifact Viewer Modal -->
<div id="codeViewerModal" class="fa-overlay hidden">
  <div class="fa-modal" style="width:min(940px, 94vw); height:84vh;">
    <div class="fa-header">
      <div class="fa-header-icon" style="background:linear-gradient(135deg, #4285f4, #a142f4);font-size:22px">📄</div>
      <div class="fa-header-text" style="flex:1;overflow:hidden">
        <h2 id="cvFileName" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">fayl.py</h2>
        <p id="cvFilePath" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted)"></p>
      </div>
      <button class="ghost" id="cvCopyBtn" style="padding:6px 14px;font-size:12.5px;margin-right:8px">📋 Nusxalash</button>
      <button class="fa-close" id="cvClose">✕</button>
    </div>
    <div class="fa-body" style="padding:0;flex:1;overflow:hidden">
      <pre style="margin:0;padding:20px;height:100%;overflow:auto;font-family:'JetBrains Mono',monospace;font-size:13.5px;line-height:1.65;background:var(--code-bg);color:var(--text)"><code id="cvCodeText"></code></pre>
    </div>
  </div>
</div>

<!-- Command Palette Modal -->
<div id="cmdPaletteModal" class="fa-overlay hidden">
  <div class="fa-modal" style="width:min(620px, 92vw); max-height:520px;">
    <div style="padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;background:var(--field)">
      <span style="font-size:18px;color:var(--user)">⚡</span>
      <input type="text" id="cmdInput" placeholder="Buyruq yoki amal yozing... (Esc yopish)" style="flex:1;border:none!important;background:transparent!important;font-size:15.5px;color:var(--ink);padding:0!important">
      <kbd style="font-size:11px;padding:3px 8px;border:1px solid var(--border);border-radius:6px;color:var(--muted);background:var(--panel-solid)">ESC</kbd>
    </div>
    <div id="cmdList" style="padding:10px;overflow-y:auto;max-height:420px;display:flex;flex-direction:column;gap:6px"></div>
  </div>
</div>

<!-- Lightbox Image Viewer Modal -->
<div id="lightboxModal" class="fa-overlay hidden" onclick="closeLightbox()">
  <img id="lightboxImg" src="" style="max-width:92vw;max-height:92vh;border-radius:18px;box-shadow:0 25px 70px rgba(0,0,0,0.65);object-fit:contain">
</div>

<!-- Full Access Modal -->
<div id="faModal" class="fa-overlay hidden">
  <div class="fa-modal">
    <div class="fa-header">
      <div class="fa-header-icon">🔓</div>
      <div class="fa-header-text">
        <h2>Ruxsatsiz Full Access Rejimi</h2>
        <p>Cloud Code / Codex uslubidagi filtirsiz rejim sozlamalari</p>
      </div>
      <button class="fa-close" id="faClose">✕</button>
    </div>
    <div class="fa-body">

      <div class="fa-section">
        <h3><span class="fa-icon" style="background:rgba(234,67,53,.15);color:#ea4335">⚡</span> Nima bu? <span class="fa-badge info">HUJJAT</span></h3>
        <p><strong>Full Access rejimi</strong> — bu Google Cloud Code, GitHub Codex va boshqa AI agentlarida mavjud bo'lgan <em>filtirsiz</em>, <em>cheklanmagan</em> ishlash rejimi. Bu rejimda agent barcha fayl operatsiyalari, terminal buyruqlari va tizim resurslariga <strong>to'liq ruxsat</strong> oladi.</p>
        <p>Odatda agent har bir fayl o'zgartirish yoki buyruq bajarishdan oldin <em>ruxsat so'raydi</em>. Full Access rejimida esa hamma narsa avtomatik tasdiqlanadi — xuddi <code>--dangerously-skip-permissions</code> bayrog'i bilan.</p>
      </div>

      <div class="fa-section">
        <h3><span class="fa-icon" style="background:rgba(66,133,244,.15);color:#4285f4">🛠️</span> Yoqish usullari <span class="fa-badge safe">3 USUL</span></h3>
        <p><strong>1-usul:</strong> Terminal orqali (eng oson):</p>
        <div class="fa-cmd"><button class="copy-btn" onclick="copyFA(this)">Nusxalash</button>agy -p "vazifa" --dangerously-skip-permissions</div>
        <p><strong>2-usul:</strong> Muhit o'zgaruvchisi bilan:</p>
        <div class="fa-cmd"><button class="copy-btn" onclick="copyFA(this)">Nusxalash</button>export AGY_SKIP_PERMISSIONS=1
agy -p "vazifa"</div>
        <p><strong>3-usul:</strong> Sozlama faylida doimiy yoqish:</p>
        <div class="fa-cmd"><button class="copy-btn" onclick="copyFA(this)">Nusxalash</button># ~/.gemini/settings.json
{
  "permissions": {
    "skip_all": true,
    "auto_approve_reads": true,
    "auto_approve_writes": true,
    "auto_approve_commands": true
  }
}</div>
      </div>

      <div class="fa-section">
        <h3><span class="fa-icon" style="background:rgba(251,188,5,.15);color:#fbbc05">🔑</span> Cloud Code rejimi <span class="fa-badge info">GOOGLE</span></h3>
        <p>Google Cloud Code da AI agent quyidagi ruxsatlarga ega bo'ladi:</p>
        <ul>
          <li>📂 <strong>Fayl tizimi</strong> — barcha fayllarni o'qish, yozish, o'chirish</li>
          <li>💻 <strong>Terminal</strong> — ixtiyoriy buyruqlarni bajarish (pip, npm, git, docker...)</li>
          <li>🌐 <strong>Tarmoq</strong> — API so'rovlari, yuklab olish, web scraping</li>
          <li>🔧 <strong>Tizim</strong> — muhit o'zgaruvchilari, xizmatlar, portlar boshqaruvi</li>
          <li>📦 <strong>Paketlar</strong> — kutubxonalar o'rnatish va yangilash</li>
        </ul>
      </div>

      <div class="fa-section">
        <h3><span class="fa-icon" style="background:rgba(52,168,83,.15);color:#34a853">🎯</span> Codex rejimi <span class="fa-badge info">GITHUB</span></h3>
        <p>GitHub Codex (va Copilot Workspace) da filtirsiz rejim:</p>
        <ul>
          <li>🔀 <strong>Git operatsiyalari</strong> — commit, push, branch, merge avtomatik</li>
          <li>🧪 <strong>Test</strong> — testlarni yozish va bajarish cheklovsiz</li>
          <li>🏗️ <strong>Build</strong> — loyihani qurish, deploy qilish</li>
          <li>📝 <strong>Refactoring</strong> — katta hajmdagi kod o'zgartirishlari</li>
        </ul>
      </div>

      <div class="fa-section">
        <h3><span class="fa-icon" style="background:rgba(161,66,244,.15);color:#a142f4">⚙️</span> Tezkor sozlamalar</h3>
        <div class="fa-toggle-row">
          <span>🔓 Fayllarni avtomatik tasdiqlash</span>
          <label class="fa-toggle"><input type="checkbox" id="faAutoFiles" checked><span class="slider"></span></label>
        </div>
        <div class="fa-toggle-row">
          <span>💻 Buyruqlarni avtomatik bajarish</span>
          <label class="fa-toggle"><input type="checkbox" id="faAutoCmd" checked><span class="slider"></span></label>
        </div>
        <div class="fa-toggle-row">
          <span>🌐 Tarmoq so'rovlarini ruxsat etish</span>
          <label class="fa-toggle"><input type="checkbox" id="faAutoNet"><span class="slider"></span></label>
        </div>
        <div class="fa-toggle-row">
          <span>🗑️ O'chirish operatsiyalariga ruxsat</span>
          <label class="fa-toggle"><input type="checkbox" id="faAutoDelete"><span class="slider"></span></label>
        </div>
      </div>

      <div class="fa-section" style="border-color:rgba(234,67,53,.3)">
        <h3><span class="fa-icon" style="background:rgba(234,67,53,.15);color:#ea4335">⚠️</span> Ogohlantirish <span class="fa-badge danger">EHTIYOT</span></h3>
        <p>Full Access rejimida agent <strong>barcha buyruqlarni</strong> tasdiqlashsiz bajaradi. Bu qulaylik beradi, lekin:</p>
        <ul>
          <li>❌ Noto'g'ri buyruq tizimga zarar yetkazishi mumkin</li>
          <li>❌ Muhim fayllar o'chirilishi yoki qayta yozilishi mumkin</li>
          <li>❌ Xavfsizlik parollari yoki kalitlari ko'rinib qolishi mumkin</li>
        </ul>
        <p style="color:#fbbc05"><strong>Maslahat:</strong> Faqat ishonchli loyihalarda va muhim bo'lmagan muhitlarda foydalaning.</p>
      </div>

    </div>
    <div class="fa-footer">
      <button class="fa-cancel" id="faCancelBtn">Yopish</button>
      <button class="fa-apply" id="faApplyBtn">✅ Full Access yoqish</button>
    </div>
  </div>
</div>

<main><div class="wrap">
  <div id="loginCard" class="card hidden">
    <div class="hero">
      <div class="logo" style="margin-bottom:12px;"><svg width="48" height="48" viewBox="0 0 40 40"><path d="M20 5 L33 33 L27 33 L20 17 L13 33 L7 33 Z" fill="#4285f4"/><path d="M20 5 L26 18 L14 18 Z" fill="#ea4335"/><path d="M16 24 L24 24 L27 33 L13 33 Z" fill="#fbbc05"/><path d="M20 17 L24 26 L16 26 Z" fill="#34a853"/></svg></div>
      <h1 class="hero-title">Muhasib <em>Antigravity Studio</em></h1>
      <h2 style="font-size: clamp(24px, 3.8vw, 36px); font-weight: 700; margin: 8px 0 16px; color: var(--ink);">Bugun nima <em style="font-style: normal; background: linear-gradient(100deg, #1a73e8, #7c3aed 45%, #ea4335 75%, #fbbc05); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;">quramiz</em>?</h2>
      <p>Google akkaunt bilan kiring — API kaliti kerak emas. Interactive Anti-Gravity Workspace.</p>
    </div>
    <div id="loginStart" style="text-align:center">
      <button id="beginLogin" style="font-size:16px;padding:12px 28px">Kirishni boshlash 🚀</button>
      <p class="muted" style="margin-top:12px">Boshqa joyda ochiq <code>agy</code> bo'lsa avval uni yoping (Ctrl+C).</p>
    </div>
    <div id="loginFlow" class="hidden">
      <div class="step"><div class="num">1</div><div style="flex:1"><p>Google hisobingizga kiring va ruxsat bering:</p>
        <p><a id="authLink" class="btn" target="_blank" rel="noopener">🔓 Google hisobi bilan kirish</a></p></div></div>
      <div class="step"><div class="num">2</div><div style="flex:1"><p>Ochilgan sahifadagi <b>kodni</b> nusxalab, shu yerga joylang:</p>
        <div class="row"><input type="text" id="code" placeholder="Paste this code... (4/0AX...)"><button id="sendCode">Yuborish</button></div>
        <p class="muted">Kodsiz avtomatik o'tsa ham bo'ladi. Muammo bo'lsa — <button id="restartLogin" class="ghost" style="padding:4px 10px;font-size:12px">Qaytadan</button></p></div></div>
      <p id="loginMsg" class="muted"></p>
      <details><summary>Batafsil (agy chiqishi)</summary><pre class="term" id="term"></pre></details>
    </div>
  </div>

  <!-- Biznes ko'rsatkichlari — chatdan chiqmasdan doim ko'rinib turadi -->
  <div id="hisobBar" class="hisob-bar hidden">
    <div class="hisob-head">
      <span class="hisob-title">Hisob holati</span>
      <span class="hisob-brief" id="hisobBrief"></span>
    </div>
    <div class="hisob-cells" id="hisobCells">
    <button class="hisob-cell" type="button" data-bolim="kassa" title="Kassadagi naqd pul">
      <span class="hc-label">Kassa</span><b class="hc-value" id="hbKassa">—</b><span class="hc-extra" id="hbKassaExtra"></span><span class="hc-sub" id="hbKassaSub"></span>
    </button>
    <button class="hisob-cell" type="button" data-bolim="ombor" title="Ombordagi tovarlar">
      <span class="hc-label">Ombor</span><b class="hc-value" id="hbOmbor">—</b><span class="hc-sub" id="hbOmborSub"></span>
    </button>
    <button class="hisob-cell" type="button" data-bolim="qarzdorlar" title="Menga qarzdor odamlar">
      <span class="hc-label">Qarzdorlar</span><b class="hc-value" id="hbQarzdor">—</b><span class="hc-sub" id="hbQarzdorSub"></span>
    </button>
    <button class="hisob-cell" type="button" data-bolim="qarzlarim" title="Men qarzdor bo'lgan odamlar">
      <span class="hc-label">Qarzlarim</span><b class="hc-value" id="hbQarzim">—</b><span class="hc-sub" id="hbQarzimSub"></span>
    </button>
    <button class="hisob-cell" type="button" data-bolim="foyda" title="Sof foyda / zarar">
      <span class="hc-label">Foyda</span><b class="hc-value" id="hbFoyda">—</b><span class="hc-sub" id="hbFoydaSub"></span>
    </button>
    <button class="hisob-cell" type="button" data-bolim="amallar" title="Oxirgi yozuvlar" style="flex:0 0 auto;min-width:auto">
      <span class="hc-label">Tarix</span><b class="hc-value" id="hbAmallar">—</b>
    </button>
    </div>
  </div>
  <div id="hisobDetail" class="hisob-detail hidden"></div>

  <!-- Bo'sh holat. Mahsulot nomi sarlavhada allaqachon turibdi, shuning uchun
       bu yerda bitta savol va to'rtta boshlang'ich yo'l qoladi. -->
  <div id="welcomeBox" class="hidden">
    <div class="bosh-brend">
      <svg viewBox="0 0 40 40" aria-hidden="true">
        <path d="M20 5 L33 33 L27 33 L20 17 L13 33 L7 33 Z" fill="#4285f4"/>
        <path d="M20 5 L26 18 L14 18 Z" fill="#ea4335"/>
        <path d="M16 24 L24 24 L27 33 L13 33 Z" fill="#fbbc05"/>
        <path d="M20 17 L24 26 L16 26 Z" fill="#34a853"/>
      </svg>
      <span>Muhasib<b>Pro</b></span>
    </div>
    <div class="quick-grid">
      <button type="button" class="quick-card" onclick="useQuickPrompt('Alisherga 200 ming qarz berdim')">
        <span class="q-title">Qarz yozib qo'yish</span>
        <span class="q-desc">Kim, qancha — daftarga o'zi tushadi</span>
      </button>
      <button type="button" class="quick-card" onclick="useQuickPrompt('Sardordan 10 kg un qarzga oldim, kilosi 8 ming')">
        <span class="q-title">Tovar kirimi</span>
        <span class="q-desc">Naqtga yoki qarzga olganingizni ayting</span>
      </button>
      <button type="button" class="quick-card" onclick="useQuickPrompt('🔎 Shu papkadagi fayllarni skanerlab, loyiha tuzilishini tushuntirib ber')">
        <span class="q-title">Loyihani tahlil qilish</span>
        <span class="q-desc">Fayllar, tuzilma va arxitektura</span>
      </button>
      <button type="button" class="quick-card" onclick="useQuickPrompt('🎬 Avvalgi MP4 fayllarni ko‘rsatma: loyihada Uzbek Neural ovozi bilan yangi, alohida nomli video reklama rolik tayyorla')">
        <span class="q-title">Reklama roligi</span>
        <span class="q-desc">video/ quvuri orqali yangi multik</span>
      </button>
    </div>
  </div>

  <div id="chatArea" class="hidden" style="flex-direction:column;gap:18px"></div>
</div></main>

<div id="picker" class="hidden" style="position:fixed;inset:0;z-index:120;background:rgba(10,15,28,.42);display:grid;place-items:center;backdrop-filter:blur(14px) saturate(140%)">
  <div class="card" style="width:min(580px,92vw);max-height:80vh;display:flex;flex-direction:column;gap:12px">
    <div style="display:flex;gap:8px;align-items:center"><b style="flex:1;font-size:17px;color:var(--ink)">Papka tanlash</b><button id="pkClose" class="ghost" style="padding:4px 12px">✕</button></div>
    <div id="pkPath" class="muted" style="word-break:break-all;font-size:12px"></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button id="pkUp" class="ghost">⬆️ Yuqoriga</button>
      <button id="pkMkdirBtn" class="ghost" style="color:var(--primary,#4f46e5)">➕ Yangi papka</button>
      <button id="pkPick" style="flex:1">✓ Shu papkani tanlash</button>
    </div>
    <div id="pkMkdirBox" class="hidden" style="display:flex;gap:8px;align-items:center;background:var(--card-bg,#fff);padding:8px;border-radius:10px;border:1px solid var(--border)">
      <input type="text" id="pkNewName" placeholder="Yangi papka nomi..." style="flex:1;padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--ink);font-size:13px;outline:none">
      <button id="pkMkdirConfirm" style="padding:8px 14px;font-size:13px">Yaratish</button>
      <button id="pkMkdirCancel" class="ghost" style="padding:8px 10px;font-size:13px">✕</button>
    </div>
    <div id="pkList" style="overflow-y:auto;border:1px solid var(--border);border-radius:12px;padding:6px"></div>
  </div>
</div>

<footer class="hidden" id="foot">
  <div id="imgPreviewBar" class="img-preview-bar hidden">
    <img id="imgPreview" src="" alt="preview">
    <button id="removeImg" class="remove-btn" title="O'chirish">✕</button>
    <span style="font-size:12px;color:var(--muted)">Rasm biriktirildi</span>
  </div>

  <div class="ag-input-card">
    <textarea id="input" rows="1" placeholder="Savol yoki vazifa yozing..."></textarea>
    <div class="ag-input-footer-row">
      <div class="ag-input-left-tools">
        <input type="file" id="fileInput" accept="image/*" style="display:none">
        <button id="attachBtn" class="ag-tool-btn ag-plus-btn" title="Rasm biriktirish">+</button>
        <button id="voiceInputBtn" class="ag-tool-btn voice-input-btn" type="button" title="Mikrofondan gapiring">🎙</button>
        <button id="cgptVoiceBtn" class="ag-tool-btn" type="button"
                title="ChatGPT ovozi bilan gaplashish — daftaringizdagi raqamlarni bilib turadi">Ovoz</button>

        <div class="ag-model-select-wrap">
          <select id="modelSel" class="ag-model-select" title="AI agentini tanlang">
            <option value="">Composer Auto</option>
          </select>
          <span class="ag-model-chevron">˅</span>
        </div>

        <!-- Ish papkasi — ilgari kompozitor tepasida alohida qator bo'lib
             suzib turardi. Endi u ham shu qatordagi oddiy tanlagich. -->
        <div class="ag-workspace-selector">
          <button type="button" class="ag-ws-btn hidden" id="folderBox" title="Agent shu papkada ishlaydi">
            <svg class="ag-ws-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>
            <span id="folderNameDisplay">Folder</span>
          </button>
          <input type="text" id="folder" class="hidden" placeholder="/papka/yoli">
          <button id="pickBtn" class="hidden"></button>
        </div>
      </div>

      <button id="send" class="ag-send-circle-btn" title="Yuborish">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="5" y1="12" x2="19" y2="12"></line>
          <polyline points="12 5 19 12 12 19"></polyline>
        </svg>
      </button>
    </div>
  </div>

</footer>

<!-- ══ ChatGPT ovozi (8779 ko'prigi) ══════════════════════════════════════
     8777 ning O'Z ovozli rejimi (Realtime sfera, suzuvchi tugma, ovoz
     tanlagichlari) olib tashlandi. Bu yerda faqat ko'prikdan kelgan jonli
     matn ko'rsatiladi — gapirish va eshitish ChatGPT tomonida. -->
<style>
  /* Ovoz ko'prigi paneli. Ilgari bu blokda `display:none` dan keyin yana
     `display:flex` yozilgani uchun panel hech qachon yashirinmasdi va
     ekran burchagida bo'sh quti bo'lib turardi. */
  .cgpt-panel{display:none;position:fixed;right:18px;bottom:18px;z-index:60;
    width:360px;max-width:calc(100vw - 36px);max-height:calc(100vh - 40px);
    flex-direction:column;
    background:rgba(20,23,30,.94);border:1px solid rgba(255,255,255,.12);
    border-radius:14px;padding:12px 14px;backdrop-filter:blur(14px);
    box-shadow:0 14px 44px rgba(0,0,0,.45);font-size:13px;color:#e6e8ee}
  .cgpt-panel.on{display:flex}
  .cgpt-head{display:flex;align-items:center;gap:8px;margin-bottom:7px}
  .cgpt-head span:nth-child(2){flex:1;font-weight:650;font-size:12px;color:#9aa3b2}
  .cgpt-head button{background:transparent;border:0;color:#8b93a2;cursor:pointer;
    font-size:14px;padding:0 3px}
  .cgpt-head button:hover{color:#fff}
  .cgpt-dot{width:8px;height:8px;border-radius:50%;background:#4a5160;flex:0 0 auto}
  .cgpt-dot.live{background:#3fb950;box-shadow:0 0 8px #3fb950;
    animation:cgptBlink 1.4s infinite}
  @keyframes cgptBlink{0%,100%{opacity:1}50%{opacity:.4}}


  /* ══ DASHBOARD ═══════════════════════════════════════════════════════ */
  #dashOverlay{display:none;position:fixed;inset:0;z-index:80;
    background:var(--bg-soft);
    backdrop-filter:blur(14px);overflow-y:auto;padding:26px 18px}
  #dashOverlay.on{display:block;animation:dashIn .22s var(--ease) both}
  @keyframes dashIn{from{opacity:0}to{opacity:1}}
  .dash-shell{max-width:1060px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
  .dash-head{display:flex;align-items:center;gap:12px;padding:4px 2px}
  .dash-head b{font-size:17px;letter-spacing:-.01em}
  .dash-sub{flex:1;font-size:12px;color:var(--muted)}
  .dash-head button{border:1px solid var(--border);background:var(--field);
    color:var(--muted);border-radius:10px;width:34px;height:34px;cursor:pointer;
    font-size:14px;transition:all .15s var(--ease)}
  .dash-head button:hover{background:var(--field-hover);color:var(--text)}
  .dash-cards{display:flex;flex-wrap:wrap;gap:10px}
  .dash-card{flex:1 1 150px;min-width:140px;padding:12px 14px;border-radius:13px;
    border:1px solid var(--border);background:var(--panel-solid);cursor:pointer;
    box-shadow:var(--card-shadow);text-align:left;font-family:inherit;color:var(--text);
    display:flex;flex-direction:column;align-items:flex-start;gap:2px;
    transition:transform .16s var(--ease),box-shadow .16s var(--ease),border-color .16s var(--ease)}
  .dash-card>div{width:100%}
  .dash-card:hover{transform:translateY(-2px);box-shadow:var(--card-shadow-lift);
    border-color:var(--border-hover)}
  .dash-card.faol{border-color:var(--border-hover);box-shadow:var(--card-shadow-lift)}
  .dash-card .dc-l{font-size:10px;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:var(--muted)}
  .dash-card .dc-v{margin-top:3px;font-size:17px;font-weight:750;
    font-variant-numeric:tabular-nums;color:var(--ink)}
  .dash-card .dc-s{font-size:10.5px;color:var(--muted);margin-top:1px}
  .dash-card.yashil .dc-v{color:var(--accent)}
  .dash-card.qizil .dc-v{color:#d93025}
  :root[data-theme=dark] .dash-card.qizil .dc-v{color:#f87171}
  .dash-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  @media(max-width:860px){.dash-grid{grid-template-columns:1fr}}
  .dash-box{border:1px solid var(--border);border-radius:14px;padding:13px 15px;
    background:var(--panel-solid);box-shadow:var(--card-shadow)}
  .dash-box h4{margin:0 0 9px;font-size:11px;font-weight:700;letter-spacing:.06em;
    text-transform:uppercase;color:var(--muted);display:flex;align-items:center;gap:8px}
  .dash-note{font-weight:500;text-transform:none;letter-spacing:0;font-size:10.5px}
  .dash-chart{width:100%;min-height:170px}
  .dash-chart svg{display:block;width:100%}
  .dash-vals{display:inline-flex;gap:5px}
  .dash-vals button{border:1px solid var(--border);background:var(--field);
    color:var(--muted);border-radius:999px;padding:2px 10px;font-size:10.5px;
    cursor:pointer;font-family:inherit;font-weight:650}
  .dash-vals button.on{background:var(--field-hover);color:var(--text);
    border-color:var(--border-hover)}
  .dash-jadval-orash{max-height:340px;overflow:auto;border-radius:10px}
  .dash-jadval{width:100%;border-collapse:collapse;font-size:12.5px}
  .dash-jadval th{position:sticky;top:0;background:var(--panel-solid);
    text-align:left;font-size:10px;letter-spacing:.07em;text-transform:uppercase;
    color:var(--muted);padding:7px 9px;border-bottom:1px solid var(--border)}
  .dash-jadval td{padding:7px 9px;border-bottom:1px solid var(--border);
    vertical-align:middle}
  .dash-jadval .son{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  .dash-jadval .musbat{color:var(--accent);font-weight:650}
  .dash-jadval .manfiy{color:#d93025;font-weight:650}
  :root[data-theme=dark] .dash-jadval .manfiy{color:#f87171}
  .dash-jadval .nol{color:var(--muted)}
  .dash-tur{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;
    border-radius:999px;font-size:10.5px;font-weight:700;letter-spacing:.4px;
    color:#fff;white-space:nowrap}
  .dash-muted{color:var(--muted);font-size:11px}


  .dash-model{margin-left:auto;border:1px solid var(--border);background:var(--field);
    color:var(--text);border-radius:999px;padding:4px 10px;font-size:11px;
    font-family:inherit;font-weight:600;outline:none;max-width:230px;cursor:pointer;
    text-transform:none;letter-spacing:0;transition:all .15s var(--ease)}
  .dash-model:hover{border-color:var(--border-hover)}


  /* karta bosilganda ochiladigan tafsilot */
  .dash-tafsilot{display:none}
  .dash-tafsilot.on{display:block;animation:dashTaf .2s var(--ease) both}
  @keyframes dashTaf{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
  .dash-taf-bosh{display:flex;align-items:center;gap:10px;margin-bottom:10px}
  .dash-taf-bosh b{font-size:13.5px}
  .dash-taf-bosh .yop{margin-left:auto;border:1px solid var(--border);
    background:var(--field);color:var(--muted);border-radius:8px;width:26px;height:26px;
    cursor:pointer;font-size:12px}
  .dash-taf-bosh .yop:hover{background:var(--field-hover);color:var(--text)}
  .dash-taf-jadval{width:100%;border-collapse:collapse;font-size:12.5px}
  .dash-taf-jadval th{text-align:left;font-size:10px;letter-spacing:.06em;
    text-transform:uppercase;color:var(--muted);padding:6px 8px;
    border-bottom:1px solid var(--border)}
  .dash-taf-jadval td{padding:8px;border-bottom:1px solid var(--border);vertical-align:middle}
  .dash-taf-jadval .son{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}


  /* ombor: lokatsiya chiplari */
  .lok-chiplar{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:11px}
  .lok-chip{display:inline-flex;align-items:center;gap:7px;padding:6px 13px;
    border-radius:999px;border:1px solid var(--border);background:var(--field);
    color:var(--muted);font-family:inherit;font-size:11.5px;font-weight:650;
    cursor:pointer;transition:all .15s var(--ease)}
  .lok-chip b{font-variant-numeric:tabular-nums;color:var(--text);font-weight:750}
  .lok-chip:hover{background:var(--field-hover);border-color:var(--border-hover)}
  .lok-chip.on{background:var(--user-bubble);border-color:var(--border-hover);
    color:var(--user-text)}
  .lok-chip.on b{color:var(--user-text)}

  .omb-nom{font-weight:650;font-size:13px}
  .lok-taqsim{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
  .lok-taqsim span{font-size:10.5px;color:var(--muted);padding:1px 8px;
    border-radius:999px;background:var(--field);border:1px solid var(--border)}
  .lok-taqsim b{color:var(--text);font-variant-numeric:tabular-nums}
  .omb-jadval tfoot td{border-bottom:0;border-top:2px solid var(--border);
    padding-top:10px;font-size:13px}


  /* tovar rasmi */
  .omb-rasm-td{width:1%;padding-right:0}
  .omb-rasm-btn{border:1px solid var(--border);background:var(--field);border-radius:10px;
    width:46px;height:46px;padding:0;cursor:pointer;overflow:hidden;display:grid;
    place-items:center;transition:all .15s var(--ease)}
  .omb-rasm-btn:hover{border-color:var(--border-hover);transform:scale(1.05)}
  .omb-rasm{width:100%;height:100%;object-fit:cover;display:block}
  .omb-rasm.yoq{display:grid;place-items:center;font-size:18px;opacity:.4;
    width:100%;height:100%}
  img.omb-rasm.yoq{display:none}

  /* barkodni kattalashtirish tugmasi */
  .bk-katta{border:0;background:transparent;padding:0;cursor:pointer;line-height:0;
    border-radius:5px;transition:transform .15s var(--ease)}
  .bk-katta:hover{transform:scale(1.06)}

  /* katta barkod oynasi */
  #bkKatta{position:fixed;inset:0;z-index:120;background:rgba(0,0,0,.55);
    backdrop-filter:blur(6px);display:grid;place-items:center;padding:20px;
    animation:dashTaf .18s var(--ease) both}
  .bk-katta-ich{background:#fff;border-radius:18px;padding:24px 28px;text-align:center;
    box-shadow:0 30px 80px rgba(0,0,0,.5);max-width:95vw}
  .bk-katta-nom{font-size:15px;font-weight:700;color:#111;margin-bottom:14px}
  .bk-katta-kod{font-family:ui-monospace,Menlo,monospace;font-size:14px;color:#333;
    letter-spacing:2px;margin-top:8px}
  .bk-katta-izoh{font-size:11px;color:#777;margin-top:10px}
  .bk-katta-tugma{display:flex;gap:8px;justify-content:center;margin-top:16px}
  .bk-katta-tugma button{border:1px solid #d0d0d0;background:#f5f5f5;color:#222;
    border-radius:9px;padding:8px 16px;font-size:12.5px;font-weight:650;cursor:pointer;
    font-family:inherit}
  .bk-katta-tugma button:hover{background:#eaeaea}
  @media print{ #bkKatta{position:static;background:#fff} .bk-katta-tugma{display:none} }

  /* barkod */
  .bk-hujayra{display:flex;align-items:center;gap:9px}
  .bk-svg{background:#fff;border-radius:5px;padding:3px 5px;flex:0 0 auto}
  .bk-raqam{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;
    color:var(--muted);letter-spacing:.4px}
  .bk-avto{font-size:9px;padding:1px 6px;border-radius:999px;background:var(--field);
    color:var(--muted);border:1px solid var(--border)}
  .bk-tahrir{border:1px solid var(--border);background:var(--field);color:var(--muted);
    border-radius:7px;width:24px;height:24px;cursor:pointer;font-size:11px}
  .bk-tahrir:hover{background:var(--field-hover);color:var(--text)}

  /* qidirish maydoni jadval sarlavhasida */
  .dash-qidir{margin-left:auto;border:1px solid var(--border);background:var(--field);
    color:var(--text);border-radius:999px;padding:4px 12px;font-size:11.5px;
    font-family:inherit;width:150px;outline:none;text-transform:none;letter-spacing:0;
    font-weight:500;transition:all .15s var(--ease)}
  .dash-qidir:focus{border-color:var(--border-hover);width:210px}

  /* Excel uslubidagi tanlov */
  .dash-jadval tbody tr{cursor:pointer}
  .dash-jadval tbody tr:hover{background:var(--field)}
  .dash-jadval tbody tr.tanlangan{background:var(--field-hover);
    box-shadow:inset 3px 0 0 var(--border-hover)}
  .dash-jadval tbody tr.yangi{animation:dashYangi 1.4s var(--ease)}
  @keyframes dashYangi{0%{background:var(--field-hover)}100%{background:transparent}}

  /* suhbat */
  .dash-suhbat{display:flex;flex-direction:column;gap:9px}
  #dashChat{display:flex;flex-direction:column;gap:8px;max-height:260px;overflow-y:auto;
    padding-right:3px}
  #dashChat:empty{display:none}
  .dmsg{padding:8px 13px;border-radius:13px;font-size:13px;line-height:1.55;
    max-width:82%;white-space:pre-wrap;word-break:break-word}
  .dmsg.u{align-self:flex-end;background:var(--user-bubble);
    border:1px solid var(--border);color:var(--user-text)}
  .dmsg.a{align-self:flex-start;background:var(--field);border:1px solid var(--border);
    color:var(--ink)}
  .dmsg.q{align-self:flex-start;background:rgba(251,191,36,.12);
    border:1px solid rgba(251,191,36,.35);color:var(--ink)}
  .dmsg.step{align-self:flex-start;background:transparent;border:0;padding:2px 4px;
    font-size:11.5px;color:var(--muted)}
  .dash-composer{display:flex;gap:8px;align-items:flex-end}
  .dash-composer textarea{flex:1;resize:none;border:1px solid var(--border);
    background:var(--field);color:var(--text);border-radius:13px;padding:10px 14px;
    font-family:inherit;font-size:13.5px;line-height:1.5;outline:none;max-height:120px;
    transition:border-color .15s var(--ease)}
  .dash-composer textarea:focus{border-color:var(--border-hover)}
  .dash-composer button{width:38px;height:38px;border-radius:50%;border:0;cursor:pointer;
    background:var(--border-hover);color:#fff;font-size:16px;font-weight:700;flex:0 0 auto;
    transition:filter .15s var(--ease)}
  .dash-composer button:hover:not(:disabled){filter:brightness(1.14)}
  .dash-composer button:disabled{background:var(--field);color:var(--muted);cursor:not-allowed}
  .dash-tez{display:flex;flex-wrap:wrap;gap:6px}
  .dash-tez button{border:1px dashed var(--border);background:transparent;color:var(--muted);
    border-radius:999px;padding:4px 11px;font-size:11px;cursor:pointer;font-family:inherit;
    transition:all .15s var(--ease)}
  .dash-tez button:hover{background:var(--field);color:var(--text);
    border-style:solid;border-color:var(--border-hover)}

  /* dashboard ichidagi chek biroz ixchamroq */
  #dashChat .chek{width:250px}
  #dashChat .chek-wrap{justify-content:flex-start;margin:4px 0}

  /* ══ CHEK — kassa cheki ko'rinishi ══════════════════════════════════ */
  .chek-wrap{display:flex;justify-content:center;margin:14px 0 6px;
    animation:chekIn .32s cubic-bezier(.2,.8,.3,1) both}
  @keyframes chekIn{from{opacity:0;transform:translateY(10px) scale(.97)}
                    to{opacity:1;transform:none}}
  .chek{width:300px;max-width:92%;filter:drop-shadow(0 12px 28px rgba(0,0,0,.4))}
  .chek-top,.chek-bot{height:9px;background:#f7f5ef}
  .chek-top{-webkit-mask:radial-gradient(6px 9px at 6px 0,transparent 98%,#000) repeat-x;
            mask:radial-gradient(6px 9px at 6px 0,transparent 98%,#000) repeat-x;
            -webkit-mask-size:12px 9px;mask-size:12px 9px}
  .chek-bot{-webkit-mask:radial-gradient(6px 9px at 6px 100%,transparent 98%,#000) repeat-x;
            mask:radial-gradient(6px 9px at 6px 100%,transparent 98%,#000) repeat-x;
            -webkit-mask-size:12px 9px;mask-size:12px 9px}
  .chek-body{background:#f7f5ef;color:#1a1a1a;padding:14px 18px 16px;
    border-top:3px solid var(--chek-rang,#111);
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
  .chek-brand{text-align:center;font-weight:800;letter-spacing:4px;font-size:13px}
  /* Sarlavha turga qarab rang oladi (--chek-rang) */
  .chek-kind{text-align:center;margin-top:6px;font-weight:800;font-size:14px;
    letter-spacing:1.2px;color:var(--chek-rang,#111);
    display:flex;align-items:center;justify-content:center;gap:7px}
  .chek-glyph{display:inline-flex;align-items:center;justify-content:center;
    width:19px;height:19px;border-radius:50%;background:var(--chek-rang,#111);
    color:#f7f5ef;font-size:12px;font-weight:900;line-height:1}
  .chek-tag{text-align:center;margin-top:4px;font-size:10px;letter-spacing:1.2px;
    color:#8a8578;text-transform:uppercase}
  .chek-meta{text-align:center;margin-top:5px;font-size:10.5px;color:#6b6b6b;line-height:1.5}
  .chek-cut{border-top:1px dashed #b9b4a7;margin:10px 0}
  .chek-row{display:flex;justify-content:space-between;gap:12px;padding:2.5px 0;
    font-size:11.5px;color:#3a3a3a}
  .chek-row b{font-weight:700;color:#111;text-align:right;word-break:break-word}
  .chek-row.strong{font-size:14px;padding:4px 0}
  .chek-row.strong span{font-weight:700;letter-spacing:1px}
  .chek-row.strong b{font-size:16px}
  .chek-pay{text-align:center;margin-top:9px}
  .chek-badge{display:inline-block;padding:3px 14px;border-radius:4px;
    font-size:10.5px;font-weight:800;letter-spacing:2px}
  .chek-badge.naqd{background:#1a7f4b;color:#fff}
  .chek-badge.qarz{background:#b4530f;color:#fff}
  .chek-after{text-align:center;font-size:10px;letter-spacing:2px;color:#8a8578;
    margin-bottom:5px}
  .chek-foot{text-align:center;margin-top:12px;font-size:10px;letter-spacing:1.5px;
    color:#8a8578}

  /* xato + tuzatish tugmasi */
  #cgptFix{display:none;margin-top:9px;padding:10px 11px;border-radius:10px;
    background:rgba(218,54,51,.12);border:1px solid rgba(218,54,51,.32)}
  #cgptFix.on{display:block}
  #cgptFixText{font-size:12px;line-height:1.5;color:#ffb3b0;margin-bottom:8px}
  #cgptFixBtn{width:100%;padding:8px 10px;border-radius:8px;border:0;cursor:pointer;
    background:#1f6feb;color:#fff;font-size:12.5px;font-weight:650}
  #cgptFixBtn:hover{filter:brightness(1.12)}
  #cgptFixBtn:disabled{background:#30363d;color:#8b949e;cursor:not-allowed}

  /* jonli suhbat ro'yxati */
  #cgptLog{display:none;flex-direction:column;gap:7px;margin-top:9px;
    max-height:230px;overflow-y:auto;padding-right:3px;
    border-top:1px solid rgba(255,255,255,.09);padding-top:9px}
  #cgptLog.on{display:flex}
  #cgptLog::-webkit-scrollbar{width:5px}
  #cgptLog::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14);border-radius:4px}
  .cgpt-msg{font-size:12.5px;line-height:1.5;padding:7px 11px;border-radius:11px;
    max-width:88%;word-break:break-word;white-space:pre-wrap}
  .cgpt-msg.u{align-self:flex-end;background:rgba(88,166,255,.16);
    border:1px solid rgba(88,166,255,.26);color:#dce6f5}
  .cgpt-msg.a{align-self:flex-start;background:rgba(255,255,255,.05);
    border:1px solid rgba(255,255,255,.09);color:#e6e8ee}
  .cgpt-msg .who{display:block;font-size:9.5px;letter-spacing:.7px;
    text-transform:uppercase;opacity:.5;margin-bottom:3px}

  /* "gapiryapti" ko'rsatkichi */
  #cgptTyping{display:none;align-items:center;gap:4px;margin-top:8px;
    font-size:11px;color:#8b949e}
  #cgptTyping.on{display:flex}
  #cgptTyping i{width:5px;height:5px;border-radius:50%;background:#8957e5;
    animation:cgptDots 1.1s ease-in-out infinite}
  #cgptTyping i:nth-child(2){animation-delay:.16s}
  #cgptTyping i:nth-child(3){animation-delay:.32s}
  #cgptTyping span{margin-left:5px}
  @keyframes cgptDots{0%,60%,100%{opacity:.25;transform:translateY(0)}
                      30%{opacity:1;transform:translateY(-3px)}}

  /* bosqichlar */
  #cgptSteps{display:none;flex-direction:column;gap:5px}
  #cgptSteps.on{display:flex}
  .cgpt-step{display:flex;align-items:center;gap:8px;font-size:12px;color:#6e7681}
  .cgpt-step i{width:14px;height:14px;border-radius:50%;flex:0 0 auto;
    border:1.5px solid #3a4150;position:relative}
  .cgpt-step b{margin-left:auto;font-weight:500;font-size:11px;color:#5b6474}
  .cgpt-step.now{color:#c9d1d9}
  .cgpt-step.now i{border-color:#58a6ff;animation:cgptSpin 1s linear infinite}
  .cgpt-step.now i::after{content:'';position:absolute;inset:1px;border-radius:50%;
    border:1.5px solid transparent;border-top-color:#58a6ff}
  .cgpt-step.fail{color:#ffb3b0}
  .cgpt-step.fail i{border-color:#da3633;background:#da3633;animation:none}
  .cgpt-step.fail i::after{content:'';position:absolute;left:5.5px;top:2px;width:1.6px;height:6px;
    background:#0d1117;box-shadow:0 7px 0 0 #0d1117}
  .cgpt-step.done{color:#8b949e}
  .cgpt-step.done i{border-color:#2ea043;background:#2ea043}
  .cgpt-step.done i::after{content:'';position:absolute;left:4px;top:1px;width:4px;height:8px;
    border:solid #0d1117;border-width:0 1.6px 1.6px 0;transform:rotate(45deg)}
  @keyframes cgptSpin{to{transform:rotate(360deg)}}

  /* tayyor */
  #cgptReady{display:none;text-align:center;padding:6px 0 2px}
  #cgptReady.on{display:block}
  .cgpt-ready-badge{display:inline-flex;align-items:center;gap:9px;
    background:linear-gradient(135deg,#1a7f4b,#2ea043);color:#fff;
    padding:9px 20px 9px 14px;border-radius:999px;font-weight:800;font-size:14px;
    letter-spacing:1.4px;box-shadow:0 0 0 0 rgba(46,160,67,.55);
    animation:cgptPop .3s ease-out, cgptHalo 1.7s ease-out .3s infinite}
  .cgpt-mic-ring{width:11px;height:11px;border-radius:50%;background:#fff;
    box-shadow:0 0 0 0 rgba(255,255,255,.85);animation:cgptRing 1.3s ease-out infinite}
  .cgpt-ready-sub{margin-top:7px;font-size:11.5px;color:#8b949e}
  @keyframes cgptPop{from{transform:scale(.86);opacity:0}to{transform:scale(1);opacity:1}}
  @keyframes cgptHalo{0%{box-shadow:0 0 0 0 rgba(46,160,67,.5)}
                      70%{box-shadow:0 0 0 14px rgba(46,160,67,0)}
                      100%{box-shadow:0 0 0 0 rgba(46,160,67,0)}}
  @keyframes cgptRing{0%{box-shadow:0 0 0 0 rgba(255,255,255,.8)}
                      70%{box-shadow:0 0 0 8px rgba(255,255,255,0)}
                      100%{box-shadow:0 0 0 0 rgba(255,255,255,0)}}
</style>
<!-- ══ DASHBOARD ══════════════════════════════════════════════════════════
     To'liq ko'rinish: kassalar, grafiklar va amallar zanjiri. Ma'lumot
     /api/hisob va /api/hisob/jurnal dan olinadi — hech narsa taxmin qilinmaydi. -->
<div id="dashOverlay">
  <div class="dash-shell">
    <div class="dash-head">
      <b>📊 MUHASIB Dashboard</b>
      <span class="dash-sub" id="dashSub"></span>
      <button id="dashYangila" type="button" title="Yangilash">↻</button>
      <button id="dashYopish" type="button" title="Yopish">✕</button>
    </div>
    <div class="dash-cards" id="dashCards"></div>
    <div class="dash-box dash-tafsilot" id="dashTafsilot"></div>
    <div class="dash-grid">
      <div class="dash-box">
        <h4>Kassa harakati <span class="dash-note">har valyuta alohida</span></h4>
        <div id="dashChiziq" class="dash-chart"></div>
      </div>
      <div class="dash-box">
        <h4>Kunlik kirim / chiqim <span id="dashValTanlov" class="dash-vals"></span></h4>
        <div id="dashUstun" class="dash-chart"></div>
      </div>
    </div>
    <div class="dash-box">
      <h4>Amallar zanjiri
        <span class="dash-note">↑↓ tanlash · Enter tafsilot · Delete o'chirish · / qidirish</span>
        <input id="dashQidir" class="dash-qidir" type="text" placeholder="qidirish…">
      </h4>
      <div class="dash-jadval-orash" id="dashOrash">
        <table class="dash-jadval">
          <thead><tr><th>Sana · vaqt</th><th>Amal</th><th>Tafsilot</th><th>Kassa</th>
                     <th class="son">O'zgarish</th><th class="son">Qoldiq</th></tr></thead>
          <tbody id="dashTana"></tbody>
        </table>
      </div>
    </div>

    <!-- Suhbat: amalni shu yerdan aytasiz, kerak bo'lsa savol beradi -->
    <div class="dash-box dash-suhbat">
      <h4>Yangi amal <span class="dash-note">oddiy gap bilan ayting — kerak bo'lsa so'raydi</span>
        <select id="dashModel" class="dash-model" title="AI modelini tanlang"></select>
      </h4>
      <div id="dashChat"></div>
      <div class="dash-composer">
        <textarea id="dashInput" rows="1"
          placeholder="Masalan: Sardordan 10 kg un sotib oldim, kilosi 8 ming, nasiyaga"></textarea>
        <button id="dashSend" type="button" title="Yuborish (Enter)">↑</button>
      </div>
      <div class="dash-tez" id="dashTez"></div>
    </div>
  </div>
</div>

<div id="cgptPanel" class="cgpt-panel">
  <div class="cgpt-head">
    <span class="cgpt-dot" id="cgptDot"></span>
    <span id="cgptState">ChatGPT ovozi</span>
    <button id="cgptCloseBtn" type="button" title="Tugatish">&#10005;</button>
  </div>

  <!-- Ishga tushish bosqichlari: qachon gapirish mumkinligi aniq bo'lsin -->
  <div id="cgptSteps">
    <div class="cgpt-step" data-step="0"><i></i><span>Daftar o&#8216;qilmoqda</span><b></b></div>
    <div class="cgpt-step" data-step="1"><i></i><span>ChatGPT&#8217;ga uzatilmoqda</span><b></b></div>
    <div class="cgpt-step" data-step="2"><i></i><span>Ovozli rejim ochilmoqda</span><b></b></div>
    <div class="cgpt-step" data-step="3"><i></i><span>Mikrofon yoqilmoqda</span><b></b></div>
  </div>

  <!-- Tayyor holat: katta va yorqin, ustiga qisqa signal ovozi beriladi -->
  <div id="cgptReady">
    <div class="cgpt-ready-badge"><span class="cgpt-mic-ring"></span>GAPIRING</div>
    <div class="cgpt-ready-sub">Mikrofon yoqiq — ChatGPT eshitib turibdi</div>
  </div>

  <!-- Xato va tuzatish tugmasi (masalan: ChatGPT'ga kirish kerak) -->
  <div id="cgptFix">
    <div id="cgptFixText"></div>
    <button id="cgptFixBtn" type="button"></button>
  </div>

  <!-- Jonli suhbat: siz nima dedingiz va ChatGPT nima deyapti -->
  <div id="cgptLog"></div>
  <div id="cgptTyping"><i></i><i></i><i></i><span>ChatGPT gapiryapti</span></div>
</div>

<script>
const $=s=>document.querySelector(s);
const chatArea=$('#chatArea'); let signedIn=false,convo=false,busy=false,loginPoll=null;

// Interactive Anti-Gravity Physics Canvas Engine
(function() {
  const canvas = document.getElementById('agCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let width, height;
  let particles = [];
  let mouse = { x: -1000, y: -1000, active: false };
  let zeroGActive = false;

  const colors = ['#4285f4', '#ea4335', '#fbbc05', '#34a853', '#a142f4'];

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  class Particle {
    constructor() {
      this.reset();
    }
    reset() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * 0.8;
      this.vy = (Math.random() - 0.5) * 0.8;
      this.radius = Math.random() * 3 + 2;
      this.color = colors[Math.floor(Math.random() * colors.length)];
      this.alpha = Math.random() * 0.5 + 0.3;
      this.pulse = Math.random() * Math.PI * 2;
      this.pulseSpeed = 0.02 + Math.random() * 0.03;
    }
    update() {
      this.pulse += this.pulseSpeed;
      
      if (zeroGActive) {
        this.vx += (Math.random() - 0.5) * 0.2;
        this.vy += (Math.random() - 0.5) * 0.2;
      }

      this.x += this.vx;
      this.y += this.vy;

      if (mouse.active) {
        const dx = this.x - mouse.x;
        const dy = this.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const maxDist = zeroGActive ? 280 : 180;
        if (dist < maxDist && dist > 0) {
          const force = (maxDist - dist) / maxDist;
          const push = force * (zeroGActive ? 4 : 2);
          this.vx += (dx / dist) * push * 0.1;
          this.vy += (dy / dist) * push * 0.1;
        }
      }

      this.vx *= 0.98;
      this.vy *= 0.98;

      if (this.x < 0) { this.x = 0; this.vx *= -1; }
      if (this.x > width) { this.x = width; this.vx *= -1; }
      if (this.y < 0) { this.y = 0; this.vy *= -1; }
      if (this.y > height) { this.y = height; this.vy *= -1; }
    }
    draw() {
      const light = document.documentElement.dataset.theme !== 'dark';
      ctx.save();
      ctx.globalAlpha = (this.alpha + Math.sin(this.pulse) * 0.15) * (light ? 0.5 : 1);
      ctx.fillStyle = this.color;
      ctx.shadowBlur = light ? 8 : 12;
      ctx.shadowColor = this.color;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }

  const particleCount = Math.min(Math.floor(window.innerWidth / 16), 80);
  for (let i = 0; i < particleCount; i++) {
    particles.push(new Particle());
  }

  window.addEventListener('mousemove', e => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.active = true;
  });

  window.addEventListener('mouseleave', () => {
    mouse.active = false;
  });

  window.addEventListener('click', e => {
    const cx = e.clientX;
    const cy = e.clientY;
    particles.forEach(p => {
      const dx = p.x - cx;
      const dy = p.y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 300 && dist > 0) {
        const force = (300 - dist) / 300;
        p.vx += (dx / dist) * force * 10;
        p.vy += (dy / dist) * force * 10;
      }
    });
  });

  const zeroGBtn = document.getElementById('zeroGBtn');
  if (zeroGBtn) {
    zeroGBtn.addEventListener('click', () => {
      zeroGActive = !zeroGActive;
      document.body.classList.toggle('zero-g-active', zeroGActive);
      zeroGBtn.classList.toggle('active', zeroGActive);
      if (zeroGActive) {
        particles.forEach(p => {
          p.vx = (Math.random() - 0.5) * 8;
          p.vy = (Math.random() - 0.5) * 8;
        });
      }
    });
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);

    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const p1 = particles[i];
        const p2 = particles[j];
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.save();
          ctx.globalAlpha = (1 - dist / 120) * 0.15;
          ctx.strokeStyle = p1.color;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    particles.forEach(p => {
      p.update();
      p.draw();
    });

    requestAnimationFrame(animate);
  }
  animate();
})();

/* Konfetti — faqat bayram uchun qisqa otilish (doimiy fon emas). */
function burstConfetti(n){
  const c=$('#confetti'),cols=['#4285f4','#ea4335','#fbbc05','#34a853','#a142f4'];
  const frag=document.createDocumentFragment();
  for(let i=0;i<(n||60);i++){
    const el=document.createElement('i');
    el.style.cssText=`left:${45+Math.random()*10}%;top:55%;background:${cols[i%cols.length]};`+
      `--dx:${(Math.random()-0.5)*90}vw;--dy:${-30-Math.random()*45}vh;--rot:${Math.random()*720-360}deg;`+
      `animation-delay:${Math.random()*0.15}s`;
    frag.appendChild(el);
  }
  c.appendChild(frag);
  setTimeout(()=>{c.innerHTML='';},2600);
}

/* --- CHAT HISTORY SIDEBAR SYSTEM --- */
let activeSessionId = null;
const ACTIVE_SESSION_STORAGE_KEY = 'agv_active_session';
const HISTORY_STORAGE_KEY = 'agv_chat_history';
const HISTORY_FALLBACK_STORAGE_KEY = 'agv_chat_history_session';
const HISTORY_MAX_SESSIONS = 40;
const HISTORY_MAX_MESSAGES = 80;
const HISTORY_MAX_TEXT_LENGTH = 12000;
const HISTORY_MAX_SERIALIZED_LENGTH = 900000;
let sessionCache = null;

function compactHistoryImage(imgData) {
  const src = String(imgData && imgData.src || '');
  if (!src || src.startsWith('data:') || src.length > 4096) return null;
  return { src };
}

/* Ish oqimini tarixga qisqartirib saqlaydi. Tarix localStorage'da yotadi va
   hajmi cheklangan, shuning uchun matnlar qirqiladi va qadamlar soni cheklanadi. */
function compactHistoryOqim(oqim) {
  if (!Array.isArray(oqim) || !oqim.length) return undefined;
  const toza = oqim
    .filter(x => x && (x.tur === 'izoh' || x.tur === 'guruh'))
    .slice(-24)
    .map(x => x.tur === 'izoh'
      ? { tur: 'izoh', matn: String(x.matn || '').slice(0, 400) }
      : {
          tur: 'guruh', ochiq: false,
          qadamlar: (Array.isArray(x.qadamlar) ? x.qadamlar : []).slice(0, 30).map(q => ({
            yorliq: String(q.yorliq || '').slice(0, 160),
            izoh: String(q.izoh || '').slice(0, 60),
            tur: String(q.tur || 'hisob'),
            fayl: q.fayl ? {
              nom: String(q.fayl.nom || '').slice(0, 80),
              amal: String(q.fayl.amal || ''),
              qoshildi: Number(q.fayl.qoshildi) || 0,
              ochirildi: Number(q.fayl.ochirildi) || 0,
            } : null,
          })),
        })
    .filter(x => x.tur === 'izoh' ? x.matn : x.qadamlar.length);
  return toza.length ? toza : undefined;
}

function compactSessions(rawSessions) {
  if (!Array.isArray(rawSessions)) return [];
  return rawSessions
    .filter(session => session && typeof session === 'object' && typeof session.id === 'string')
    .slice(0, HISTORY_MAX_SESSIONS)
    .map(session => ({
      id: session.id,
      title: typeof session.title === 'string' ? session.title.slice(0, 160) : 'Suhbat',
      timestamp: typeof session.timestamp === 'string' ? session.timestamp : new Date().toISOString(),
      messages: (Array.isArray(session.messages) ? session.messages : [])
        .slice(-HISTORY_MAX_MESSAGES)
        .filter(message => message && typeof message === 'object')
        .map(message => ({
          role: message.role === 'user' ? 'user' : 'model',
          text: String(message.text || '').slice(0, HISTORY_MAX_TEXT_LENGTH),
          imgData: compactHistoryImage(message.imgData),
          oqim: compactHistoryOqim(message.oqim),
          timestamp: typeof message.timestamp === 'string' ? message.timestamp : new Date().toISOString(),
        })),
    }));
}

function fitHistoryStorage(rawSessions) {
  const sessions = compactSessions(rawSessions);
  while (sessions.length && JSON.stringify(sessions).length > HISTORY_MAX_SERIALIZED_LENGTH) {
    const oldest = sessions[sessions.length - 1];
    if (oldest.messages.length > 1) oldest.messages.shift();
    else sessions.pop();
  }
  return sessions;
}

function rememberActiveSession(sessionId) {
  try {
    if (sessionId) localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId);
    else localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
  } catch (error) {}
}

function getSessions() {
  if (Array.isArray(sessionCache)) return sessionCache;
  let saved = [];
  try {
    saved = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY) || '[]');
  } catch (error) {
    try {
      saved = JSON.parse(sessionStorage.getItem(HISTORY_FALLBACK_STORAGE_KEY) || '[]');
    } catch (fallbackError) {}
  }
  sessionCache = fitHistoryStorage(saved);
  return sessionCache;
}

function saveSessions(sessions) {
  sessionCache = fitHistoryStorage(sessions);
  const serialized = JSON.stringify(sessionCache);
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, serialized);
    try { sessionStorage.removeItem(HISTORY_FALLBACK_STORAGE_KEY); } catch (error) {}
    return true;
  } catch (error) {
    try {
      sessionStorage.setItem(HISTORY_FALLBACK_STORAGE_KEY, serialized);
      return true;
    } catch (fallbackError) {
      console.warn('Suhbat tarixi brauzer xotirasiga yozilmadi.', fallbackError);
      return false;
    }
  }
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) {
    return 'Bugun ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  }
  return d.toLocaleDateString([], {month: 'short', day: 'numeric'});
}

function renderHistory(filterText = '') {
  const list = $('#historyList');
  if (!list) return;
  const sessions = getSessions();
  const q = filterText.toLowerCase().trim();
  const filtered = sessions.filter(s => (s.title || '').toLowerCase().includes(q));

  if (!filtered.length) {
    list.innerHTML = `<div style="text-align:center;padding:24px 10px;color:var(--muted);font-size:12.5px">${q ? 'Topilmadi' : 'Suhbatlar tarixi boʻsh'}</div>`;
    return;
  }

  list.innerHTML = filtered.map(s => `
    <div class="history-item ${s.id === activeSessionId ? 'active' : ''}" onclick="loadSession('${s.id}')">
      <div class="history-info">
        <span class="history-title">${(typeof LIVE !== 'undefined' && LIVE && LIVE.sid === s.id) ? '<span class="run-dot" title="Ish davom etmoqda"></span>' : '💬 '}${esc(s.title || 'Suhbat')}</span>
        <span class="history-date">${(typeof LIVE !== 'undefined' && LIVE && LIVE.sid === s.id) ? 'ishlayapti…' : formatDate(s.timestamp)}</span>
      </div>
      <div class="history-actions">
        <button class="history-share" onclick="event.stopPropagation(); shareSessionById('${s.id}')" title="Sessiyani ulashish">🔗</button>
        <button class="history-del" onclick="event.stopPropagation(); deleteSession('${s.id}')" title="O'chirish">🗑️</button>
      </div>
    </div>
  `).join('');
}

function createNewSession() {
  liveUnmount();
  const sessions = getSessions();
  const newS = {
    id: 's_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4),
    title: 'Yangi suhbat',
    timestamp: new Date().toISOString(),
    messages: []
  };
  sessions.unshift(newS);
  saveSessions(sessions);
  activeSessionId = newS.id;
  rememberActiveSession(activeSessionId);
  convo = false;
  chatArea.innerHTML = ''; paintWelcome();
  renderHistory();
  return newS;
}

function ensureActiveSession() {
  const sessions = getSessions();
  const active = sessions.find(session => session.id === activeSessionId);
  if (active) return active;
  const restored = sessions[0];
  if (!restored) return createNewSession();
  activeSessionId = restored.id;
  rememberActiveSession(activeSessionId);
  convo = restored.messages.some(message => message.role === 'model');
  if (!chatArea.children.length && restored.messages.length) loadSession(restored.id);
  return restored;
}

function saveMessageToHistory(role, text, imgData, sidOverride, oqim) {
  let sessions = getSessions();
  let sid = sidOverride || ensureActiveSession().id;
  if (!sid) {
    sid = createNewSession().id;
    sessions = getSessions();
  }
  let sIndex = sessions.findIndex(s => s.id === sid);
  if (sIndex < 0) {
    if (sidOverride) return;        // suhbat o'chirib yuborilgan — saqlaydigan joy yo'q
    const fresh = createNewSession();
    sessions = getSessions();
    sIndex = sessions.findIndex(s => s.id === fresh.id);
  }

  const msgObj = { role, text, imgData, timestamp: new Date().toISOString() };
  /* Ish oqimi ham saqlanadi — sahifa yangilansa qadamlar yo'qolmaydi.
     Rasmlar vaqtinchalik fayllarga ishora qilgani uchun ular saqlanmaydi. */
  if (oqim && oqim.length) msgObj.oqim = oqim.filter(x => x.tur !== 'rasm');
  sessions[sIndex].messages.push(msgObj);

  if (role === 'user' && (sessions[sIndex].title === 'Yangi suhbat' || !sessions[sIndex].title)) {
    const cleanTitle = text.trim().slice(0, 32);
    sessions[sIndex].title = cleanTitle ? cleanTitle + (text.length > 32 ? '…' : '') : 'Visual Suhbat';
  }
  sessions[sIndex].timestamp = new Date().toISOString();

  const activeS = sessions.splice(sIndex, 1)[0];
  sessions.unshift(activeS);

  saveSessions(sessions);
  renderHistory();
}

function loadSession(id) {
  const sessions = getSessions();
  const s = sessions.find(x => x.id === id);
  if (!s) return;

  liveUnmount();
  activeSessionId = id;
  rememberActiveSession(activeSessionId);
  convo = true;
  chatArea.innerHTML = ''; paintWelcome();
  showChat(true);

  if (s.messages && s.messages.length) {
    s.messages.forEach(m => {
      const bubble = addMsgToUI(m.role, m.text, false, m.imgData);
      if (m.oqim && m.oqim.length && bubble) {
        const oqimEl = document.createElement('div');
        oqimEl.innerHTML = oqimHTML(m.oqim, true);
        bubble.insertBefore(oqimEl, bubble.firstChild);
      }
    });
  }
  if (LIVE && LIVE.sid === id) liveMount();     // shu suhbatda ish ketayotgan bo'lsa — davomini ko'rsatamiz
  renderHistory();
  paintJobBadge();
  toggleSidebar(false);
}

function deleteSession(id) {
  if (LIVE && LIVE.sid === id) liveUnmount();
  let sessions = getSessions();
  sessions = sessions.filter(s => s.id !== id);
  saveSessions(sessions);
  if (activeSessionId === id) {
    activeSessionId = null;
    rememberActiveSession(null);
    chatArea.innerHTML = ''; paintWelcome();
    convo = false;
  }
  renderHistory();
}

/* ═══════════════════════════════════════════════════════════════
   SESSIYANI ULASHISH — share, load, delete shared sessions
   ═══════════════════════════════════════════════════════════════ */

function showShareToast(msg, duration = 3000) {
  const toast = $('#shareToast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('visible');
  clearTimeout(toast._tid);
  toast._tid = setTimeout(() => toast.classList.remove('visible'), duration);
}

async function shareSessionById(sessionId) {
  const sessions = getSessions();
  const s = sessions.find(x => x.id === sessionId);
  if (!s) { showShareToast('❌ Sessiya topilmadi'); return; }
  if (!s.messages || !s.messages.length) { showShareToast('❌ Bo\'sh sessiyani ulashib bo\'lmaydi'); return; }

  try {
    const r = await fetch('/api/session/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: s.title || 'Suhbat',
        messages: s.messages,
        model: $('#modelSel').value || '__chatgpt_sol__',
      }),
    });
    const data = await r.json();
    if (data.error) { showShareToast('❌ ' + data.error); return; }

    // Havolani clipboard'ga nusxalash
    const shareUrl = location.origin + data.url;
    try {
      await navigator.clipboard.writeText(shareUrl);
      showShareToast('✅ Havola nusxalandi! Sol dek ishlaydi.');
    } catch (e) {
      showShareToast('✅ Ulashildi: ' + shareUrl, 5000);
    }
    loadSharedSessions();
  } catch (e) {
    showShareToast('❌ Ulashishda xato: ' + e.message);
  }
}

async function loadSharedSessions() {
  const container = $('#sharedSessionsList');
  if (!container) return;
  try {
    const r = await fetch('/api/session/shared');
    const list = await r.json();
    if (!list.length) {
      container.innerHTML = '<div style="text-align:center;padding:12px;color:var(--muted);font-size:12.5px">Hali hech narsa ulashilmagan. Suhbat yonidagi 🔗 tugmasini bosing.</div>';
      return;
    }
    container.innerHTML = list.map(s => `
      <div class="shared-session-card" onclick="loadSharedSession('${s.id}')">
        <div class="shared-session-info">
          <span class="shared-session-title">🔗 ${esc(s.title)}</span>
          <span class="shared-session-meta">
            <span class="shared-session-badge">Sol Chat</span>
            ${s.messageCount} xabar · ${s.created ? s.created.replace('T', ' ') : ''}
          </span>
        </div>
        <div class="shared-session-actions">
          <button onclick="event.stopPropagation(); copySharedLink('${s.id}')" title="Havolani nusxalash">📋</button>
          <button class="shared-del" onclick="event.stopPropagation(); deleteSharedSession('${s.id}')" title="O'chirish">🗑️</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = '<div style="text-align:center;padding:12px;color:var(--muted);font-size:12.5px">Yuklab bo\'lmadi</div>';
  }
}

async function loadSharedSession(shareId) {
  try {
    const r = await fetch('/api/session/shared/' + encodeURIComponent(shareId));
    const data = await r.json();
    if (data.error) { showShareToast('❌ ' + data.error); return; }

    // Yangi local sessiya yaratib, ulashilgan xabarlarni yuklash
    liveUnmount();
    const sessions = getSessions();
    const newS = {
      id: 'sh_local_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4),
      title: '🔗 ' + (data.title || 'Ulashilgan suhbat'),
      timestamp: new Date().toISOString(),
      messages: data.messages || [],
      sharedFrom: shareId,
    };
    sessions.unshift(newS);
    saveSessions(sessions);
    activeSessionId = newS.id;
    rememberActiveSession(activeSessionId);

    // Model ni Sol ga qo'yish
    const modelSel = $('#modelSel');
    if (modelSel) {
      const solVal = '__chatgpt_sol__';
      if (Array.from(modelSel.options).some(o => o.value === solVal)) {
        modelSel.value = solVal;
        localStorage.setItem('agv_model', solVal);
      }
    }

    convo = true;
    chatArea.innerHTML = ''; paintWelcome();
    showChat(true);
    if (newS.messages && newS.messages.length) {
      newS.messages.forEach(m => addMsgToUI(m.role, m.text, false, m.imgData));
    }
    renderHistory();
    toggleSidebar(false);
    showShareToast('✅ Sessiya yuklandi — Sol dek gaplashing!');
  } catch (e) {
    showShareToast('❌ Yuklab bo\'lmadi: ' + e.message);
  }
}

async function deleteSharedSession(shareId) {
  try {
    await fetch('/api/session/shared/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: shareId }),
    });
    showShareToast('🗑️ O\'chirildi');
    loadSharedSessions();
  } catch (e) {
    showShareToast('❌ O\'chirib bo\'lmadi');
  }
}

async function copySharedLink(shareId) {
  const url = location.origin + '/shared/' + shareId;
  try {
    await navigator.clipboard.writeText(url);
    showShareToast('📋 Havola nusxalandi!');
  } catch (e) {
    showShareToast('📋 ' + url, 5000);
  }
}

// URL orqali shared sessiyani avtomatik yuklash
function checkSharedSessionUrl() {
  const path = location.pathname;
  if (path.startsWith('/shared/')) {
    const shareId = path.replace('/shared/', '');
    if (shareId) {
      setTimeout(() => loadSharedSession(shareId), 500);
    }
  }
}

function restoreActiveSession() {
  const sessions = getSessions();
  if (!sessions.length) return;
  let savedId = '';
  try {
    savedId = localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY) || '';
  } catch (error) {}
  const target = sessions.some(session => session.id === savedId)
    ? savedId
    : sessions[0].id;
  loadSession(target);
}

function toggleSidebar(forceState) {
  const sb = $('#sidebar');
  const overlay = $('#sidebarOverlay');
  if (!sb || !overlay) return;
  const isOpen = forceState !== undefined ? forceState : !sb.classList.contains('open');
  sb.classList.toggle('open', isOpen);
  overlay.classList.toggle('visible', isOpen);
}

$('#toggleSidebar').onclick = () => toggleSidebar(true);
if ($('#mobileNavToggle')) $('#mobileNavToggle').onclick = () => toggleSidebar();
$('#closeSidebar').onclick = () => toggleSidebar(false);
$('#sidebarOverlay').onclick = () => toggleSidebar(false);
$('#sbNewChatBtn').onclick = () => {
  createNewSession();
  toggleSidebar(false);
};
$('#historySearch').oninput = (e) => renderHistory(e.target.value);

// Ulashilgan sessiyalar
if ($('#refreshSharedBtn')) {
  $('#refreshSharedBtn').onclick = () => loadSharedSessions();
}
// Sozlamalar tabi ochilganda ulashilgan sessiyalar yangilanadi
document.querySelectorAll('.sb-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    if (tab.dataset.tab === 'tools') {
      setTimeout(loadSharedSessions, 100);
      setTimeout(paintUlanish, 60);        // ulanishlar holati har ochilganda yangilanadi
    }
  });
});

function useQuickPrompt(text) {
  $('#input').value = text;
  $('#input').focus();
  submit();
}

function esc(s){ return (s||'').replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

/* Pastga tushirish. CSS'dagi scroll-behavior:smooth tez-tez chaqirilganda
   animatsiyani qayta boshlab, pastga yetib bormaydi — shu sababli darhol suramiz.
   force=false bo'lsa va foydalanuvchi yuqorini o'qiyotgan bo'lsa — tegmaymiz. */
function scrollDown(force){
  const m = $('main');
  if(!m) return;
  if(!force && (m.scrollHeight - m.scrollTop - m.clientHeight) > 160) return;
  const prev = m.style.scrollBehavior;
  m.style.scrollBehavior = 'auto';
  m.scrollTop = m.scrollHeight;
  m.style.scrollBehavior = prev;
}

/* ── Gemini yulduzchasi (lipillovchi ish indikatori) ── */
const GEM_SPARK = `<svg class="gem-spark" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs><linearGradient id="gemgrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#4285f4"/><stop offset="38%" stop-color="#9b72cb"/>
    <stop offset="70%" stop-color="#d96570"/><stop offset="100%" stop-color="#fbbc05"/>
  </linearGradient></defs>
  <path fill="url(#gemgrad)" d="M12 0 Q13.3 8.6 24 12 Q13.3 15.4 12 24 Q10.7 15.4 0 12 Q10.7 8.6 12 0 Z"/>
</svg>`;

/* amal satridan qisqa holat matnini chiqaradi */
function actPhase(a){
  if(!a) return 'Ishlayapti…';
  const s = String(a).trim();
  if(s === '__stop__') return 'To\'xtatilmoqda…';
  if(s.includes('Biznes buyruq')) return 'Biznes funksiyasi yaratilmoqda…';
  if(s.startsWith('$')) return 'Buyruq bajarilmoqda…';
  if(s.startsWith('✍️')) return 'Fayl yozilmoqda…';
  if(s.startsWith('✏️')) return 'Fayl tahrirlanmoqda…';
  if(s.startsWith('📖') || s.startsWith('📄')) return 'Fayl o\'qilmoqda…';
  if(s.startsWith('📂')) return 'Papka ko\'rilmoqda…';
  if(s.startsWith('🔎')) return 'Qidirilmoqda…';
  if(s.startsWith('🌐')) return 'Internetdan qidirilmoqda…';
  if(s.startsWith('🎨')) return 'Rasm ishlab chiqarilmoqda…';
  if(s.startsWith('🎬') || s.startsWith('🎞️')) return 'Video ishlab chiqarilmoqda…';
  if(s.startsWith('✅')) return 'Yakunlanmoqda…';
  return 'Ishlayapti…';
}

function fmtDur(ms){
  const s = Math.max(0, Math.floor(ms/1000));
  return s < 60 ? s + 's' : Math.floor(s/60) + 'm ' + String(s%60).padStart(2,'0') + 's';
}

/* Jonli indikator: lipillovchi yulduzcha + holat + o'tgan vaqt + server puls nuqtasi */
function makeThinking(){
  const el = document.createElement('div');
  el.className = 'thinking';
  el.innerHTML = GEM_SPARK +
    '<span class="think-label">Javob tayyorlanmoqda…</span>' +
    '<span class="think-time">0s</span>' +
    '<span class="think-beat" title="Server bilan aloqa bor"></span>' +
    '<button class="think-stop" type="button" title="To\'xtatish (Esc)">■ To\'xtatish</button>';
  el.querySelector('.think-stop').onclick = stopLive;
  const labelEl = el.querySelector('.think-label');
  const timeEl  = el.querySelector('.think-time');
  const beatEl  = el.querySelector('.think-beat');
  let t0 = Date.now(), lastBeat = Date.now(), timer = null;
  function tick(){
    const d = Date.now() - t0;
    timeEl.textContent = fmtDur(d);
    const stale = Date.now() - lastBeat > 8000;
    beatEl.classList.toggle('stale', stale);
    beatEl.title = stale ? 'Serverdan signal kelmayapti…' : 'Server bilan aloqa bor';
  }
  return {
    el,
    start(sinceMs){ t0 = sinceMs || Date.now(); lastBeat = Date.now(); tick(); timer = setInterval(tick, 1000); },
    since(ms){ if(ms){ t0 = ms; tick(); } },
    beat(){
      lastBeat = Date.now();
      beatEl.classList.remove('hit'); void beatEl.offsetWidth; beatEl.classList.add('hit');
    },
    /* Agent hozir aynan nima qilayotganini ko'rsatadi — umumiy "ishlayapti" emas,
       balki haqiqiy qadam: qaysi fayl, qaysi buyruq, qanday natija. */
    phase(step){
      const s = String(step || '').trim();
      if(!s){ labelEl.textContent = 'Javob tayyorlanmoqda…'; return; }
      if(s === '__stop__'){ labelEl.textContent = 'To\'xtatilmoqda…'; return; }
      labelEl.textContent = s.length > 110 ? s.slice(0, 108) + '…' : s;
      labelEl.title = s;
    },
    stop(){ if(timer) clearInterval(timer); timer = null; el.remove(); }
  };
}

/* ══════ JONLI ISH (LIVE) — sahifa yangilansa ham yo'qolmaydi ══════
   Ish serverda "job" sifatida yuradi. Bu yerda faqat unga ulanamiz:
   suhbat almashsa DOM yechiladi, qaytib kelinsa yana ulanadi.        */
let LIVE = null;      // {jobId, sid, acts[], finalText, startedAt, ui}
let DESKTOP_LAST = { actions: [], endedAt: 0 };
let desktopLiveTimer = null;

function desktopLiveAutoEnabled(){
  try { return localStorage.getItem('agv_desktop_live_auto') === 'on'; } catch(e) { return false; }
}

function paintDesktopLiveAuto(){
  const button = $('#desktopLiveAuto');
  if(button) button.textContent = desktopLiveAutoEnabled() ? 'Avto: YOQ' : 'Avto: O‘CHIQ';
}

function desktopLiveOpen(){
  const modal = $('#desktopLiveModal');
  return Boolean(modal && !modal.classList.contains('hidden'));
}

function paintDesktopLiveActions(){
  const list = $('#desktopLiveActions');
  const count = $('#desktopLiveActionCount');
  if(!list || !count) return;
  const running = Boolean(LIVE);
  const actions = running ? LIVE.acts : DESKTOP_LAST.actions;
  count.textContent = actions.length ? actions.length + ' qadam' : 'kutilmoqda';
  if(!actions.length){
    list.innerHTML = '<div class="desktop-live-empty">Agentga vazifa yuboring. U fayl, terminal yoki visual quvur bilan ishlaganda qadamlar shu yerda jonli paydo bo‘ladi.</div>';
    return;
  }
  list.innerHTML = actions.slice(-18).map((action, index, recent) => {
    const active = running && index === recent.length - 1;
    return '<div class="desktop-live-action' + (active ? ' active' : '') + '">' +
      '<b>' + (Math.max(0, actions.length - recent.length) + index + 1) + '</b>' +
      '<span>' + esc(action) + '</span>' +
    '</div>';
  }).join('');
}

function desktopLiveSetStatus(text, problem=false){
  const status = $('#desktopLiveStatus');
  if(!status) return;
  status.classList.toggle('problem', problem);
  const copy = status.querySelector('span');
  if(copy) copy.textContent = text;
}

async function desktopLiveStreamError(){
  if(!desktopLiveOpen()) return;
  let message = 'Desktop oqimi uzildi. Yangilash tugmasi bilan qayta ulang.';
  try{
    const response = await fetch('/api/desktop/frame?health=' + Date.now(), {cache:'no-store'});
    if(!response.ok){
      const detail = await response.json().catch(() => ({}));
      message = detail.error || message;
    }
  }catch(e){}
  if(!desktopLiveOpen()) return;
  desktopLiveSetStatus('Ekran ruxsati kerak', true);
  $('#desktopLiveFrameLabel').textContent = 'Desktop oqimi ulanmagan';
  const placeholder = $('#desktopLivePlaceholder');
  placeholder.classList.remove('hidden');
  placeholder.querySelector('strong').textContent = 'Desktop Live ulanmagan';
  placeholder.querySelector('p').textContent = message;
}

function refreshDesktopLive(){
  if(!desktopLiveOpen()) return;
  const image = $('#desktopLiveFrame');
  const placeholder = $('#desktopLivePlaceholder');
  const refresh = $('#desktopLiveRefresh');
  if(refresh) refresh.disabled = true;
  image.onload = () => {
    if(!desktopLiveOpen()) return;
    image.style.display = 'block';
    placeholder.classList.add('hidden');
    desktopLiveSetStatus(LIVE ? 'Agent ishlayapti' : 'Turbo 8 FPS');
    $('#desktopLiveFrameLabel').textContent = 'Jonli oqim · 8 FPS · ' + new Date().toLocaleTimeString();
    $('#desktopLiveClock').textContent = new Date().toLocaleTimeString();
    if(refresh) refresh.disabled = false;
  };
  image.onerror = () => { if(refresh) refresh.disabled = false; desktopLiveStreamError(); };
  image.removeAttribute('src');
  image.src = '/api/desktop/stream?fps=8&ts=' + Date.now();
}

function openDesktopLive(){
  const modal = $('#desktopLiveModal');
  if(!modal) return;
  modal.classList.remove('hidden');
  paintDesktopLiveAuto();
  paintDesktopLiveActions();
  refreshDesktopLive();
  if(desktopLiveTimer) clearInterval(desktopLiveTimer);
  desktopLiveTimer = setInterval(() => {
    paintDesktopLiveActions();
    const clock = $('#desktopLiveClock');
    if(clock) clock.textContent = new Date().toLocaleTimeString();
  }, 1000);
}

function closeDesktopLive(){
  const modal = $('#desktopLiveModal');
  if(modal) modal.classList.add('hidden');
  if(desktopLiveTimer){ clearInterval(desktopLiveTimer); desktopLiveTimer = null; }
  const image = $('#desktopLiveFrame');
  if(image){
    image.onload = null;
    image.onerror = null;
    image.removeAttribute('src');
  }
}

/* ══════ BRAUZER PANELI ══════
   Agent haqiqiy Chrome oynasini boshqaradi. Sahifani iframe ichida ko'rsatib
   bo'lmaydi (saytlar ruxsat bermaydi), shuning uchun panel jonli kadr oqimini
   ko'rsatadi — foydalanuvchi agent nima qilayotganini real vaqtda ko'rib turadi. */
let BRAUZER = { qadamlar: [], url: '', sarlavha: '', ochildi: false };

function brauzerOchiqmi(){
  const m = $('#brauzerModal');
  return Boolean(m && !m.classList.contains('hidden'));
}

function brauzerHolat(matn, muammo=false){
  const el = $('#brauzerStatus');
  if(!el) return;
  el.classList.toggle('problem', muammo);
  const s = el.querySelector('span');
  if(s) s.textContent = matn;
}

function paintBrauzerQadamlar(){
  const ro = $('#brauzerQadamlar'), son = $('#brauzerQadamSoni');
  if(!ro || !son) return;
  const q = BRAUZER.qadamlar;
  son.textContent = q.length ? q.length + ' qadam' : 'kutilmoqda';
  if(!q.length){
    ro.innerHTML = '<div class="desktop-live-empty">Agentga “falon saytga kirib shuni qil” deb ayting — bosgan har bir tugmasi shu yerda chiqadi.</div>';
    return;
  }
  ro.innerHTML = q.slice(-20).map((s, i, oxirgilar) => {
    const faol = Boolean(LIVE) && i === oxirgilar.length - 1;
    return '<div class="desktop-live-action' + (faol ? ' active' : '') + '">' +
      '<b>' + (Math.max(0, q.length - oxirgilar.length) + i + 1) + '</b>' +
      '<span>' + esc(s) + '</span></div>';
  }).join('');
  ro.scrollTop = ro.scrollHeight;
}

function refreshBrauzer(){
  if(!brauzerOchiqmi()) return;
  const img = $('#brauzerFrame'), joy = $('#brauzerPlaceholder'), btn = $('#brauzerRefresh');
  if(btn) btn.disabled = true;
  img.onload = () => {
    if(!brauzerOchiqmi()) return;
    img.style.display = 'block';
    joy.classList.add('hidden');
    brauzerHolat(LIVE ? 'Agent ishlayapti' : 'Ulangan');
    $('#brauzerFrameLabel').textContent = 'Jonli · ' + new Date().toLocaleTimeString();
    if(btn) btn.disabled = false;
  };
  img.onerror = async () => {
    if(btn) btn.disabled = false;
    if(!brauzerOchiqmi()) return;
    brauzerHolat('Ulanmagan', true);
    img.style.display = 'none';
    joy.classList.remove('hidden');
    $('#brauzerFrameLabel').textContent = 'Brauzer ochilmagan';
  };
  img.removeAttribute('src');
  img.src = '/api/brauzer/oqim?fps=2&ts=' + Date.now();
}

async function brauzerOch(url){
  url = (url || '').trim();
  if(!url) return;
  brauzerHolat('Ochilmoqda…');
  $('#brauzerFrameLabel').textContent = 'Sahifa ochilmoqda…';
  try{
    const r = await fetch('/api/brauzer/och', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url})
    });
    const d = await r.json();
    if(!d.ok) throw new Error(d.error || 'ochib bo‘lmadi');
    BRAUZER.url = d.url || url;
    BRAUZER.sarlavha = d.sarlavha || '';
    $('#brauzerUrl').value = BRAUZER.url;
    $('#brauzerSarlavha').textContent = BRAUZER.sarlavha || BRAUZER.url;
    BRAUZER.qadamlar.push('🌐 Siz ochdingiz · ' + BRAUZER.url);
    paintBrauzerQadamlar();
    refreshBrauzer();
  }catch(e){
    brauzerHolat('Xato', true);
    $('#brauzerFrameLabel').textContent = 'Ochib bo‘lmadi: ' + (e.message || e);
  }
}

/* ── Panel orqali boshqarish ──────────────────────────────────────────────
   Kadr oddiy rasm, shuning uchun bosilgan nuqtani sahifa koordinatasiga
   o'girish kerak: rasm `object-fit: contain` bilan chiziladi, ya'ni chetida
   bo'sh yo'l qolishi mumkin. Shuni hisobga olmasak bosish siljib ketadi. */
function brauzerKoordinata(hodisa){
  const img = $('#brauzerFrame');
  if(!img || !img.naturalWidth) return null;
  const r = img.getBoundingClientRect();
  const nisbat = Math.min(r.width / img.naturalWidth, r.height / img.naturalHeight);
  const en = img.naturalWidth * nisbat, boy = img.naturalHeight * nisbat;
  const chapBosh = r.left + (r.width - en) / 2, tepaBosh = r.top + (r.height - boy) / 2;
  const x = (hodisa.clientX - chapBosh) / nisbat, y = (hodisa.clientY - tepaBosh) / nisbat;
  if(x < 0 || y < 0 || x > img.naturalWidth || y > img.naturalHeight) return null;
  return {x: Math.round(x), y: Math.round(y)};
}

async function brauzerAmal(tana){
  try{
    await fetch('/api/brauzer/amal', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(tana)});
  }catch(e){}
}

function brauzerBoshqaruvniUla(){
  const img = $('#brauzerFrame');
  if(!img || img.dataset.ulangan) return;
  img.dataset.ulangan = '1';

  img.addEventListener('click', e => {
    const n = brauzerKoordinata(e);
    if(!n) return;
    img.focus();
    brauzerAmal({tur:'bos', x:n.x, y:n.y});
  });
  img.addEventListener('dblclick', e => {
    const n = brauzerKoordinata(e);
    if(n) brauzerAmal({tur:'bos', x:n.x, y:n.y, ikki:true});
  });
  img.addEventListener('wheel', e => {
    const n = brauzerKoordinata(e);
    if(!n) return;
    e.preventDefault();
    brauzerAmal({tur:'scroll', x:n.x, y:n.y, delta: e.deltaY});
  }, {passive:false});

  /* Klaviatura: oddiy belgilar matn sifatida, boshqaruv tugmalari alohida.
     Yozilgan matn faqat shu Mac ichida qoladi — hech qayerga saqlanmaydi. */
  const MAXSUS = ['Enter','Tab','Escape','Backspace','Delete','ArrowUp','ArrowDown',
                  'ArrowLeft','ArrowRight','Home','End','PageUp','PageDown'];
  img.addEventListener('keydown', e => {
    if(e.metaKey || e.ctrlKey || e.altKey) return;
    if(MAXSUS.includes(e.key)){
      e.preventDefault();
      brauzerAmal({tur:'tugma', tugma: e.key});
    } else if(e.key.length === 1){
      e.preventDefault();
      brauzerAmal({tur:'yoz', matn: e.key});
    }
  });
  /* Nusxa-joylash — uzun parol yoki kodni qo'lda terish shart emas */
  img.addEventListener('paste', e => {
    const matn = (e.clipboardData || window.clipboardData).getData('text');
    if(matn){ e.preventDefault(); brauzerAmal({tur:'yoz', matn}); }
  });
}

/* Agent kirish so'raganini panel shu yerdan biladi. SSE bilan emas, chunki
   vosita kutayotgan paytda hodisa oqimi to'xtab turadi. */
let brauzerHolatTimer = null;
async function brauzerHolatniSora(){
  if(!brauzerOchiqmi()) return;
  try{
    const d = await (await fetch('/api/brauzer/holat', {cache:'no-store'})).json();
    if(d.url && document.activeElement !== $('#brauzerUrl')) $('#brauzerUrl').value = d.url;
    if(d.sarlavha) $('#brauzerSarlavha').textContent = d.sarlavha;
    const login = d.login || {};
    const qatlam = $('#brauzerLogin');
    qatlam.classList.toggle('hidden', !login.faol);
    if(login.faol){
      $('#brauzerLoginIzoh').textContent = login.izoh || 'Agent kutib turibdi.';
      brauzerHolat('Sizdan kirish kutilmoqda', true);
    }
  }catch(e){}
}

async function brauzerDavomEt(){
  $('#brauzerLogin').classList.add('hidden');
  brauzerHolat('Davom etilmoqda…');
  await fetch('/api/brauzer/davom', {method:'POST'}).catch(()=>{});
}

function openBrauzer(){
  const m = $('#brauzerModal');
  if(!m) return;
  m.classList.remove('hidden');
  BRAUZER.ochildi = true;
  if(BRAUZER.url) $('#brauzerUrl').value = BRAUZER.url;
  paintBrauzerQadamlar();
  brauzerBoshqaruvniUla();
  refreshBrauzer();
  brauzerHolatniSora();
  if(brauzerHolatTimer) clearInterval(brauzerHolatTimer);
  brauzerHolatTimer = setInterval(brauzerHolatniSora, 2000);
}

function closeBrauzer(){
  const m = $('#brauzerModal');
  if(m) m.classList.add('hidden');
  if(brauzerHolatTimer){ clearInterval(brauzerHolatTimer); brauzerHolatTimer = null; }
  const img = $('#brauzerFrame');
  if(img){ img.onload = null; img.onerror = null; img.removeAttribute('src'); }
}

/* Agent birinchi marta brauzerga tegsa — panel o'zi ochiladi. Foydalanuvchi
   hech narsa bosmasdan agent saytda nima qilayotganini ko'rib turadi. */
function brauzerHodisa(holat, qadam){
  if(holat){
    if(holat.url) BRAUZER.url = holat.url;
    if(holat.sarlavha) BRAUZER.sarlavha = holat.sarlavha;
  }
  if(qadam) BRAUZER.qadamlar.push(qadam);
  if(!brauzerOchiqmi() && !BRAUZER.ochildi){ openBrauzer(); }
  else if(brauzerOchiqmi()){
    const u = $('#brauzerUrl');
    if(u && document.activeElement !== u) u.value = BRAUZER.url || '';
    $('#brauzerSarlavha').textContent = BRAUZER.sarlavha || BRAUZER.url || 'Brauzer';
  }
  paintBrauzerQadamlar();
}

/* ══════ JADVAL OYNASI ══════
   Agent Google Sheets bilan ishlaganda ma'lumot shu yerda ko'rinadi.
   Modal qilmadik: suhbat ochiq qoladi va agent ishini davom ettiraveradi. */
function paintJadval(d){
  const panel = $('#jadvalPanel');
  if(!panel || !d) return;
  const qatorlar = d.qatorlar || [];
  $('#jadvalSarlavha').textContent = d.sarlavha || 'Jadval';
  const havola = $('#jadvalHavola');
  if(d.havola){ havola.href = d.havola; havola.style.display = ''; }
  else havola.style.display = 'none';

  if(!qatorlar.length){
    $('#jadvalTana').innerHTML = '<div style="padding:18px;text-align:center;color:var(--muted);font-size:12.5px">Ma’lumot yo‘q</div>';
    $('#jadvalFoot').textContent = '';
  } else {
    /* Birinchi qator sarlavha deb olinadi — jadvallarda deyarli har doim shunday */
    const bosh = qatorlar[0], tana = qatorlar.slice(1);
    $('#jadvalTana').innerHTML =
      '<table><thead><tr><th class="qator-raqam"></th>' +
        bosh.map(h => '<th>' + esc(h) + '</th>').join('') +
      '</tr></thead><tbody>' +
      tana.map((q, i) => '<tr><td class="qator-raqam">' + (i + 2) + '</td>' +
        bosh.map((_, j) => '<td>' + esc(q[j] === undefined ? '' : q[j]) + '</td>').join('') +
        '</tr>').join('') +
      '</tbody></table>';
    $('#jadvalFoot').textContent = tana.length + ' qator · ' + bosh.length + ' ustun' +
      (d.varaq ? ' · ' + d.varaq : '');
  }
  panel.classList.remove('hidden', 'yigik');
}

if($('#jadvalYop')) $('#jadvalYop').onclick = () => $('#jadvalPanel').classList.add('hidden');
if($('#jadvalYig')) $('#jadvalYig').onclick = () => $('#jadvalPanel').classList.toggle('yigik');

/* ══════ ULANISHLAR PANELI ══════
   Har bir ulanish o'z tasdiqlash usuliga ega: TV ekranidagi kod, telefondagi
   so'rov, @BotFather bergan token. Hech qayerda parol so'ralmaydi. */
let ULANISH = null;

function ulanishNatija(el, matn, ok){
  const j = el.querySelector('.ulanish-natija');
  if(j){ j.textContent = matn; j.className = 'ulanish-natija ' + (ok ? 'ok' : 'xato'); }
}

function ulanishKarta(belgi, nom, izoh, ulangan, ich){
  return '<div class="ulanish-karta"><div class="ulanish-bosh">' +
    '<span class="ulanish-belgi">' + belgi + '</span>' +
    '<span class="ulanish-nom"><b>' + esc(nom) + '</b></span>' +
    '<span class="ulanish-nishon ' + (ulangan ? 'ok' : 'yoq') + '">' +
      (ulangan ? 'ulangan' : 'ulanmagan') + '</span>' +
    '<small class="ulanish-nom">' + izoh + '</small>' +
    '</div><div class="ulanish-tana">' + ich +
    '<div class="ulanish-natija"></div></div></div>';
}

async function paintUlanish(){
  const joy = $('#ulanishRoyxat');
  if(!joy) return;
  try{
    ULANISH = await (await fetch('/api/ulanish/holat', {cache:'no-store'})).json();
  }catch(e){
    joy.innerHTML = '<div class="ulanish-yuklanmoqda">Holatni olib bo‘lmadi.</div>';
    return;
  }
  const u = ULANISH;
  let html = '';

  /* Printer — macOS o'zi boshqaradi, sozlash kerak emas */
  const p = u.printer || {royxat:[], soni:0};
  html += ulanishKarta('🖨️', 'Printerlar',
    p.soni ? p.royxat.map(x => esc(x.nom) + ' — ' + x.holat).join('<br>')
           : 'Printer topilmadi. macOS sozlamalaridan qo‘shing.',
    p.soni > 0,
    (p.soni ? '<div class="ulanish-qator"><button type="button" data-sinov="printer">Sinov cheki chiqarish</button></div>' : '') +
    (p.chek ? '<div class="ulanish-yordam">Chek printeri topildi: <code>' + esc(p.chek) +
              '</code> — agent sotuv chekini shunga chiqaradi.</div>' : ''));

  /* TV — ekrandagi kod bilan */
  const tv = u.tv || {};
  html += ulanishKarta('📺', 'Televizor',
    tv.ulangan ? ('Ulangan: ' + esc(tv.host || '') + (tv.yoqiq ? ' · yoqiq' : ''))
               : 'Android TV / Google TV — ekranda chiqadigan kod bilan ulanadi.',
    Boolean(tv.ulangan),
    '<div class="ulanish-qator"><button type="button" id="tvQidir">Wi-Fi dan qidirish</button>' +
      (tv.ulangan ? '<button type="button" data-sinov="tv">Sinash</button>' : '') + '</div>' +
    '<div id="tvQurilmalar"></div>' +
    '<div class="ulanish-qator hidden" id="tvKodQator">' +
      '<input id="tvKod" type="text" inputmode="numeric" placeholder="TV ekranidagi 6 xonali kod">' +
      '<button type="button" class="asosiy" id="tvTasdiq">Tasdiqlash</button></div>' +
    '<div class="ulanish-yordam">TV va Mac bir Wi-Fi da bo‘lishi kerak. TV da <code>Android TV</code> yoki <code>Google TV</code> bo‘lsa ishlaydi.</div>');

  /* iPhone — Messages orqali */
  const ip = u.iphone || {};
  html += ulanishKarta('📱', 'iPhone — SMS va qo‘ng‘iroq',
    ip.messages_bor ? 'Messages ilovasi orqali ishlaydi.' : 'Messages ilovasi topilmadi.',
    Boolean(ip.messages_bor),
    '<div class="ulanish-yordam">Ishlashi uchun: Mac va iPhone bir <b>Apple ID</b> da bo‘lsin, ' +
    'iPhone da <code>Sozlamalar → Xabarlar → SMS uzatish</code> yoqilsin. ' +
    'Qo‘ng‘iroq uchun <code>Sozlamalar → Telefon → Boshqa qurilmada</code>.</div>');

  /* Android telefon — adb so'rovi bilan */
  const an = u.android || {};
  const anQ = (an.qurilmalar || []);
  html += ulanishKarta('🤖', 'Android telefon',
    anQ.length ? anQ.map(x => esc(x.model || x.id) + ' — ' + x.holat).join('<br>')
      : (an.adb ? 'Telefon ulanmagan.' : 'adb o‘rnatilmagan.'),
    anQ.some(x => x.holat === 'device'),
    '<div class="ulanish-yordam">' + (an.adb
      ? 'Telefonda <code>Developer options → USB debugging</code> ni yoqing va USB bilan ulang. ' +
        'Telefonda “Ruxsat berilsinmi?” so‘rovi chiqadi — <b>Ruxsat</b> bosing.'
      : 'Terminalda: <code>brew install android-platform-tools</code>') + '</div>');

  /* Telegram — bot tokeni bilan */
  const tg = u.telegram || {};
  html += ulanishKarta('✈️', 'Telegram',
    tg.ulangan ? ('Bot: @' + esc(tg.bot || '')) : 'Bot tokeni bilan ulanadi.',
    Boolean(tg.ulangan),
    '<div class="ulanish-qator">' +
      '<input id="tgToken" type="password" autocomplete="off" placeholder="' +
        (tg.ulangan ? '•••••• (saqlangan)' : '123456:AAE...') + '">' +
      '<button type="button" class="asosiy" id="tgSaqla">Saqlash</button>' +
      (tg.ulangan ? '<button type="button" id="tgOchir">O‘chirish</button>' : '') +
    '</div>' +
    (tg.ulangan ? '<div class="ulanish-qator"><button type="button" id="tgSuhbat">Suhbatlarni ko‘rish</button></div><div id="tgRoyxat"></div>' : '') +
    '<div class="ulanish-yordam">Telegramda <code>@BotFather</code> ga <code>/newbot</code> yozing, ' +
    'u bergan tokenni shu yerga joylang. Bot faqat <b>o‘ziga yozgan</b> odamga xabar yubora oladi — ' +
    'kerakli odam botingizga bir marta <code>/start</code> yozsin.</div>');

  /* Google Sheets — o'z Google hisobingiz bilan, ilovadan chiqmasdan */
  const sh = u.sheets || {};
  const avto = sh.avto || {};
  html += ulanishKarta('📊', 'Google Sheets',
    sh.ulangan
      ? ('Ulangan · ' + (sh.usul === 'google' ? 'Google hisobingiz' : esc(sh.pochta || 'xizmat hisobi')) +
         (sh.jadvallar !== undefined ? ' · ' + sh.jadvallar + ' jadval' : ''))
      : (sh.mijoz_bor ? 'Ruxsat berish qoldi — bir marta bosing.'
                      : 'Daftaringiz jadvalga o‘zi tushib turadi.'),
    Boolean(sh.ulangan),
    (!sh.ulangan
      ? /* Ulanish — Cloud Console kerak emas, hammasi Google Sheets ichida */
        '<div class="ulanish-qator">' +
          '<button type="button" class="asosiy" id="shKodOl">1 · Kodni nusxalash</button>' +
          '<button type="button" id="shSkriptOch">2 · Sheets’da ochish</button>' +
        '</div>' +
        '<div class="ulanish-qator">' +
          '<input id="shSkriptUrl" type="text" autocomplete="off" placeholder="3 · Web app manzilini joylang (…/exec)">' +
          '<button type="button" class="asosiy" id="shSkriptSaqla">Ulash</button>' +
        '</div>' +
        '<div class="ulanish-yordam"><b>Uch qadam:</b><br>' +
        '1. <b>Kodni nusxalash</b> — kod buferga tushadi<br>' +
        '2. <b>Sheets’da ochish</b> — yangi Apps Script muharriri ochiladi. Google hisobingizga ' +
        'kirishni so‘rasa, shu oynaning o‘zida kirasiz. Muharrirdagi borini o‘chirib, ' +
        'kodni joylang va <code>⌘S</code> bilan saqlang<br>' +
        '3. Yuqoridagi <code>Deploy → New deployment</code> ni bosing, turini ' +
        '<code>Web app</code> tanlang, <code>Who has access</code> ni <code>Anyone</code> ' +
        'qiling, <b>Deploy</b> bosing. Birinchi marta ruxsat so‘raydi — <b>Allow</b> bering. ' +
        'Chiqqan <code>…/exec</code> manzilini shu yerga joylang<br><br>' +
        '<b>Cloud Console, JSON kalit va jadvalni ulashish kerak emas.</b> Skript sizning ' +
        'hisobingiz nomidan ishlaydi, hamma jadvalingizni ko‘radi va faqat shu dastur ' +
        'unga murojaat qila oladi.</div>'
      : /* Ulangan — avto-yozuvni sozlash */
        (true
          ?
            '<div class="ulanish-qator">' +
              '<input id="shAvto" type="text" placeholder="Jadval havolasini joylang" value="' +
                (avto.id ? esc('https://docs.google.com/spreadsheets/d/' + avto.id) : '') + '">' +
              '<button type="button" class="asosiy" id="shAvtoSaqla">Ulash</button>' +
            '</div>' +
            (avto.id
              ? '<div class="ulanish-qator">' +
                  '<button type="button" id="shSinxron">Hozir yuborish</button>' +
                  '<button type="button" id="shAvtoOchir">Avto-yozuvni to‘xtatish</button>' +
                '</div>' +
                '<div class="ulanish-yordam">✅ <b>Avto-yozuv yoqilgan.</b> Daftarga har yozganingizda ' +
                'jadval o‘zi yangilanadi — qo‘shish ham, o‘chirish ham. Varaq: <code>' +
                esc(avto.varaq || 'Amallar') + '</code>' +
                (avto.holat ? '<br>Oxirgi yuborish: ' + esc(avto.holat) : '') + '</div>'
              : '<div class="ulanish-yordam">Jadval havolasini joylasangiz, daftardagi har bir ' +
                'o‘zgarish o‘sha jadvalga <b>avtomatik</b> tushib turadi.</div>') +
            '<div class="ulanish-qator"><button type="button" id="shUzish">Ulanishni uzish</button></div>'
          : '')
    ) + (sh.xato ? '<div class="ulanish-natija xato">' + esc(sh.xato) + '</div>' : ''));

  /* Kalendar, eslatma va pochta — macOS ilovalari orqali */
  const kal = u.kalendar || {}, po = u.pochta || {};
  html += ulanishKarta('📅', 'Kalendar, eslatma va pochta',
    'Kalendar: ' + (kal.bor ? 'bor' : 'yo‘q') + ' · Eslatmalar: ' + (kal.eslatma ? 'bor' : 'yo‘q') +
    ' · Mail: ' + (po.hisoblar ? po.hisoblar + ' hisob' : 'hisob sozlanmagan'),
    Boolean(kal.bor),
    '<div class="ulanish-yordam">Uchalasi ham macOS ilovalari orqali ishlaydi — sozlash kerak emas. ' +
    'iCloud yoqilgan bo‘lsa voqea va eslatma telefoningizda ham chiqadi. ' +
    'Xat yuborish uchun <b>Mail</b> ilovasida hech bo‘lmasa bitta hisob bo‘lsin.<br>' +
    'Birinchi marta ishlatganda macOS ruxsat so‘raydi — <b>Ruxsat</b> bosing.</div>');

  /* Instagram va shunga o'xshash saytlar — brauzer paneli orqali */
  html += ulanishKarta('🌐', 'Instagram va boshqa saytlar',
    'Brauzer paneli orqali — siz kirasiz, agent davom ettiradi.', true,
    '<div class="ulanish-yordam">Instagram parol bilan avtomatlashtirishni taqiqlaydi va bunday ' +
    'hisoblarni bloklaydi. Shuning uchun agent <b>Brauzer</b> panelida saytni ochadi, siz o‘sha ' +
    'oynada kirasiz va u ishni davom ettiradi. Bir marta kirsangiz yetadi — profil saqlanadi.</div>' +
    '<div class="ulanish-qator"><button type="button" id="ulanishBrauzer">Brauzerni ochish</button></div>');

  joy.innerHTML = html;
  ulanishHodisalar();
}

function ulanishHodisalar(){
  document.querySelectorAll('[data-sinov]').forEach(b => {
    b.onclick = async () => {
      const karta = b.closest('.ulanish-karta');
      b.disabled = true; ulanishNatija(karta, 'Sinalmoqda…', true);
      try{
        const d = await (await fetch('/api/ulanish/sinov', {method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({tur: b.dataset.sinov, printer: (ULANISH.printer||{}).chek || ''})})).json();
        ulanishNatija(karta, d.ok ? (d.xabar || d.javob || 'Ishladi ✅') : ('Xato: ' + (d.sabab||'')), d.ok);
      }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
      b.disabled = false;
    };
  });

  const qidir = $('#tvQidir');
  if(qidir) qidir.onclick = async () => {
    const karta = qidir.closest('.ulanish-karta');
    qidir.disabled = true; ulanishNatija(karta, 'Wi-Fi tekshirilmoqda…', true);
    try{
      const d = await (await fetch('/api/ulanish/qurilmalar?soniya=7')).json();
      const bosh = (d.qurilmalar || []).filter(x => x.boshqariladi);
      const hammasi = d.qurilmalar || [];
      $('#tvQurilmalar').innerHTML = hammasi.length
        ? hammasi.map(x => '<div class="ulanish-qurilma"><span>' + esc(x.nom) + ' · ' + esc(x.tur) + '</span>' +
            (x.boshqariladi ? '<button type="button" class="asosiy" data-host="' + esc(x.ip) + '">Ulash</button>' : '') +
            '</div>').join('')
        : '<div class="ulanish-yordam">Qurilma topilmadi. TV yoqiqmi va bir Wi-Fi damisiz — tekshiring.</div>';
      ulanishNatija(karta, hammasi.length + ' qurilma topildi' +
        (bosh.length ? '' : ' (boshqariladigan TV yo‘q)'), true);
      document.querySelectorAll('[data-host]').forEach(t => {
        t.onclick = async () => {
          t.disabled = true; ulanishNatija(karta, 'TV ga ulanmoqda…', true);
          try{
            const r = await (await fetch('/api/ulanish/tv/boshla', {method:'POST',
              headers:{'Content-Type':'application/json'},
              body: JSON.stringify({host: t.dataset.host})})).json();
            if(!r.ok){ ulanishNatija(karta, 'Xato: ' + r.sabab, false); t.disabled = false; return; }
            ulanishNatija(karta, r.xabar, true);
            if(r.kod_kerak){ $('#tvKodQator').classList.remove('hidden'); $('#tvKod').focus(); }
            else paintUlanish();
          }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
          t.disabled = false;
        };
      });
    }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
    qidir.disabled = false;
  };

  const tasdiq = $('#tvTasdiq');
  if(tasdiq) tasdiq.onclick = async () => {
    const karta = tasdiq.closest('.ulanish-karta');
    ulanishNatija(karta, 'Kod tekshirilmoqda…', true);
    try{
      const d = await (await fetch('/api/ulanish/tv/tasdiq', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({kod: $('#tvKod').value})})).json();
      ulanishNatija(karta, d.ok ? d.xabar : ('Xato: ' + d.sabab), d.ok);
      if(d.ok) setTimeout(paintUlanish, 900);
    }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
  };

  const saqla = $('#tgSaqla');
  if(saqla) saqla.onclick = async () => {
    const karta = saqla.closest('.ulanish-karta');
    const token = $('#tgToken').value.trim();
    if(!token){ ulanishNatija(karta, 'Tokenni joylang.', false); return; }
    ulanishNatija(karta, 'Tekshirilmoqda…', true);
    try{
      const d = await (await fetch('/api/ulanish/telegram', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({token})})).json();
      if(d.ok && d.ulangan){ ulanishNatija(karta, 'Ulandi: @' + d.bot, true); setTimeout(paintUlanish, 700); }
      else ulanishNatija(karta, 'Xato: ' + (d.sabab || 'token qabul qilinmadi'), false);
    }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
  };

  const ochir = $('#tgOchir');
  if(ochir) ochir.onclick = async () => {
    await fetch('/api/ulanish/telegram', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({clear:true})}).catch(()=>{});
    paintUlanish();
  };

  const suhbat = $('#tgSuhbat');
  if(suhbat) suhbat.onclick = async () => {
    const karta = suhbat.closest('.ulanish-karta');
    try{
      const d = await (await fetch('/api/ulanish/telegram/suhbatlar')).json();
      const s = d.suhbatlar || [];
      $('#tgRoyxat').innerHTML = s.length
        ? s.map(x => '<div class="ulanish-qurilma"><span>' + esc(x.nom) + '</span><code style="font-size:10.5px">' + x.id + '</code></div>').join('')
        : '<div class="ulanish-yordam">Hali hech kim botga yozmagan.</div>';
      ulanishNatija(karta, s.length + ' suhbat', true);
    }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
  };

  /* ── Google Sheets: mijoz fayli → ruxsat → avto-yozuv ── */
  const shKarta = () => document.querySelector('.ulanish-karta:has(#shMijoz), ' +
    '.ulanish-karta:has(#shRuxsat), .ulanish-karta:has(#shAvto)') ||
    [...document.querySelectorAll('.ulanish-karta')].find(k => k.textContent.includes('Google Sheets'));

  /* 1 · Skript kodini nusxalash */
  const shKodOl = $('#shKodOl');
  if(shKodOl) shKodOl.onclick = async () => {
    const karta = shKarta();
    try{
      const d = await (await fetch('/api/ulanish/sheets/skript')).json();
      if(!d.ok){ ulanishNatija(karta, 'Xato: ' + (d.sabab||''), false); return; }
      await navigator.clipboard.writeText(d.kod);
      shKodOl.textContent = '1 · Nusxalandi ✓';
      ulanishNatija(karta, 'Kod nusxalandi. Endi 2-tugmani bosing.', true);
      setTimeout(() => { shKodOl.textContent = '1 · Kodni nusxalash'; }, 3000);
    }catch(e){ ulanishNatija(karta, 'Nusxalab bo‘lmadi: ' + e.message, false); }
  };

  /* 2 · Apps Script muharririni brauzer panelida ochish.
     `script.new` — Google'ning rasmiy qisqa manzili, to'g'ridan-to'g'ri yangi
     loyiha muharririni ochadi. `script.google.com/home/...` esa kirilmagan
     bo'lsa hujjat sahifasiga yo'naltirib yuboradi. */
  const shSkriptOch = $('#shSkriptOch');
  if(shSkriptOch) shSkriptOch.onclick = async () => {
    toggleSidebar(false);
    openBrauzer();
    await brauzerOch('https://script.new');
  };

  /* 3 · Deploy manzilini saqlash va darrov sinash */
  const shSkriptSaqla = $('#shSkriptSaqla');
  if(shSkriptSaqla) shSkriptSaqla.onclick = async () => {
    const karta = shKarta();
    const url = $('#shSkriptUrl').value.trim();
    if(!url){ ulanishNatija(karta, 'Deploy bergan manzilni joylang.', false); return; }
    ulanishNatija(karta, 'Sinab ko‘rilmoqda…', true);
    try{
      const d = await (await fetch('/api/ulanish/sheets/skript', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({url})})).json();
      if(d.ok){ ulanishNatija(karta, 'Ulandi ✅', true); setTimeout(paintUlanish, 800); }
      else ulanishNatija(karta, d.sabab || 'ulanmadi', false);
    }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
  };

  const shAvtoSaqla = $('#shAvtoSaqla');
  if(shAvtoSaqla) shAvtoSaqla.onclick = async () => {
    const karta = shKarta();
    const jadval = $('#shAvto').value.trim();
    if(!jadval){ ulanishNatija(karta, 'Jadval havolasini joylang.', false); return; }
    ulanishNatija(karta, 'Ulanmoqda va birinchi yuborish ketmoqda…', true);
    try{
      const d = await (await fetch('/api/ulanish/sheets/avto', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({jadval})})).json();
      const s = d.sinxron || {};
      if(d.ok && s.ok){ ulanishNatija(karta, 'Tayyor — ' + s.qator + ' amal yuborildi.', true);
                        setTimeout(paintUlanish, 900); }
      else ulanishNatija(karta, 'Xato: ' + (s.sabab || d.sabab || ''), false);
    }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
  };

  const shSinxron = $('#shSinxron');
  if(shSinxron) shSinxron.onclick = async () => {
    const karta = shKarta();
    ulanishNatija(karta, 'Yuborilmoqda…', true);
    try{
      const d = await (await fetch('/api/ulanish/sheets/sinxron', {method:'POST'})).json();
      ulanishNatija(karta, d.ok ? (d.qator + ' amal yuborildi ✅') : ('Xato: ' + d.sabab), d.ok);
      if(d.ok) setTimeout(paintUlanish, 900);
    }catch(e){ ulanishNatija(karta, 'Xato: ' + e.message, false); }
  };

  const shAvtoOchir = $('#shAvtoOchir');
  if(shAvtoOchir) shAvtoOchir.onclick = async () => {
    await fetch('/api/ulanish/sheets/avto', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({jadval:''})}).catch(()=>{});
    paintUlanish();
  };

  const shUzish = $('#shUzish');
  if(shUzish) shUzish.onclick = async () => {
    if(!confirm('Ulanishni uzasizmi? Avto-yozuv ham to‘xtaydi.')) return;
    await fetch('/api/ulanish/sheets/skript', {method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({clear:true})}).catch(()=>{});
    paintUlanish();
  };

  const br = $('#ulanishBrauzer');
  if(br) br.onclick = () => { toggleSidebar(false); openBrauzer(); };
}

if($('#ulanishYangila')) $('#ulanishYangila').onclick = paintUlanish;

function jobMap(){ try { return JSON.parse(localStorage.getItem('agv_jobmap') || '{}'); } catch(e) { return {}; } }
function setJobMap(m){ try { localStorage.setItem('agv_jobmap', JSON.stringify(m)); } catch(e) {} }
function linkJob(sid, jid){
  if(!sid) return;
  const m = jobMap();
  if(jid) m[sid] = jid; else delete m[sid];
  setJobMap(m);
}
function sessionOfJob(jid){ const m = jobMap(); return Object.keys(m).find(k => m[k] === jid) || null; }

function liveMount(){
  if(!LIVE || LIVE.ui) return;
  const b = addMsgToUI('model', '', true);
  const wrap = b.parentElement;
  wrap.classList.add('working');
  wrap.dataset.agentComplete = 'false';
  b.innerHTML = '';
  /* Kartani oldindan chiqarmaymiz: savolda shunchaki "video"/"rasm" so'zi
     bo'lgani "tayyor fayl chiqadi" degani emas. Rasm biriktirilgan bo'lsa —
     ko'rsatamiz; aks holda karta faqat haqiqiy visual qadam kelganda paydo bo'ladi. */
  const visualEl = (LIVE.visual && LIVE.sourceImage) ? makeVisualProgressCard(LIVE.sourceImage) : null;
  if(visualEl) b.appendChild(visualEl);
  /* Reja va vosita rasmlari javob matnidan YUQORIDA turadi: ular jarayon,
     javob emas. Shunda yakuniy javob pastda toza ko'rinadi. */
  const rejaEl = document.createElement('div'); b.appendChild(rejaEl);
  const oqimEl = document.createElement('div'); b.appendChild(oqimEl);
  const bodyEl = document.createElement('div'); b.appendChild(bodyEl);
  const think  = makeThinking(); b.appendChild(think.el);
  think.start(LIVE.startedAt);
  if(LIVE.acts.length) think.phase(LIVE.acts[LIVE.acts.length-1]);
  LIVE.ui = { b, wrap, visualEl, rejaEl, oqimEl, bodyEl, think };
  paintReja(); paintOqim();
  livePaint();
}

/* Jonli reja — agent qadamlarni belgilab boradi, foydalanuvchi qayerdaligini ko'radi */
function paintReja(){
  if(!LIVE || !LIVE.ui || !LIVE.ui.rejaEl) return;
  const reja = LIVE.reja || [];
  if(!reja.length){ LIVE.ui.rejaEl.innerHTML = ''; return; }
  const tayyor = reja.filter(q => q.holat === 'tayyor').length;
  const belgi = { tayyor: '✓', ishlanmoqda: '●' };
  LIVE.ui.rejaEl.innerHTML =
    '<div class="reja-panel"><div class="reja-bosh">🗒️ <b>Reja</b>' +
    '<span>' + tayyor + '/' + reja.length + '</span></div>' +
    reja.map(q => '<div class="reja-qator ' + esc(q.holat || '') + '"><i>' +
      (belgi[q.holat] || '') + '</i><span>' + esc(q.matn || '') + '</span></div>').join('') +
    '</div>';
}

/* ══════ ISH OQIMI ══════
   Agentning har bir xom qadamini ro'yxatga to'kib tashlash o'qishga og'ir.
   Shuning uchun: izoh — alohida gap, undan keyingi vositalar esa bitta
   yig'ma qatorga yig'iladi ("2 ta buyruq bajarildi, hisob.py tahrirlandi
   +12 −3"). Bosilsa ichidagi qadamlar ochiladi.                            */

/* Bir turdagi qadamlar nechta ekanini o'zbekcha jumlaga aylantiradi */
function oqimXulosa(qadamlar){
  const sanoq = {}, fayllar = new Map();
  let rasm = 0;
  for(const q of qadamlar){
    if(q.tur === 'rasm-korish'){ rasm++; continue; }
    if(q.fayl){
      const f = fayllar.get(q.fayl.nom) || {amallar: new Set()};
      f.amallar.add(q.fayl.amal);
      fayllar.set(q.fayl.nom, f);
      continue;
    }
    sanoq[q.tur] = (sanoq[q.tur] || 0) + 1;
  }
  const bolaklar = [];
  let faylBilanBoshlandi = false;
  if(fayllar.size === 1){
    const [nom, f] = [...fayllar.entries()][0];
    bolaklar.push(nom + ' ' + [...f.amallar].join(' va '));
    faylBilanBoshlandi = true;      // fayl nomiga bosh harf berilmaydi
  } else if(fayllar.size > 1){
    bolaklar.push(fayllar.size + ' ta fayl o‘zgartirildi');
  }
  const jadval = [
    ['oqish',     n => n + ' ta fayl o‘qildi'],
    ['qidiruv',   n => n === 1 ? 'qidiruv o‘tkazildi' : n + ' marta qidirildi'],
    ['buyruq',    n => n === 1 ? '1 ta buyruq bajarildi' : n + ' ta buyruq bajarildi'],
    ['brauzer',   n => 'saytda ' + n + ' ta amal'],
    ['ekran',     n => 'ekranda ' + n + ' ta amal'],
    ['web',       n => n === 1 ? 'internetdan ma‘lumot olindi' : n + ' marta internetdan qidirildi'],
    ['hisob',     n => n + ' ta daftar amali'],
    ['rasm',      n => n === 1 ? 'rasm yaratildi' : n + ' ta rasm yaratildi'],
    ['yordamchi', n => n === 1 ? 'yordamchi agent ishladi' : n + ' ta yordamchi ishladi'],
    ['reja',      n => 'reja yangilandi'],
    ['qadam',     n => n + ' ta qadam bajarildi'],
  ];
  for(const [kalit, gap] of jadval){ if(sanoq[kalit]) bolaklar.push(gap(sanoq[kalit])); }
  if(rasm) bolaklar.push(rasm === 1 ? 'skrinshot olindi' : rasm + ' ta skrinshot olindi');
  if(!bolaklar.length) return qadamlar.length + ' ta qadam';
  const matn = bolaklar.join(', ');
  return faylBilanBoshlandi ? matn : matn.charAt(0).toUpperCase() + matn.slice(1);
}

function oqimStat(qadamlar){
  let q = 0, o = 0;
  for(const x of qadamlar){ if(x.fayl){ q += x.fayl.qoshildi || 0; o += x.fayl.ochirildi || 0; } }
  if(!q && !o) return '';
  return '<span class="oqim-stat"><b>+' + q + '</b><i>−' + o + '</i></span>';
}

const OQIM_CHEV = '<svg class="oqim-chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';

/* Bitta chizuvchi ikki joyga xizmat qiladi: jonli ish va tarixdan
   qayta ochilgan suhbat. Farqi faqat ochish/yopish tugmasida — jonlisi
   qayta chizilgani uchun holatni ma'lumotda saqlaydi, tarixdagisi esa
   to'g'ridan-to'g'ri DOM'ni ochib yopadi. */
function oqimHTML(oqim, tarix=false, jonli=false){
  if(!oqim || !oqim.length) return '';
  const oxirgiGuruh = oqim.map(x => x.tur).lastIndexOf('guruh');
  return '<div class="oqim">' + oqim.map((x, i) => {
    if(x.tur === 'izoh')
      return '<div class="oqim-izoh">' + esc(x.matn) + '</div>';
    if(x.tur === 'rasm')
      return '<figure class="qadam-rasm"><img src="' + esc(x.url) + '" alt="' + esc(x.izoh) +
             '" onclick="window.open(this.src,\'_blank\')"><figcaption>' + esc(x.izoh) +
             '</figcaption></figure>';
    if(x.tur === 'videolar') return ytRoyxat(x.videolar);
    const faol = jonli && i === oxirgiGuruh;
    const bosish = tarix ? 'oqimDomOchYop(this)' : 'oqimOchYop(' + i + ')';
    return '<button type="button" class="oqim-guruh' + (x.ochiq ? ' ochiq' : '') +
             (faol ? ' faol' : '') + '" onclick="' + bosish + '">' +
             OQIM_CHEV +
             '<span class="oqim-xulosa">' + esc(oqimXulosa(x.qadamlar)) + '</span>' +
             oqimStat(x.qadamlar) +
           '</button>' +
           '<div class="oqim-tafsilot' + (x.ochiq ? ' on' : '') + '">' +
             x.qadamlar.map(q => '<div class="oqim-qadam"><span>' + esc(q.yorliq) + '</span>' +
               (q.izoh ? '<em>' + esc(q.izoh) + '</em>' : '') + '</div>').join('') +
           '</div>';
  }).join('') + '</div>';
}

/* ── Oqimni QISMLAB chizish ──────────────────────────────────────────────
   Ilgari har bir qadamda butun oqim `innerHTML` bilan qaytadan chizilardi.
   Buning oqibati: rasm va video elementlari har safar yo'q qilinib qayta
   yaratilar, ya'ni qaytadan yuklanar edi — ekranda narsalar miltillab
   yo'qolib-paydo bo'lardi va scroll sakrardi.

   Endi har bir oqim yozuviga bitta DOM tugun to'g'ri keladi: yangi yozuv
   qo'shiladi, o'zgargani joyida yangilanadi, rasm va videolarga esa umuman
   tegilmaydi. */
function oqimTugun(x, i){
  const el = document.createElement('div');
  el.dataset.oqim = i;
  if(x.tur === 'izoh'){
    el.className = 'oqim-izoh';
    el.textContent = x.matn || '';
    return el;
  }
  if(x.tur === 'rasm'){
    el.className = 'oqim-orin';
    el.innerHTML = '<figure class="qadam-rasm"><img src="' + esc(x.url) + '" alt="' +
      esc(x.izoh) + '" onclick="window.open(this.src,\'_blank\')"><figcaption>' +
      esc(x.izoh) + '</figcaption></figure>';
    return el;
  }
  if(x.tur === 'videolar'){
    el.className = 'oqim-orin';
    el.innerHTML = ytRoyxat(x.videolar);
    return el;
  }
  el.className = 'oqim-orin';
  el.innerHTML =
    '<button type="button" class="oqim-guruh" onclick="oqimOchYop(' + i + ')">' +
      OQIM_CHEV + '<span class="oqim-xulosa"></span><span class="oqim-stat-orin"></span>' +
    '</button><div class="oqim-tafsilot"></div>';
  return el;
}

/* Guruh tuguni ichidagi o'zgaruvchan qismlarni yangilaydi (butun tugunni emas) */
function oqimGuruhYangila(el, x, faol){
  const tugma = el.querySelector('.oqim-guruh');
  const xulosa = el.querySelector('.oqim-xulosa');
  const statOrin = el.querySelector('.oqim-stat-orin');
  const tafsilot = el.querySelector('.oqim-tafsilot');

  const yangiXulosa = oqimXulosa(x.qadamlar);
  if(xulosa.textContent !== yangiXulosa) xulosa.textContent = yangiXulosa;

  const yangiStat = oqimStat(x.qadamlar);
  if(statOrin.dataset.stat !== yangiStat){
    statOrin.dataset.stat = yangiStat;
    statOrin.innerHTML = yangiStat;
  }

  tugma.classList.toggle('ochiq', Boolean(x.ochiq));
  tugma.classList.toggle('faol', Boolean(faol));
  tafsilot.classList.toggle('on', Boolean(x.ochiq));

  /* Qadam qatorlari faqat qo'shiladi — borlariga tegilmaydi */
  for(let j = tafsilot.children.length; j < x.qadamlar.length; j++){
    const q = x.qadamlar[j];
    const qator = document.createElement('div');
    qator.className = 'oqim-qadam';
    qator.innerHTML = '<span>' + esc(q.yorliq) + '</span>' +
                      (q.izoh ? '<em>' + esc(q.izoh) + '</em>' : '');
    tafsilot.appendChild(qator);
  }
}

function paintOqim(){
  if(!LIVE || !LIVE.ui || !LIVE.ui.oqimEl) return;
  const joy = LIVE.ui.oqimEl;
  const oqim = LIVE.oqim || [];
  let idish = joy.firstElementChild;
  if(!idish || !idish.classList.contains('oqim')){
    joy.innerHTML = '';
    idish = document.createElement('div');
    idish.className = 'oqim';
    joy.appendChild(idish);
  }
  const oxirgiGuruh = oqim.map(x => x.tur).lastIndexOf('guruh');
  for(let i = 0; i < oqim.length; i++){
    let el = idish.children[i];
    if(!el){
      el = oqimTugun(oqim[i], i);
      idish.appendChild(el);
    }
    if(oqim[i].tur === 'guruh')
      oqimGuruhYangila(el, oqim[i], !LIVE.done && i === oxirgiGuruh);
  }
}

function oqimOchYop(i){
  if(!LIVE || !LIVE.oqim || !LIVE.oqim[i]) return;
  LIVE.oqim[i].ochiq = !LIVE.oqim[i].ochiq;
  paintOqim();       // faqat shu guruhning sinflari o'zgaradi
}

function oqimDomOchYop(tugma){
  tugma.classList.toggle('ochiq');
  const tafsilot = tugma.nextElementSibling;
  if(tafsilot && tafsilot.classList.contains('oqim-tafsilot'))
    tafsilot.classList.toggle('on');
}

/* Yangi qadam oqimga tushadi: ochiq guruh bo'lsa unga qo'shiladi, aks holda
   yangi guruh ochiladi. Izoh kelganda guruh yopiladi — keyingi vositalar
   yangi izohga tegishli bo'ladi. */
function oqimQadam(qadam){
  if(!LIVE) return;
  LIVE.oqim = LIVE.oqim || [];
  const oxirgi = LIVE.oqim[LIVE.oqim.length - 1];
  if(!oxirgi || oxirgi.tur !== 'guruh')
    LIVE.oqim.push({tur: 'guruh', qadamlar: [], ochiq: false});
  LIVE.oqim[LIVE.oqim.length - 1].qadamlar.push(qadam);
  paintOqim();
}

function oqimIzoh(matn){
  if(!LIVE || !matn) return;
  LIVE.oqim = LIVE.oqim || [];
  LIVE.oqim.push({tur: 'izoh', matn: matn});
  paintOqim();
}

function oqimRasm(url, izoh){
  if(!LIVE) return;
  LIVE.oqim = LIVE.oqim || [];
  LIVE.oqim.push({tur: 'rasm', url: url, izoh: izoh});
  paintOqim();
}

/* Qidiruv topgan videolar oqimga karta panjarasi bo'lib tushadi */
function oqimVideolar(videolar){
  if(!LIVE || !videolar || !videolar.length) return;
  LIVE.oqim = LIVE.oqim || [];
  LIVE.oqim.push({tur: 'videolar', videolar: videolar});
  paintOqim();
}

function liveUnmount(){
  if(LIVE && LIVE.ui){ LIVE.ui.think.stop(); LIVE.ui = null; }
}

function livePaint(){
  if(!LIVE || !LIVE.ui) return;
  const { bodyEl } = LIVE.ui;
  bodyEl.innerHTML = LIVE.finalText ? renderMD(LIVE.finalText) : '';
  scrollDown();
  setTimeout(initExcelWidgets, 20);
}

function makeVisualProgressCard(sourceImage){
  const el = document.createElement('div');
  el.className = 'visual-progress-card';
  const preview = sourceImage ? '<img class="visual-progress-source" src="' + esc(sourceImage) + '" alt="Biriktirilgan reference rasm"><div class="visual-progress-icon">✦</div>' : '<div class="visual-progress-icon">✦</div>';
  el.innerHTML = '<div class="visual-progress-preview">' + preview + '</div><div class="visual-progress-meta"><i class="visual-progress-dot"></i><div class="visual-progress-copy"><strong>Tayyorlanmoqda</strong><span>Rasm yoki video ustida ish ketmoqda…</span></div></div>';
  return el;
}

function paintVisualProgress(action){
  if(!LIVE || !LIVE.ui) return;
  if(!LIVE.ui.visualEl){
    /* Faqat haqiqiy rasm/video qadami kelganda kartani qo'yamiz */
    if(!LIVE.visual || !/🎨|🎬|🎞️/.test(String(action || ''))) return;
    const el = makeVisualProgressCard(LIVE.sourceImage);
    LIVE.ui.b.insertBefore(el, LIVE.ui.bodyEl);
    LIVE.ui.visualEl = el;
  }
  const status = LIVE.ui.visualEl.querySelector('.visual-progress-copy span');
  const low = String(action || '').toLowerCase();
  if(low.includes('inson motion')) status.textContent = 'Haqiqiy image-to-video imkoniyati tekshirilmoqda — 2D qatlam qabul qilinmaydi…';
  else if(low.includes('video') || low.includes('animat')) status.textContent = 'Yangi video sahnalari render qilinmoqda…';
  else if(low.includes('rasm') || low.includes('image')) status.textContent = 'Rasm yaratish yoki reference rasm tahriri bajarilmoqda…';
  else if(low.includes('o\'qilyapti') || low.includes('read')) status.textContent = 'Reference fayl va kerakli elementlar tahlil qilinmoqda…';
  else status.textContent = 'Visual ishlab chiqarish jarayoni davom etmoqda…';
}

function finishVisualProgress(success){
  if(!LIVE || !LIVE.ui || !LIVE.ui.visualEl) return;
  const el = LIVE.ui.visualEl;
  const status = el.querySelector('.visual-progress-copy span');
  if(success){
    el.classList.add('done');
    status.textContent = 'Jarayon yakunlandi — tayyor fayl quyidagi javobda ko‘rsatiladi.';
  } else {
    status.textContent = 'Jarayon yakunlanmadi — agent javobidagi xatoni tekshiring.';
  }
}

/* Token oqimini har bir bo'lakda qayta chizsak markdown render sekinlashadi —
   shuning uchun chizishni ~50ms ga guruhlaymiz: matn silliq "yozilib" boradi. */
let livePaintTimer = null;
function livePaintSoon(){
  if(livePaintTimer) return;
  livePaintTimer = setTimeout(() => { livePaintTimer = null; livePaint(); }, 50);
}

function liveEvent(o){
  if(!LIVE) return;
  if(o.job){
    LIVE.jobId = o.job;
    if(o.visual !== undefined) LIVE.visual = Boolean(o.visual);
    if(o.trueMotion !== undefined) LIVE.trueMotion = Boolean(o.trueMotion);
    if(o.started) LIVE.startedAt = o.started * 1000;
    linkJob(LIVE.sid, o.job);
    if(LIVE.ui) LIVE.ui.think.since(LIVE.startedAt);
    renderHistory(); paintJobBadge();
    return;                       // sarlavha hodisasi serverda saqlanmaydi
  }
  /* Serverda saqlanadigan har bir hodisani sanaymiz — aloqa uzilsa
     aynan shu indeksdan davom ettiramiz (ping saqlanmaydi, sanalmaydi). */
  if(!o.ping) LIVE.evIdx = (LIVE.evIdx || 0) + 1;

  if(o.ping && LIVE.ui) LIVE.ui.think.beat();

  if(o.delta){
    /* ChatGPT'dagidek: javob matni so'zma-so'z oqib chiqadi */
    LIVE.streamText = (LIVE.streamText || '') + o.delta;
    LIVE.finalText = LIVE.streamText;
    if(LIVE.ui) LIVE.ui.think.beat();
    livePaintSoon();
  }
  if(o.reason){
    LIVE.reasonText = (LIVE.reasonText || '') + o.reason;
    if(LIVE.ui){ LIVE.ui.think.beat(); LIVE.ui.think.phase('🧠 ' + LIVE.reasonText.slice(-90)); }
  }
  if(o.reset){
    /* Vositadan oldingi izoh — javob emas, "hozir nima qilmoqchiman" gapi.
       Uni ish oqimiga o'tkazamiz va javob oynasini tozalaymiz: yakuniy
       javob pastda toza chiqadi. */
    if(o.note){
      LIVE.acts.push('💭 ' + o.note);
      oqimIzoh(o.note);
      if(LIVE.ui) LIVE.ui.think.phase('💭 ' + o.note);
      paintDesktopLiveActions();
    }
    LIVE.streamText = '';
    LIVE.finalText = '';
    livePaint();
  }
  if(o.reja){
    LIVE.reja = o.reja;
    paintReja();
  }
  if(o.brauzer){
    brauzerHodisa(o.brauzer, o.action ? (o.detail ? o.action + ' — ' + o.detail : o.action) : '');
  }
  if(o.jadval) paintJadval(o.jadval);
  if(o.action){
    const step = o.detail ? o.action + ' — ' + o.detail : o.action;
    LIVE.acts.push(step);
    /* Sol vositalari qadam turini yuboradi. CLI agentlari (Composer, Codex)
       yubormaydi — ularni umumiy "qadam" deb belgilaymiz, aks holda hammasi
       noto'g'ri turkumga tushib qoladi. */
    oqimQadam({
      yorliq: o.action, izoh: o.detail || '',
      tur: o.rasm ? 'rasm-korish' : (o.tur || 'qadam'),
      fayl: o.fayl || null
    });
    if(LIVE.ui){ LIVE.ui.think.beat(); LIVE.ui.think.phase(step); paintVisualProgress(o.action); }
    livePaint(); paintJobBadge();
    paintDesktopLiveActions();
  }
  /* Rasm va videolar qadamdan KEYIN qo'yiladi — aks holda ular o'zini
     yuzaga chiqargan qadam guruhidan yuqorida turib qoladi. */
  if(o.rasm){
    oqimRasm(o.rasm, (o.action || 'Skrinshot') + (o.detail ? ' — ' + o.detail : ''));
    scrollDown();
  }
  if(o.videolar){ oqimVideolar(o.videolar); scrollDown(); }
  // Daftarga amal yozildi — suhbatga chek chizamiz
  if(o.chek) chekChiz(o.chek);
  if(o.error) LIVE.finalText = (LIVE.finalText ? LIVE.finalText+'\n' : '') + '⚠️ ' + o.error;
  if(o.done){
    if(o.text) LIVE.finalText = o.text;
    LIVE.done = true;
    convo = true;
    if(livePaintTimer){ clearTimeout(livePaintTimer); livePaintTimer = null; }
    paintDesktopLiveActions();
  }
}

/* Oqim uzilsa (internet, uyqu rejimi, server band) — ish tugamagan bo'lsa qayta ulanamiz */
async function runLive(firstRes){
  let res = firstRes;
  for(let attempt = 0; attempt < 5; attempt++){
    try {
      await driveStream(res);
    } catch(e) {
      if(LIVE){
        LIVE.finalText = '⚠️ ' + (e.message || 'Server javobini o‘qib bo‘lmadi.');
        LIVE.done = true;
      }
      return;
    }
    if(!LIVE || LIVE.done || !LIVE.jobId) return;
    await new Promise(r => setTimeout(r, 1500));
    try {
      res = await fetch('/api/job?id=' + encodeURIComponent(LIVE.jobId) + '&from=' + (LIVE.evIdx || 0));
    } catch(e) {
      LIVE.finalText = '⚠️ Jarayon uzildi: ' + (e.message || 'serverga qayta ulanib bo‘lmadi.');
      LIVE.done = true;
      return;
    }
  }
  if(LIVE && !LIVE.done){
    LIVE.finalText = '⚠️ Video jarayoni yakunlangani tasdiqlanmadi. Tayyor MP4 fayl topilmadi.';
    LIVE.done = true;
  }
}

async function driveStream(res){
  if(!res.ok){
    let message = 'Server xatosi (' + res.status + ')';
    try {
      const data = await res.json();
      message = data.error || message;
    } catch(e) {}
    throw new Error(message);
  }
  const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = '';
  while(true){
    const { value, done } = await reader.read();
    if(done) break;
    buf += dec.decode(value, {stream:true});
    let i;
    while((i = buf.indexOf('\n\n')) >= 0){
      const chunk = buf.slice(0, i); buf = buf.slice(i+2);
      for(const ln of chunk.split('\n')){
        if(!ln.startsWith('data:')) continue;
        let o; try { o = JSON.parse(ln.slice(5).trim()); } catch(e) { continue; }
        liveEvent(o);
      }
    }
  }
}

function liveFinish(){
  if(!LIVE) return;
  const sid = LIVE.sid;
  const text = LIVE.finalText || '⚠️ Jarayon natijasiz tugadi. Tayyor MP4 fayl topilmadi.';
  LIVE.finalText = text;
  if(LIVE.ui){
    finishVisualProgress(!text.startsWith('⚠️'));
    LIVE.ui.think.stop();
    LIVE.ui.wrap.classList.remove('working');
    paintOqim();           // ish tugadi — oxirgi guruhdan "faol" belgisi olinadi
    livePaint();
    LIVE.ui.wrap.dataset.agentComplete = 'true';
    LIVE.ui.wrap.dataset.agentText = text;
    LIVE.ui.wrap.dataset.agentCompletedAt = String(Date.now());
    LIVE.ui = null;
  }
  if(!text.startsWith('⚠️')) offerVoicePlayback(text);
  linkJob(sid, null);
  try {
    saveMessageToHistory('model', text, null, sid, LIVE.oqim);
  } catch (error) {
    console.warn('Agent javobi tarixga saqlanmadi, lekin suhbat davom etadi.', error);
  }
  DESKTOP_LAST = { actions: LIVE.acts.slice(), endedAt: Date.now() };
  LIVE = null;
  paintJobBadge(); renderHistory(); paintDesktopLiveActions();
  loadHisob();          // javob tugadi — raqamlar o'zgargan bo'lishi mumkin
}

/* Sarlavhadagi umumiy indikator — qaysi suhbatda bo'lsangiz ham ko'rinadi */
let jobBadgeTimer = null;
const BASE_TITLE = document.title;
function paintJobBadge(){
  const el = $('#jobBadge');
  if(!el) return;
  const stopBtn = $('#jobStop');
  if(!LIVE){
    el.classList.add('hidden');
    if(stopBtn) stopBtn.classList.add('hidden');
    document.title = BASE_TITLE;
    if(jobBadgeTimer){ clearInterval(jobBadgeTimer); jobBadgeTimer = null; }
    return;
  }
  document.title = '✦ ' + fmtDur(Date.now() - LIVE.startedAt) + ' · ishlayapti — MUHASIB';
  el.classList.remove('hidden');
  if(stopBtn) stopBtn.classList.toggle('hidden', !LIVE.jobId || LIVE.stopping);
  if(!el.dataset.built){
    el.innerHTML = GEM_SPARK + '<span class="jb-text">Ishlayapti…</span><span class="jb-time">0s</span>';
    el.dataset.built = '1';
  }
  el.querySelector('.jb-text').textContent =
    LIVE.stopping ? 'To\'xtatilmoqda…' : actPhase(LIVE.acts[LIVE.acts.length-1]);
  el.querySelector('.jb-time').textContent = fmtDur(Date.now() - LIVE.startedAt);
  el.title = (LIVE.sid && LIVE.sid !== activeSessionId)
    ? 'Ish davom etmoqda — o\'sha suhbatga o\'tish uchun bosing'
    : 'Ish davom etmoqda';
  if(!jobBadgeTimer) jobBadgeTimer = setInterval(paintJobBadge, 1000);
}

function goToLiveJob(){
  if(!LIVE) return;
  if(LIVE.sid && LIVE.sid !== activeSessionId) loadSession(LIVE.sid);
  else scrollDown(true);
}

/* Ishni to'xtatish — agent va u ishga tushirgan buyruqlar birga to'xtaydi */
async function stopLive(){
  if(!LIVE || LIVE.stopping) return;
  if(!LIVE.jobId){ return; }                 // hali server javob bermadi
  LIVE.stopping = true;
  document.querySelectorAll('.think-stop').forEach(b => { b.disabled = true; b.textContent = '⏳ To\'xtatilmoqda…'; });
  if(LIVE.ui) LIVE.ui.think.phase('__stop__');
  paintJobBadge();
  try{
    await fetch('/api/job/stop', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({id: LIVE.jobId})
    });
  }catch(e){}
  /* qolganini oqim o'zi yopadi: server "done" hodisasini yuboradi */
}

document.addEventListener('keydown', e => {
  if(e.key !== 'Escape') return;
  if(closeHeaderMenus()) return;
  if(brauzerOchiqmi()){ closeBrauzer(); return; }
  if(desktopLiveOpen()){ closeDesktopLive(); return; }
  if(!LIVE || LIVE.stopping) return;
  const modal = $('#faModal');
  if(modal && !modal.classList.contains('hidden')) return;   // modal ochiq bo'lsa tegmaymiz
  stopLive();
});

if($('#brauzerBtn')) $('#brauzerBtn').onclick = () => { closeHeaderMenus(); openBrauzer(); };
if($('#brauzerClose')) $('#brauzerClose').onclick = closeBrauzer;
if($('#brauzerRefresh')) $('#brauzerRefresh').onclick = refreshBrauzer;
if($('#brauzerGo')) $('#brauzerGo').onclick = () => brauzerOch($('#brauzerUrl').value);
if($('#brauzerBack')) $('#brauzerBack').onclick = async () => {
  try{
    const r = await fetch('/api/brauzer/och', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({orqaga:true})});
    const d = await r.json();
    if(d.url){ BRAUZER.url = d.url; $('#brauzerUrl').value = d.url; }
    if(d.sarlavha) $('#brauzerSarlavha').textContent = d.sarlavha;
  }catch(e){}
  refreshBrauzer();
};
if($('#brauzerDavom')) $('#brauzerDavom').onclick = brauzerDavomEt;
if($('#brauzerUrl')) $('#brauzerUrl').addEventListener('keydown', e => {
  if(e.key === 'Enter'){ e.preventDefault(); brauzerOch(e.target.value); }
});
if($('#brauzerModal')) {
  $('#brauzerModal').onclick = event => { if(event.target === $('#brauzerModal')) closeBrauzer(); };
}

if($('#desktopLiveBtn')) $('#desktopLiveBtn').onclick = openDesktopLive;
if($('#desktopLiveClose')) $('#desktopLiveClose').onclick = closeDesktopLive;
if($('#desktopLiveRefresh')) $('#desktopLiveRefresh').onclick = refreshDesktopLive;
if($('#desktopLiveAuto')) {
  $('#desktopLiveAuto').onclick = () => {
    try {
      localStorage.setItem('agv_desktop_live_auto', desktopLiveAutoEnabled() ? 'off' : 'on');
    } catch(e) {}
    paintDesktopLiveAuto();
  };
}
if($('#desktopLiveModal')) {
  $('#desktopLiveModal').onclick = event => {
    if(event.target === $('#desktopLiveModal')) closeDesktopLive();
  };
}

function closeHeaderMenus(exceptMenu=null){
  let closed = false;
  document.querySelectorAll('.clean-nav-menu').forEach(menu => {
    if(menu === exceptMenu) return;
    const dropdown = menu.querySelector('.clean-nav-dropdown');
    const trigger = menu.querySelector('.clean-nav-trigger');
    if(dropdown && dropdown.classList.contains('open')){
      dropdown.classList.remove('open');
      if(trigger) trigger.setAttribute('aria-expanded', 'false');
      closed = true;
    }
  });
  return closed;
}

document.querySelectorAll('.clean-nav-trigger').forEach(trigger => {
  trigger.onclick = event => {
    event.stopPropagation();
    const menu = trigger.closest('.clean-nav-menu');
    const dropdown = menu ? menu.querySelector('.clean-nav-dropdown') : null;
    if(!dropdown) return;
    const opening = !dropdown.classList.contains('open');
    closeHeaderMenus(menu);
    dropdown.classList.toggle('open', opening);
    trigger.setAttribute('aria-expanded', opening ? 'true' : 'false');
  };
});

document.querySelectorAll('.clean-nav-dropdown .clean-nav-item').forEach(item => {
  item.addEventListener('click', () => closeHeaderMenus());
});

document.addEventListener('click', event => {
  if(!event.target.closest('.clean-nav-menu')) closeHeaderMenus();
});

/* Sahifa yangilangandan keyin davom etayotgan ishga qayta ulanish */
let resumeBusy = false;
async function resumeJobs(){
  if(LIVE || resumeBusy) return;
  resumeBusy = true;
  try { await resumeJobsInner(); } finally { resumeBusy = false; }
}

async function resumeJobsInner(){
  let jobs = [];
  try {
    const r = await fetch('/api/jobs');
    jobs = (await r.json()).jobs || [];
  } catch(e) { return; }

  const runningIds = jobs.filter(j => j.state === 'running').map(j => j.id);
  const m = jobMap();                       // tugab ketgan ishlarni xaritadan tozalaymiz
  let changed = false;
  for(const sid of Object.keys(m)){ if(!runningIds.includes(m[sid])){ delete m[sid]; changed = true; } }
  if(changed) setJobMap(m);

  const job = jobs.find(j => j.state === 'running');
  if(!job) return;

  let sid = sessionOfJob(job.id);
  if(!sid){
    sid = activeSessionId || createNewSession().id;
    linkJob(sid, job.id);
    const session = getSessions().find(candidate => candidate.id === sid);
    const alreadySaved = Boolean(session && (session.messages || []).some(message =>
      message.role === 'user' && message.text === job.prompt
    ));
    if(job.prompt && !alreadySaved) saveMessageToHistory('user', job.prompt, null, sid);
  }

  LIVE = { jobId: job.id, sid, acts: [], finalText: '', streamText: '', evIdx: 0, startedAt: job.started * 1000, ui: null, visual: Boolean(job.visual), trueMotion: Boolean(job.trueMotion) };
  paintJobBadge();
  if(sid === activeSessionId){
    if(!chatArea.children.length) loadSession(sid);
    if(!LIVE.ui) liveMount();
    if(desktopLiveAutoEnabled()) openDesktopLive();
  }

  busy = true; $('#send').disabled = true;
  try {
    await runLive(await fetch('/api/job?id=' + encodeURIComponent(job.id) + '&from=0'));
  } catch(e) {
    if(LIVE) LIVE.finalText = (LIVE.finalText ? LIVE.finalText+'\n' : '') + '⚠️ Aloqa uzildi: ' + e.message;
  } finally {
    liveFinish();
    busy = false; $('#send').disabled = false;
  }
}

function audTag(p){
  return `<div class="chat-audio-wrap" style="margin:8px 0"><span style="font-size:12px;color:var(--muted);display:block;margin-bottom:4px">🎵 ${esc(p.split('/').pop())}</span><audio class="chat-audio" src="/api/file?path=${encodeURIComponent(p)}" controls preload="metadata" style="width:100%;max-width:400px;border-radius:12px"></audio></div>`;
}

/* Video fayl havolasini chatning o'zida o'ynaydigan pleyerga aylantiradi */
function vidTag(p){
  return `<video class="chat-video" src="/api/file?path=${encodeURIComponent(p)}" controls preload="metadata" playsinline></video>`;
}

/* YouTube kartasi. Pleyer o'rniga avval muqova chiziladi — bosilgandagina
   iframe qo'yiladi. Bu tez, toza va bir nechta video birga chiqqanda ham
   sahifani sekinlashtirmaydi. nocookie domeni kuzatuv cookie'sini qo'ymaydi. */
const YT_PLAY = '<span class="yt-play"><i><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></i></span>';

function ytTag(id, nom, kanal, vaqt){
  const sid = esc(id);
  const sarlavha = esc((nom || '').trim() || 'YouTube video');
  const past = [kanal, vaqt].filter(Boolean).map(esc).join(' · ');
  return '<figure class="yt-karta">' +
    '<button type="button" class="yt-muqova" data-yt="' + sid + '" ' +
            'title="' + sarlavha + '" onclick="ytOch(this)">' +
      /* maxresdefault — 1280x720, keng kartada ham aniq. Hamma videoda
         bo'lavermaydi, shuning uchun bo'lmasa hqdefault ga tushamiz
         (u 4:3, lekin `object-fit: cover` qora yo'llarni kesib tashlaydi). */
      '<img src="https://i.ytimg.com/vi/' + sid + '/maxresdefault.jpg" alt="" loading="lazy" ' +
        'onerror="this.onerror=null;this.src=\'https://i.ytimg.com/vi/' + sid + '/hqdefault.jpg\'">' +
      YT_PLAY + (vaqt ? '<span class="yt-vaqt">' + esc(vaqt) + '</span>' : '') +
    '</button>' +
    '<figcaption class="yt-meta"><span class="yt-meta-matn"><b>' + sarlavha + '</b>' +
      (past ? '<small>' + past + '</small>' : '') + '</span>' +
      '<a href="https://www.youtube.com/watch?v=' + sid + '" target="_blank" rel="noopener">YouTube ↗</a>' +
    '</figcaption></figure>';
}

/* Muqova bosilganda haqiqiy pleyerga almashadi */
function ytOch(tugma){
  const id = tugma.dataset.yt;
  const ramka = document.createElement('iframe');
  ramka.className = 'yt-ramka';
  ramka.src = 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0';
  ramka.title = tugma.title || 'YouTube video';
  ramka.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture; fullscreen';
  ramka.referrerPolicy = 'strict-origin-when-cross-origin';
  ramka.allowFullscreen = true;
  tugma.replaceWith(ramka);
}

/* Qidiruv natijalari — bir nechta video panjara bo'lib chiqadi */
function ytRoyxat(videolar){
  if(!videolar || !videolar.length) return '';
  return '<div class="yt-royxat">' +
    videolar.map(v => ytTag(v.id, v.sarlavha, v.kanal, v.davomiylik)).join('') +
    '</div>';
}

function imgTag(path, alt='Tayyor rasm'){
  let url = path.trim();
  if(url.startsWith('file://')) url = url.slice(7);
  if(url.startsWith('/')) url = '/api/file?path=' + encodeURIComponent(url);
  return `<img src="${url}" class="chat-img" alt="${alt}" onclick="openLightbox('${url}')" style="cursor:zoom-in">`;
}

function renderMD(text){
  if(!text) return '';
  let str = esc(text);

  /* ── Tayyor HTML bo'laklarini qo'riqlash ────────────────────────────────
     Keyingi almashtirishlar allaqachon yasalgan HTML ichiga kirib buzardi:
     masalan rasm-yo'li qoidasi YouTube kartasidagi `.../mqdefault.jpg` ni
     ushlab, uning o'rniga <img> qo'yardi — ekranda HTML matn bo'lib
     chiqib qolardi. Endi har bir tayyor bo'lak nishonga almashtiriladi va
     eng oxirida joyiga qaytariladi. */
  const saqlangan = [];
  const qot = html => '' + (saqlangan.push(html) - 1) + '';

  /* Kod bloklari birinchi qo'riqlanadi — ular ichidagi fayl yo'llari
     rasm yoki videoga aylanib ketmasin. */
  str = str.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(_, lang, code){
    const l = lang || 'code';
    return qot(`<div class="code-block"><div class="code-head"><span>${l}</span>` +
      `<button onclick="copyCode(this)">Nusxalash</button></div><pre><code>${code}</code></pre></div>`);
  });

  /* audio fayllar */
  str = str.replace(/\[[^\]]*\]\((?:file:\/\/)?(\/[^)\s]+\.(?:mp3|m4a|wav|aiff))\)/gi, (_, p) => qot(audTag(p)));
  str = str.replace(/`?(?:file:\/\/)?(\/[A-Za-z0-9_\-./ ]+\.(?:mp3|m4a|wav|aiff))`?/gi, (_, p) => qot(audTag(p)));

  /* video fayllar */
  str = str.replace(/\[[^\]]*\]\((?:file:\/\/)?(\/[^)\s]+\.(?:mp4|mov|webm|m4v))\)/gi, (_, p) => qot(vidTag(p)));
  str = str.replace(/`?(?:file:\/\/)?(\/[A-Za-z0-9_\-./ ]+\.(?:mp4|mov|webm|m4v))`?/gi, (_, p) => qot(vidTag(p)));

  /* YouTube havolasi — suhbatning o'zida ochiladigan kartaga aylanadi */
  str = str.replace(/\[([^\]]*)\]\((https?:\/\/(?:www\.|m\.)?(?:youtube\.com\/watch\?[^)\s]*v=|youtu\.be\/|youtube\.com\/shorts\/)([A-Za-z0-9_-]{11})[^)\s]*)\)/gi,
    (_, nom, url, id) => qot(ytTag(id, nom)));
  str = str.replace(/(?:^|\s)(https?:\/\/(?:www\.|m\.)?(?:youtube\.com\/watch\?\S*v=|youtu\.be\/|youtube\.com\/shorts\/)([A-Za-z0-9_-]{11})\S*)/gi,
    (hammasi, url, id) => (hammasi.startsWith(' ') ? ' ' : '') + qot(ytTag(id, '')));

  str = str.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => qot(imgTag(src, alt)));

  /* Agent oddiy fayl yo'lini yozsa ham yaratilgan rasm chatda ko'rinadi. */
  str = str.replace(/`?(?:file:\/\/)?(\/[A-Za-z0-9_\-./ ]+\.(?:png|jpe?g|webp|gif))`?/gi,
    (_, path) => qot(imgTag(path)));

  str = str.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  str = str.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  str = str.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  str = str.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  str = str.replace(/^\&gt;\s?(.*$)/gim, '<blockquote>$1</blockquote>');
  str = str.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  str = str.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  /* Markdown Table Parser & Header Title Capture */
  str = str.replace(/(?:(?:^|\n)((?:(?:<strong>|<h3>|<h2>|<h1>)?\s*([^\n|<>]+?\:?)\s*(?:<\/strong>|<\/h[123]>)?)?\s*\n)?)?((?:^|\n)[ \t]*\|[^\n]+\|[ \t]*\r?\n[ \t]*\|[\s\-:\t|]+\|[ \t]*\r?\n(?:[ \t]*\|[^\n]+\|[ \t]*(?:\r?\n|$)?)+)/gi, function(match, titleLine, titleRaw, tableBlock) {
    if (!tableBlock) return match;
    const lines = tableBlock.trim().split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length < 2) return match;
    
    // Check separator row
    if (!/^\|[\s\-:\t|]+\|$/.test(lines[1])) return match;
    
    const parseRow = row => row.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    const headers = parseRow(lines[0]);
    const bodyRows = lines.slice(2).map(parseRow);
    
    let titleText = "Fayldagi ma'lumotlar jadvali";
    if (titleRaw) {
      let t = titleRaw.replace(/<[^>]+>/g, '').replace(/\:$/, '').trim();
      if (t && t.length > 1 && !t.includes('|')) titleText = t;
    }
    
    let html = `<div class="chat-table-wrapper">
      <div class="chat-table-head">
        <span class="chat-table-icon">📊</span>
        <span class="chat-table-title">${titleText}</span>
      </div>
      <div class="chat-table-scroll">
        <table class="chat-table"><thead><tr>`;
    
    headers.forEach(h => { html += `<th>${h}</th>`; });
    html += '</tr></thead><tbody>';
    bodyRows.forEach(row => {
      html += '<tr>';
      row.forEach(c => { html += `<td>${c}</td>`; });
      html += '</tr>';
    });
    html += '</tbody></table></div></div>';
    return html;
  });

  /* Interactive Excel Widget for .xlsx files */
  str = str.replace(/\[([^\]]*)\]\(([^)]+)\)/gi, function(match, text, href) {
    let url = href.trim();
    let absPath = url.startsWith('file://') ? url.slice(7) : url;
    let cleanPath = absPath.split('?')[0].split('#')[0];
    if (!cleanPath.toLowerCase().endsWith('.xlsx')) {
      return match;
    }
    const fileName = cleanPath.split('/').pop() || 'mahsulotlar.xlsx';
    
    return `<div class="chat-excel-container" data-excel-path="${esc(absPath)}" data-filename="${esc(fileName)}">
      <div class="excel-top-bar">
        <div class="excel-title-group">
          <span class="excel-icon-badge">XLSX</span>
          <span class="excel-filename">${esc(fileName)}</span>
        </div>
        <a href="/api/file?path=${encodeURIComponent(absPath)}" download="${esc(fileName)}" class="excel-download-btn">
          📥 Excel yuklab olish
        </a>
      </div>
      <div class="excel-fx-bar">
        <span class="excel-cell-id">A1</span>
        <span class="excel-fx-symbol">fx</span>
        <input type="text" class="excel-fx-input" placeholder="Katakcha qiymati..." readonly>
      </div>
      <div class="excel-grid-viewport">
        <div class="excel-loading" style="padding:24px;text-align:center;color:var(--muted);font-size:12.5px;">⚡ Interaktiv Excel yuklanmoqda…</div>
      </div>
      <div class="excel-bottom-bar">
        <div class="excel-sheet-tab">Mahsulotlar</div>
        <div class="excel-status-info">Interaktiv Kassa Excel · Tahrirlash va ko'rish</div>
      </div>
    </div>`;
  });

  /* Links: HTTP & Generic File/Download Links */
  str = str.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, text, href) {
    let url = href.trim();
    if (url.startsWith('https://') || url.startsWith('http://')) {
      return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
    }
    let absPath = url.startsWith('file://') ? url.slice(7) : url;
    if (url.startsWith('file://') || url.startsWith('/')) {
      let downloadUrl = '/api/file?path=' + encodeURIComponent(absPath);
      let ext = absPath.split('.').pop().toLowerCase();
      if (['csv', 'pdf', 'docx', 'zip'].includes(ext)) {
        return `<a href="${downloadUrl}" target="_blank" download class="chat-file-btn"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> ${text}</a>`;
      }
      return `<a href="${downloadUrl}" target="_blank" rel="noopener">${text}</a>`;
    }
    return match;
  });

  str = str.replace(/^[\*\-]\s+(.*$)/gim, '<ul><li>$1</li></ul>');
  str = str.replace(/<\/ul>\n<ul>/g, '');
  
  const parts = str.split(/(<div class="chat-table-wrapper">[\s\S]*?<\/div>|<div class="chat-excel-container">[\s\S]*?<\/div>|<h[123]>[\s\S]*?<\/h[123]>|<ul>[\s\S]*?<\/ul>|<blockquote>[\s\S]*?<\/blockquote>)/g);
  str = parts.map(p => {
    if (p.startsWith('<div class="chat-table-wrapper"') || p.startsWith('<div class="chat-excel-container"') || p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<blockquote')) return p;
    return p.replace(/\n/g, '<br>');
  }).join('');

  /* Qo'riqlangan bo'laklarni joyiga qaytaramiz. Nishon atrofidagi ortiqcha
     <br> olib tashlanadi — aks holda har karta ostida bo'sh qator qoladi. */
  str = str.replace(/(?:<br>)?(\d+)(?:<br>)?/g, (_, i) => saqlangan[+i] || '');
  return str;
}

async function initExcelWidgets() {
  const containers = document.querySelectorAll('.chat-excel-container:not([data-loaded])');
  containers.forEach(async (container) => {
    container.setAttribute('data-loaded', 'true');
    const path = container.dataset.excelPath;
    const viewport = container.querySelector('.excel-grid-viewport');
    const fxInput = container.querySelector('.excel-fx-input');
    const cellIdSpan = container.querySelector('.excel-cell-id');
    const sheetTab = container.querySelector('.excel-sheet-tab');
    
    try {
      const res = await fetch('/api/excel/data?path=' + encodeURIComponent(path));
      const data = await res.json();
      
      if (!data.rows || data.rows.length === 0) {
        viewport.innerHTML = '<div style="padding:16px;color:var(--muted);text-align:center;">Jadval boʻsh</div>';
        return;
      }
      
      if (data.sheet && sheetTab) sheetTab.textContent = data.sheet;
      
      const rows = data.rows;
      let maxCols = 0;
      rows.forEach(r => { if (r.length > maxCols) maxCols = r.length; });
      
      let html = '<table class="excel-interactive-table"><thead><tr><th class="row-hdr"></th>';
      for (let c = 0; c < maxCols; c++) {
        const colLetter = String.fromCharCode(65 + c);
        html += `<th>${colLetter}</th>`;
      }
      html += '</tr></thead><tbody>';
      
      rows.forEach((row, rIdx) => {
        const rowNum = rIdx + 1;
        const isHeader = (rIdx === 0);
        html += `<tr><th class="row-hdr">${rowNum}</th>`;
        
        for (let cIdx = 0; cIdx < maxCols; cIdx++) {
          const val = row[cIdx] !== undefined ? row[cIdx] : '';
          const colLetter = String.fromCharCode(65 + cIdx);
          const cellId = `${colLetter}${rowNum}`;
          const isBold = isHeader ? 'font-weight:bold;background:var(--field);' : '';
          const align = (!isHeader && !isNaN(parseFloat(val.replace(/,/g,'')))) ? 'text-align:right;' : '';
          
          html += `<td contenteditable="true" data-cell="${cellId}" style="${isBold}${align}">${esc(val)}</td>`;
        }
        html += '</tr>';
      });
      html += '</tbody></table>';
      
      viewport.innerHTML = html;
      
      const table = viewport.querySelector('table');
      table.querySelectorAll('td').forEach(td => {
        td.addEventListener('focus', () => {
          table.querySelectorAll('td.selected').forEach(el => el.classList.remove('selected'));
          td.classList.add('selected');
          if (cellIdSpan) cellIdSpan.textContent = td.dataset.cell;
          if (fxInput) {
            fxInput.value = td.innerText;
            fxInput.removeAttribute('readonly');
          }
        });
        
        td.addEventListener('input', () => {
          if (fxInput && td.classList.contains('selected')) {
            fxInput.value = td.innerText;
          }
        });
      });
      
      if (fxInput) {
        fxInput.addEventListener('input', () => {
          const activeTd = table.querySelector('td.selected');
          if (activeTd) {
            activeTd.innerText = fxInput.value;
          }
        });
      }
      
    } catch(err) {
      viewport.innerHTML = '<div style="padding:16px;color:#ea4335;text-align:center;">Excel faylni yuklashda xato</div>';
    }
  });
}

function copyCode(btn){
  const code = btn.closest('.code-block').querySelector('code').innerText;
  navigator.clipboard.writeText(code).then(()=>{
    const old = btn.textContent;
    btn.textContent = '✓ Nusxalandi!';
    setTimeout(()=> btn.textContent = old, 2000);
  });
}

let currentImage = null;

const attachBtn = $('#attachBtn');
const fileInput = $('#fileInput');
const imgPreviewBar = $('#imgPreviewBar');
const imgPreview = $('#imgPreview');
const removeImg = $('#removeImg');

if(attachBtn && fileInput){
  attachBtn.onclick = () => fileInput.click();
  fileInput.onchange = e => {
    if(e.target.files && e.target.files[0]) processFile(e.target.files[0]);
  };
}
if(removeImg){
  removeImg.onclick = clearAttachedImage;
}

function clearAttachedImage(){
  currentImage = null;
  if(imgPreview) imgPreview.src = '';
  if(imgPreviewBar) imgPreviewBar.classList.add('hidden');
  if(fileInput) fileInput.value = '';
}

function processFile(file){
  if(!file || !file.type.startsWith('image/')) return;
  const r = new FileReader();
  r.onload = ev => {
    const src = ev.target.result;
    const parts = src.split(',');
    const mimeMatch = parts[0].match(/:(.*?);/);
    const mime_type = mimeMatch ? mimeMatch[1] : file.type;
    const data = parts[1];
    currentImage = { mime_type, data, src };
    if(imgPreview) imgPreview.src = src;
    if(imgPreviewBar) imgPreviewBar.classList.remove('hidden');
  };
  r.readAsDataURL(file);
}

window.addEventListener('paste', e => {
  const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items || [];
  for (const item of items) {
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) processFile(file);
    }
  }
});

const footEl = $('#foot');
if(footEl){
  footEl.addEventListener('dragover', e => { e.preventDefault(); });
  footEl.addEventListener('drop', e => {
    e.preventDefault();
    if (e.dataTransfer?.files?.[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  });
}

function addMsgToUI(role,text,isLoading=false,imgData=null){
  const m=document.createElement('div');m.className='msg '+role;
  if (role !== 'user' && !isLoading && text) {
    m.dataset.agentComplete = 'true';
    m.dataset.agentText = text;
    m.dataset.agentCompletedAt = String(Date.now());
  }
  const av=document.createElement('div');av.className='av';av.textContent=role==='user'?'S':'✦';
  const b=document.createElement('div');b.className='bubble';
  let html = '';
  if(imgData && imgData.src){
    html += `<img src="${esc(imgData.src)}" class="chat-img" alt="Biriktirilgan rasm"><br>`;
  }
  if(isLoading){
    html += '<div class="thinking">' + GEM_SPARK + '<span class="think-label">Javob tayyorlanmoqda…</span></div>';
  } else {
    html += renderMD(text);
  }
  b.innerHTML=html;
  if (role !== 'user' && !isLoading && text) {
    const replayBtn = document.createElement('button');
    replayBtn.className = 'voice-replay-btn';
    replayBtn.type = 'button';
    replayBtn.title = 'Ovozda eshitish';
    replayBtn.innerHTML = '🔊 Ovozda eshitish';
    replayBtn.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (window.speakSingleText) {
        window.speakSingleText(text);
      }
    };
    b.appendChild(replayBtn);
  }
  m.appendChild(av);m.appendChild(b);chatArea.appendChild(m);
  paintWelcome();
  scrollDown(true);
  setTimeout(initExcelWidgets, 20);
  return b;
}

function addMsg(role,text,isLoading=false,imgData=null){
  const b = addMsgToUI(role, text, isLoading, imgData);
  if (!isLoading) {
    try {
      saveMessageToHistory(role, text, imgData);
    } catch (error) {
      console.warn('Suhbat tarixi saqlanmadi, lekin chat davom etadi.', error);
    }
  }
  return b;
}

function showChat(on){
  $('#chatArea').classList.toggle('hidden',!on);
  $('#foot').classList.toggle('hidden',!on);
  $('#folderBox').classList.toggle('hidden',!on);
  $('#newChat').classList.toggle('hidden',!on);
  $('#loginCard').classList.toggle('hidden',on);
  paintWelcome();
}

/* Salomlashuv va tezkor kartalar faqat suhbat bo'sh paytda turadi.
   Suhbat boshlangach ular yo'qoladi — ekranda faqat ish qoladi. */
function paintWelcome(){
  const box = $('#welcomeBox');
  if(!box) return;
  const bosh = !$('#chatArea').querySelector('.msg');
  box.classList.toggle('hidden', !signedIn || !bosh);
}

function doSwitch(){
  if(!confirm('Boshqa Google hisob bilan kirasizmi? Joriy hisob almashtiriladi.'))return;
  fetch('/api/switch',{method:'POST'}).then(r=>r.json()).then(d=>{
    signedIn=false;showChat(false);$('#loginCard').classList.remove('hidden');showFlow();
    if(d.url)$('#authLink').href=d.url;
    $('#loginMsg').innerHTML="Yangi hisob bilan kiring, kodni joylang, so'ng <button onclick=\"location.reload()\" class=\"ghost\" style=\"padding:3px 10px;font-size:12px\">✓ Yangilash</button>";
  }).catch(e=>alert('Xato: '+e.message));
}

function renderProfile(email,accountInfo={}){
  const p=$('#prof');p.classList.remove('hidden');
  const ini=(email||'U')[0].toUpperCase();
  const account = esc(email || 'Google hisobi aniqlandi');
  const accountType = esc(accountInfo.accountType || 'Google Account');
  const plan = esc(accountInfo.plan || 'Tarif ma’lumoti berilmagan');
  const avatarUrl = String(accountInfo.avatarUrl || '');
  const avatar = avatarUrl ? `<img src="${esc(avatarUrl)}" alt="Google profil rasmi" onerror="this.remove()">` : `<span>${ini}</span>`;
  p.title = `Google Account: ${email || 'aniqlanmagan'}\n${accountType}\n${plan}`;
  p.innerHTML=`<div class="profile-avatar-frame"><div class="ava google-avatar">${avatar}</div></div><div class="who"><b><span class="google-account-mark">G</span><span>${account}</span><span class="chip profile-account-chip">${accountType}</span></b><small>${plan} · AGY faol</small></div><button class="ghost profile-switch" onclick="doSwitch()" title="Google hisobini almashtirish">⇄</button>`;
}

function populateModels(models,codexInfo,solInfo){
  const sel=$('#modelSel');
  const savedModel = localStorage.getItem('agv_model');
  /* Vositalar (jadval, brauzer, printer, TV, Telegram…) faqat Sol yo'lida bor.
     Tanlagichda buni ko'rsatamiz — aks holda foydalanuvchi CLI modelini tanlab,
     nega hech narsa ishlamayotganini tushunmay qoladi. */
  sel.innerHTML = '<option value="">Composer Auto — vositasiz</option>';
  /* ChatGPT Sol — bulutga to'g'ridan-to'g'ri ulanadi: birinchi so'z ~1s da keladi,
     matn oqib chiqadi, fayl/terminal vositalari ham shu yerda ishlaydi. */
  if(solInfo && solInfo.ready){
    const solOption = document.createElement('option');
    solOption.value = solInfo.id || '__chatgpt_sol__';
    solOption.textContent = 'ChatGPT Sol — barcha vositalar';
    sel.appendChild(solOption);
    sel.value = solOption.value;               // standart tanlov
  }
  if(codexInfo && codexInfo.ready){
    const codexOption = document.createElement('option');
    codexOption.value = '__codex_chatgpt__';
    codexOption.textContent = 'Codex CLI — vositasiz';
    sel.appendChild(codexOption);
  }
  (models || []).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m + ' — vositasiz';
    sel.appendChild(opt);
  });
  if(savedModel && Array.from(sel.options).some(option => option.value === savedModel)) sel.value = savedModel;
  dashModelToldir();
}

/* Dashboarddagi tanlagich asosiysidan nusxa oladi — ro'yxat bir joyda
   turadi, ikkinchi marta yozilmaydi. Tanlov alohida saqlanadi, chunki
   dashboardda odatda tezkor model kerak bo'ladi. */
function dashModelToldir(){
  const asos = document.getElementById('modelSel');
  const dm = document.getElementById('dashModel');
  if(!asos || !dm) return;
  const saqlangan = localStorage.getItem('agv_dash_model');
  dm.innerHTML = '';
  Array.from(asos.options).forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.value;
    opt.textContent = o.textContent;
    dm.appendChild(opt);
  });
  if(saqlangan && Array.from(dm.options).some(o => o.value === saqlangan)) dm.value = saqlangan;
  else dm.value = asos.value;
}

if(document.getElementById('dashModel')){
  document.getElementById('dashModel').onchange = e =>
    localStorage.setItem('agv_dash_model', e.target.value);
}

$('#modelSel').onchange = () => {
  localStorage.setItem('agv_model', $('#modelSel').value);
};

function syncFolderDisplay() {
  const f = $('#folder') ? $('#folder').value : '';
  const d = $('#folderNameDisplay');
  if (d) {
    if (!f) {
      d.textContent = 'Folder';
    } else {
      const clean = f.replace(/\\/g, '/').replace(/\/$/, '');
      const parts = clean.split('/');
      const name = parts[parts.length - 1] || clean;
      d.textContent = name;
    }
  }
}

$('#folder').onchange = () => {
  localStorage.setItem('agv_folder', $('#folder').value);
  syncFolderDisplay();
};

/* ══════════════════════════════════════════════════════════════
   HISOB PANELI — kassa, ombor, qarzlar, foyda doim ko'z oldida.
   Ma'lumot faqat serverdagi amallar jurnalidan keladi; bu yerda
   hech narsa hisoblanmaydi, shuning uchun raqamlar hech qachon
   AI aytgan raqamdan farq qilmaydi.
   ══════════════════════════════════════════════════════════════ */
let HISOB = null, hisobOchiq = '', hisobTimer = null;

function fmtPul(qiymat){
  const son = Number(qiymat) || 0;
  const belgi = son < 0 ? '−' : '';
  return belgi + String(Math.abs(Math.round(son))).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

async function loadHisob(){
  try{
    const r = await fetch('/api/hisob');
    const d = await r.json();
    if(d.status === 'ok'){ HISOB = d.hisob; paintHisob(); }
  }catch(e){ /* panel ikkinchi darajali — xato chatni to'xtatmasin */ }
}

/* Panelni yig'ish/ochish. Tanlov localStorage da saqlanadi — sahifa
   yangilanganda ham o'sha holatda qoladi. */
function hisobYigish(yigilgan, saqla){
  const bar = $('#hisobBar'), btn = $('#hisobToggle'), txt = $('#hisobToggleTxt');
  if(!bar) return;
  bar.classList.toggle('yigilgan', yigilgan);
  if(btn) btn.setAttribute('aria-expanded', String(!yigilgan));
  if(txt) txt.textContent = yigilgan ? "Ko'rsatish" : 'Yashirish';
  if(saqla !== false) localStorage.setItem('agv_hisob_yigik', yigilgan ? '1' : '0');
}

if($('#hisobToggle')){
  $('#hisobToggle').onclick = () =>
    hisobYigish(!$('#hisobBar').classList.contains('yigilgan'));
}
hisobYigish(localStorage.getItem('agv_hisob_yigik') === '1', false);

function paintHisob(){
  const bar = $('#hisobBar');
  if(!bar) return;
  if(!HISOB || !signedIn){ bar.classList.add('hidden'); return; }
  bar.classList.remove('hidden');
  const h = HISOB;
  const put = (id, v) => { const el = $(id); if(el) el.textContent = v; };
  const valyuta = (h.biznes && h.biznes.valyuta) || 'UZS';

  /* Bir nechta kassa/valyuta bo'lsa umumiy son yaramaydi — USD va UZS
     qo'shilib ma'nosiz chiqadi. Shuning uchun har valyutani alohida
     ko'rsatamiz; bitta valyuta bo'lsa ko'rinish avvalgidek qoladi. */
  const vlar = h.valyutalar || [];
  const klar = h.kassalar || [];
  const extra = $('#hbKassaExtra');
  if(vlar.length > 1){
    // asosiy valyuta tepada katta, qolganlari ostida mayda ustun bo'lib
    const asosiy = vlar.find(v => v.valyuta === valyuta) || vlar[0];
    const qolgan = vlar.filter(v => v !== asosiy);
    put('#hbKassa', fmtPul(asosiy.kassa) + ' ' + asosiy.valyuta);
    if(extra){
      extra.innerHTML = qolgan.map(v =>
        '<span>' + fmtPul(v.kassa) + ' ' + esc(v.valyuta) + '</span>').join('');
      extra.classList.add('on');
    }
    put('#hbKassaSub', klar.length + ' kassa · ' + vlar.length + ' valyuta');
  } else {
    put('#hbKassa', fmtPul(h.kassa));
    if(extra){ extra.innerHTML = ''; extra.classList.remove('on'); }
    put('#hbKassaSub', klar.length > 1 ? (klar.length + ' kassa · ' + valyuta) : valyuta);
  }
  const kassaCell = bar.querySelector('.hisob-cell[data-bolim="kassa"]');
  if(kassaCell){
    kassaCell.title = klar.length
      ? klar.map(k => k.nom + ': ' + fmtPul(k.qoldiq) + ' ' + k.valyuta).join('\n')
      : '';
  }
  put('#hbOmbor',     fmtPul(h.ombor.jami_qiymat));
  put('#hbOmborSub',  h.ombor.tur_soni + ' xil tovar');
  put('#hbQarzdor',   fmtPul(h.qarzdorlar.jami));
  put('#hbQarzdorSub',h.qarzdorlar.odamlar.length + ' kishi');
  put('#hbQarzim',    fmtPul(h.qarzlarim.jami));
  put('#hbQarzimSub', h.qarzlarim.odamlar.length + ' kishi');
  put('#hbFoyda',     fmtPul(h.foyda.sof));
  // Kassaga solingan pul foyda EMAS — u alohida ko'rsatiladi
  put('#hbFoydaSub', 'savdo ' + fmtPul(h.foyda.savdo)
      + (h.foyda.boshqa_kirim ? '  ·  kirim ' + fmtPul(h.foyda.boshqa_kirim) : ''));
  put('#hbAmallar',   String(h.amallar_soni));

  const cell = b => bar.querySelector('.hisob-cell[data-bolim="' + b + '"]');
  const rang = (b, ok, ogoh) => {
    const el = cell(b); if(!el) return;
    el.classList.toggle('ok', !!ok); el.classList.toggle('ogoh', !!ogoh);
  };
  const kassaMusbat = vlar.length > 1 ? vlar.every(v => v.kassa >= 0) : h.kassa > 0;
  const kassaManfiy  = vlar.length > 1 ? vlar.some(v => v.kassa < 0)   : h.kassa < 0;
  rang('kassa',      kassaMusbat,            kassaManfiy);
  rang('qarzdorlar', h.qarzdorlar.jami > 0,  false);
  rang('qarzlarim',  false,                  h.qarzlarim.jami > 0);
  rang('foyda',      h.foyda.sof > 0,        h.foyda.sof < 0);

  // Yig'ilgan holatda ham eng muhimi ko'rinib tursin
  const brief = $('#hisobBrief');
  if(brief){
    const qismlar = [];
    (klar.length ? klar : [{nom:'Kassa', qoldiq:h.kassa, valyuta:valyuta}]).forEach(k =>
      qismlar.push(k.nom + ' ' + fmtPul(k.qoldiq) + ' ' + k.valyuta));
    if(h.qarzdorlar.jami) qismlar.push('qarzdorlar ' + fmtPul(h.qarzdorlar.jami));
    if(h.qarzlarim.jami)  qismlar.push('qarzlarim ' + fmtPul(h.qarzlarim.jami));
    brief.textContent = qismlar.join('  ·  ');
  }

  bar.querySelectorAll('.hisob-cell').forEach(el =>
    el.classList.toggle('active', el.dataset.bolim === hisobOchiq));
  if(hisobOchiq) paintHisobDetail(hisobOchiq);
}

function hisobQator(nom, summa, izoh){
  return '<tr><td>' + esc(nom) + (izoh ? ' <span class="muted">' + esc(izoh) + '</span>' : '') +
         '</td><td>' + fmtPul(summa) + '</td></tr>';
}

function hisobBosh(matn, misol){
  return '<div class="hisob-bosh">' + esc(matn) +
         (misol ? '<br>Masalan: <code>' + esc(misol) + '</code>' : '') + '</div>';
}

function kassaTafsiloti(h){
  const klar = h.kassalar || [];
  if(!klar.length) return '';
  return '<div class="hisob-list">' + klar.map(k =>
    '<div class="hisob-row"><span>' + esc(k.nom) + '</span>' +
    '<b>' + fmtPul(k.qoldiq) + ' ' + esc(k.valyuta) + '</b></div>').join('') + '</div>';
}

/* Kassa ochish / nomlash / o'chirish — panel ichidan. Serverdan yangilangan
   hisobot qaytadi, shuning uchun panel darrov to'g'ri raqamni ko'rsatadi. */
async function kassaAmal(sorov){
  try{
    const r = await fetch('/api/hisob/kassa', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(sorov)
    });
    const d = await r.json();
    if(d.status !== 'ok'){ alert('Bajarilmadi: ' + (d.error || '')); return; }
    HISOB = d.hisob;
    paintHisob();
  }catch(e){ alert('Serverga ulanib bo\'lmadi: ' + e.message); }
}

async function paintHisobDetail(bolim){
  const box = $('#hisobDetail');
  if(!box || !HISOB){ return; }
  const h = HISOB;
  let html = '';

  if(bolim === 'kassa'){
    // Har kassa alohida qatorda: nomi, valyutasi, qoldig'i va nomlash tugmasi
    const klar = h.kassalar || [];
    html = '<h4>Kassalar</h4><table class="kassa-jadval">' + klar.map(k =>
      '<tr><td><b>' + esc(k.nom) + '</b> <span class="muted">' + esc(k.valyuta) + '</span></td>' +
      '<td class="kassa-son">' + fmtPul(k.qoldiq) + ' ' + esc(k.valyuta) + '</td>' +
      '<td class="kassa-amal">' +
        '<button type="button" class="kassa-btn" data-nomla="' + esc(k.nom) + '" title="Nomini o\'zgartirish">✎</button>' +
        (k.nom === (h.biznes && h.biznes.asosiy_kassa) ? '' :
         '<button type="button" class="kassa-btn ochir" data-ochir="' + esc(k.nom) + '" title="O\'chirish">✕</button>') +
      '</td></tr>').join('') +
      '<tr><td colspan="3"><button type="button" class="kassa-yangi" id="kassaYangiBtn">+ Yangi kassa ochish</button></td></tr>' +
      '</table>' +
      '<h4 style="margin-top:14px">Umumiy balans</h4><table>' +
      hisobQator('Kassadagi naqd', h.kassa) +
      hisobQator('Ombor qiymati', h.ombor.jami_qiymat) +
      hisobQator('Menga qarzdorlar', h.qarzdorlar.jami) +
      hisobQator('Mening qarzlarim', -h.qarzlarim.jami) +
      '<tr><td><b>Sof balans</b></td><td><b>' + fmtPul(h.sof_balans) + '</b></td></tr></table>';
  }
  else if(bolim === 'ombor'){
    html = '<h4>Ombor qoldig\'i</h4>';
    if(!h.ombor.tovarlar.length){
      html += hisobBosh('Omborda hali tovar yo\'q.', 'Sardordan 10 kg un qarzga oldim, kilosi 8 ming');
    } else {
      html += '<table>' + h.ombor.tovarlar.map(t =>
        '<tr><td>' + esc(t.nom) + ' <span class="muted">' + t.miqdor + ' ' + esc(t.birlik) +
        (t.tan_narx ? ' · ' + fmtPul(t.tan_narx) + '/' + esc(t.birlik) : '') +
        '</span></td><td>' + fmtPul(t.qiymat) + '</td></tr>').join('') + '</table>';
    }
  }
  else if(bolim === 'qarzdorlar'){
    html = '<h4>Menga qarzdor</h4>';
    html += h.qarzdorlar.odamlar.length
      ? '<table>' + h.qarzdorlar.odamlar.map(q => hisobQator(q.kim, q.summa)).join('') + '</table>'
      : hisobBosh('Hech kim qarzdor emas.', 'Alisherga 200 ming qarz berdim');
  }
  else if(bolim === 'qarzlarim'){
    html = '<h4>Men qarzdorman</h4>';
    html += h.qarzlarim.odamlar.length
      ? '<table>' + h.qarzlarim.odamlar.map(q => hisobQator(q.kim, q.summa)).join('') + '</table>'
      : hisobBosh('Qarzingiz yo\'q.', 'Sardordan 5 million qarz oldim');
  }
  else if(bolim === 'foyda'){
    const f = h.foyda;
    html = '<h4>Foyda hisoboti</h4><table>' +
      hisobQator('Savdodan tushum', f.savdo) +
      hisobQator('Sotilgan tovar tannarxi', -f.tannarx) +
      hisobQator('Yalpi foyda', f.yalpi) +
      (f.boshqa_kirim ? hisobQator('Boshqa kirim', f.boshqa_kirim) : '') +
      hisobQator('Xarajatlar', -f.xarajat) +
      '<tr><td><b>Sof foyda</b></td><td><b>' + fmtPul(f.sof) + '</b></td></tr></table>';
  }
  else if(bolim === 'amallar'){
    html = '<h4>Oxirgi yozuvlar</h4><div class="muted">Yuklanmoqda…</div>';
    box.innerHTML = html;
  // Kassa boshqaruv tugmalari
  box.querySelectorAll('[data-nomla]').forEach(b => b.onclick = async () => {
    const eski = b.dataset.nomla;
    const yangi = prompt("Kassaning yangi nomi:", eski);
    if(yangi === null || !yangi.trim() || yangi.trim() === eski) return;
    await kassaAmal({amal:'nomlash', eski_nom: eski, yangi_nom: yangi.trim()});
  });
  box.querySelectorAll('[data-ochir]').forEach(b => b.onclick = async () => {
    if(!confirm("'" + b.dataset.ochir + "' kassasi ro'yxatdan olib tashlansinmi?\n"
                + "Amallar jurnalda saqlanib qoladi.")) return;
    await kassaAmal({amal:'ochirish', nom: b.dataset.ochir});
  });
  const yangiBtn = box.querySelector('#kassaYangiBtn');
  if(yangiBtn) yangiBtn.onclick = async () => {
    const nom = prompt("Yangi kassa nomi:");
    if(nom === null || !nom.trim()) return;
    const val = prompt("Valyutasi (UZS, USD, USDT...):",
                       (HISOB.biznes && HISOB.biznes.valyuta) || 'UZS');
    if(val === null) return;
    await kassaAmal({amal:'ochish', nom: nom.trim(), valyuta: (val || '').trim()});
  };
    try{
      const r = await fetch('/api/hisob/amallar?limit=25');
      const d = await r.json();
      const list = (d.amallar || []);
      html = '<h4>Oxirgi yozuvlar</h4>';
      html += list.length ? '<table>' + list.map(a => {
        const sana = String(a.sana || '').replace('T', ' ').slice(5, 16);
        const kim  = a.kim ? ' · ' + a.kim : '';
        const tovar = a.tovar ? ' · ' + a.tovar + ' ' + a.miqdor + ' ' + a.birlik : '';
        return '<tr><td><span class="muted">' + esc(sana) + '</span> ' +
               esc(HISOB_TUR[a.tur] || a.tur) + esc(kim + tovar) +
               (a.izoh ? ' <span class="muted">' + esc(a.izoh) + '</span>' : '') +
               '</td><td>' + fmtPul(a.summa) + '</td></tr>';
      }).join('') + '</table>'
      : hisobBosh('Hali hech narsa yozilmagan.', '3 dona non 5 mingdan sotdim');
    }catch(e){ html = '<h4>Oxirgi yozuvlar</h4>' + hisobBosh('Yozuvlarni olishda xato.'); }
  }
  box.innerHTML = html;
}

const HISOB_TUR = {
  sotuv: 'Sotuv', xarid: 'Xarid', qarz_berdim: 'Qarz berdim', qarz_oldim: 'Qarz oldim',
  qarz_qaytardim: 'Qaytardim', qarz_qaytarildi: 'Qaytarib berishdi',
  xarajat: 'Xarajat', kirim: 'Kirim', boshlangich: "Boshlang'ich"
};

document.querySelectorAll('#hisobBar .hisob-cell').forEach(el => {
  el.onclick = () => {
    const bolim = el.dataset.bolim;
    hisobOchiq = (hisobOchiq === bolim) ? '' : bolim;
    $('#hisobDetail').classList.toggle('hidden', !hisobOchiq);
    document.querySelectorAll('#hisobBar .hisob-cell').forEach(x =>
      x.classList.toggle('active', x.dataset.bolim === hisobOchiq));
    if(hisobOchiq) paintHisobDetail(hisobOchiq);
  };
});

function setStatus(on,email,pro,models,port,accountInfo,codexInfo,solInfo){
  signedIn=on;
  showChat(on);
  if(port) $('#portBadge').textContent = 'Port: ' + port;
  if(on){
    renderProfile(email,accountInfo);
    populateModels(models,codexInfo,solInfo);
    const savedDir = localStorage.getItem('agv_folder');
    if(savedDir) $('#folder').value = savedDir;
    else if(!$('#folder').value) $('#folder').value = DEFAULT_DIR;
    syncFolderDisplay();
    stopPoll();
    resumeJobs();          // yangilangandan keyin davom etayotgan ish bo'lsa — ulanamiz
    if (typeof loadVoiceConfig === 'function') loadVoiceConfig();
    loadHisob();
    if(!hisobTimer) hisobTimer = setInterval(loadHisob, 25000);
  }
}

function stopPoll(){if(loginPoll){clearInterval(loginPoll);loginPoll=null;}}
function showFlow(){$('#loginFlow').classList.remove('hidden');$('#loginStart').classList.add('hidden');}
let DEFAULT_DIR="";

async function poll(){
  try{
    const r=await fetch('/api/login/state');
    const d=await r.json();
    if(d.url){$('#authLink').href=d.url;showFlow();}
    if(d.term)$('#term').textContent=d.term;
    if(d.signedIn){setStatus(true,d.email,d.pro,d.models,d.port,d.account,d.codex,d.sol);}
  }catch(e){}
}

async function init(){
  try{
    renderHistory();
    const r=await fetch('/api/status');
    const d=await r.json();
    DEFAULT_DIR=d.home||"";
    $('#portBadge').textContent = 'Port: ' + (d.port || '8777') + (d.ip ? ' (' + d.ip + ')' : '');
    if (d.networkUrl) $('#portBadge').title = 'Wi-Fi IP: ' + d.networkUrl;
    if(d.signedIn) {
      setStatus(true,d.email,d.pro,d.models,d.port,d.account,d.codex,d.sol);
      restoreActiveSession();
      loadSharedSessions();
      checkSharedSessionUrl();
    }
    else{setStatus(false);$('#loginCard').classList.remove('hidden');}
  }catch(e){$('#loginCard').classList.remove('hidden');}
}

$('#beginLogin').onclick=async()=>{
  $('#beginLogin').disabled=true;
  $('#loginMsg').textContent='Kirish tayyorlanmoqda…';
  try{
    const r=await fetch('/api/login/start',{method:'POST'});
    const d=await r.json();
    if(d.signedIn){setStatus(true,d.email,d.pro,d.models,d.port,d.account,d.codex,d.sol);return;}
    showFlow();
    if(d.url)$('#authLink').href=d.url;
    if(!loginPoll)loginPoll=setInterval(poll,3000);
  }catch(e){
    $('#loginMsg').innerHTML='<span class="err">Xato: '+e.message+'</span>';
  }finally{
    $('#beginLogin').disabled=false;
  }
};

$('#sendCode').onclick=async()=>{
  const c=$('#code').value.trim();if(!c)return;
  $('#loginMsg').textContent='Kod yuborilmoqda…';
  await fetch('/api/login/input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:c})});
  if(!loginPoll)loginPoll=setInterval(poll,3000);
  setTimeout(poll,1500);
};

$('#restartLogin').onclick=async()=>{
  $('#loginMsg').textContent='Qayta boshlanmoqda…';
  await fetch('/api/login/start',{method:'POST'});
  if(!loginPoll)loginPoll=setInterval(poll,3000);
  setTimeout(poll,800);
};

$('#newChat').onclick=async()=>{
  await fetch('/api/new-chat',{method:'POST'});
  createNewSession();
};

function isVisualRequest(text, hasImage){
  return hasImage || /\b(image|photo|picture|video|animation|animate|generate|edit image|rasm|surat|video|animatsiya|multfilm|qimirla|tahrirla|o'zgartir)\b/i.test(text || '');
}

async function submit(){
  const t=$('#input').value.trim();
  if((!t && !currentImage)||busy||!signedIn)return;
  busy=true;
  $('#send').disabled=true;
  const imgToSend = currentImage;
  let sid;
  let continueConversation = false;
  try {
    const session = ensureActiveSession();
    sid = session.id;
    continueConversation = Boolean(
      convo || session.messages.some(message => message.role === 'model')
    );
    addMsg('user',t,false,imgToSend);
    clearAttachedImage();
    $('#input').value='';
    $('#input').style.height='auto';
  } catch (error) {
    busy=false;
    $('#send').disabled=false;
    $('#input').focus();
    console.error('Birinchi xabar oynaga qo\'shilmadi:', error);
    alert('Xabarni suhbat oynasiga qo\'shib bo\'lmadi. Matn saqlanib qoldi.');
    return;
  }
  LIVE = { jobId:null, sid, acts:[], finalText:'', streamText:'', evIdx:0, startedAt:Date.now(), ui:null, visual:isVisualRequest(t, Boolean(imgToSend)), sourceImage:imgToSend && imgToSend.src ? imgToSend.src : '' };
  liveMount();
  paintJobBadge();
  if(desktopLiveAutoEnabled()) openDesktopLive();
  try{
    const r=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({prompt:t,image:imgToSend,model:$('#modelSel').value,cont:continueConversation,folder:$('#folder').value.trim(),session:sid})
    });
    await runLive(r);
  }catch(e){
    if(LIVE) LIVE.finalText=(LIVE.finalText?LIVE.finalText+'\n':'')+'⚠️ '+e.message;
  }finally{
    liveFinish();
    busy=false;
    $('#send').disabled=false;
    $('#input').focus();
    scrollDown(true);
  }
}

$('#send').onclick=submit;
$('#input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit();}});
$('#input').addEventListener('input',()=>{
  const i=$('#input');
  i.style.height='auto';
  i.style.height=Math.min(i.scrollHeight,180)+'px';
});

let pkPath="";
async function pkLoad(p){
  try{
    const r=await fetch('/api/ls?path='+encodeURIComponent(p||''));
    const d=await r.json();
    pkPath=d.path;
    $('#pkPath').textContent=d.path;
    $('#pkUp').dataset.p=d.parent;
    $('#pkList').innerHTML=d.dirs.length ? d.dirs.map(n=>`<div class="pkrow" style="padding:8px 10px;cursor:pointer;border-radius:8px" data-n="${n.replace(/"/g,'&quot;')}">📁 ${n}</div>`).join('') : '<div class="muted" style="padding:8px">(ichki papka yoʻq)</div>';
    $('#pkList').querySelectorAll('.pkrow').forEach(el=>el.onclick=()=>pkLoad((pkPath==='/'?'':pkPath)+'/'+el.dataset.n));
  }catch(e){}
}

const openPicker = () => {
  if($('#pkMkdirBox')) $('#pkMkdirBox').classList.add('hidden');
  $('#picker').classList.remove('hidden');
  pkLoad($('#folder').value||'');
};
if($('#pickBtn')) $('#pickBtn').onclick = openPicker;
if($('#folderBox')) $('#folderBox').onclick = openPicker;
$('#pkClose').onclick=()=>$('#picker').classList.add('hidden');
$('#pkUp').onclick=()=>pkLoad($('#pkUp').dataset.p);

if($('#pkMkdirBtn')) $('#pkMkdirBtn').onclick = () => {
  const box = $('#pkMkdirBox');
  box.classList.toggle('hidden');
  if(!box.classList.contains('hidden')) {
    $('#pkNewName').value = '';
    $('#pkNewName').focus();
  }
};
if($('#pkMkdirCancel')) $('#pkMkdirCancel').onclick = () => {
  $('#pkMkdirBox').classList.add('hidden');
};

async function createNewFolder() {
  const name = $('#pkNewName').value.trim();
  if(!name) return;
  try {
    const r = await fetch('/api/mkdir', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ parent: pkPath, name: name })
    });
    const d = await r.json();
    if(d.ok) {
      $('#pkMkdirBox').classList.add('hidden');
      $('#pkNewName').value = '';
      await pkLoad(d.path);
    } else {
      alert('Xatolik: ' + (d.error || 'Papka yaratib bo\'lmadi'));
    }
  } catch(e) {
    alert('Xatolik: ' + e.message);
  }
}

if($('#pkMkdirConfirm')) $('#pkMkdirConfirm').onclick = createNewFolder;
if($('#pkNewName')) $('#pkNewName').addEventListener('keydown', e => {
  if(e.key === 'Enter') {
    e.preventDefault();
    createNewFolder();
  }
});

$('#pkPick').onclick=()=>{
  $('#folder').value = pkPath;
  localStorage.setItem('agv_folder', pkPath);
  syncFolderDisplay();
  $('#picker').classList.add('hidden');
};

const themeBtn=$('#theme');
function applyTheme(t){
  document.documentElement.dataset.theme=t;
  themeBtn.textContent=t==='dark'?'🌙':'☀️';
  try{localStorage.setItem('agv_theme',t)}catch(e){}
}
themeBtn.onclick=()=>applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
applyTheme(localStorage.getItem('agv_theme') || 'dark');

document.addEventListener('mousemove', e => {
  const bg = $('#antigravity-bg');
  if(!bg) return;
  const cx = window.innerWidth / 2;
  const cy = window.innerHeight / 2;
  const dx = (e.clientX - cx) / cx;
  const dy = (e.clientY - cy) / cy;
  bg.style.transform = `perspective(1000px) rotateY(${dx * 12}deg) rotateX(${-dy * 12}deg) translate3d(${dx * 25}px, ${dy * 25}px, 0)`;
});

function copyFA(btn){
  const cmd = btn.parentElement.textContent.replace('Nusxalash','').trim();
  navigator.clipboard.writeText(cmd).then(()=>{
    const old = btn.textContent;
    btn.textContent = '✓ Nusxalandi!';
    setTimeout(()=> btn.textContent = old, 2000);
  });
}
/* Tugma menyu ichidagi element — ichini butunlay almashtirsak belgisi va
   tuzilishi yo'qoladi. Shuning uchun faqat izoh matni yangilanadi. */
function markFullAccess(yoqilgan){
  const btn = $('#fullAccessBtn');
  if(!btn) return;
  btn.classList.toggle('on', Boolean(yoqilgan));
  const izoh = btn.querySelector('.nav-copy small');
  if(izoh) izoh.textContent = yoqilgan ? 'Yoqilgan — agent so‘ramasdan ishlaydi'
                                       : 'Agent ruxsatlarini sozlash';
}
$('#fullAccessBtn').onclick=()=>$('#faModal').classList.remove('hidden');
$('#faClose').onclick=()=>$('#faModal').classList.add('hidden');
$('#faCancelBtn').onclick=()=>$('#faModal').classList.add('hidden');
$('#faModal').onclick=e=>{if(e.target.id==='faModal')$('#faModal').classList.add('hidden');};
$('#faApplyBtn').onclick=()=>{
  const opts = {
    files: $('#faAutoFiles').checked,
    commands: $('#faAutoCmd').checked,
    network: $('#faAutoNet').checked,
    delete: $('#faAutoDelete').checked
  };
  localStorage.setItem('agv_full_access', JSON.stringify(opts));
  markFullAccess(true);
  const bub = addMsg('model', '🔓 **Full Access rejimi yoqildi!**\n\nQuyidagi ruxsatlar berildi:\n' +
    (opts.files ? '- ✅ Fayllarni avtomatik tasdiqlash\n' : '- ❌ Fayllar — ruxsat kerak\n') +
    (opts.commands ? '- ✅ Buyruqlarni avtomatik bajarish\n' : '- ❌ Buyruqlar — ruxsat kerak\n') +
    (opts.network ? '- ✅ Tarmoq so\'rovlari ruxsat etildi\n' : '- ❌ Tarmoq — ruxsat kerak\n') +
    (opts.delete ? '- ✅ O\'chirish operatsiyalari ruxsat etildi\n' : '- ❌ O\'chirish — ruxsat kerak\n') +
    '\nAgent endi `--dangerously-skip-permissions` rejimida ishlaydi. ⚡');
  $('#faModal').classList.add('hidden');
  showChat(true);
  burstConfetti(70);
};

(function(){
  try{
    const fa = JSON.parse(localStorage.getItem('agv_full_access'));
    if(fa){
      markFullAccess(true);
      if(fa.files) $('#faAutoFiles').checked=true;
      if(fa.commands) $('#faAutoCmd').checked=true;
      if(fa.network) $('#faAutoNet').checked=true;
      if(fa.delete) $('#faAutoDelete').checked=true;
    }
  }catch(e){}
})();

/* --- SIDEBAR TABS & FILE TREE LOGIC --- */
document.querySelectorAll('.sb-tab').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.sb-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.sb-tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const tabId = 'tab' + btn.dataset.tab.charAt(0).toUpperCase() + btn.dataset.tab.slice(1);
    const target = $('#' + tabId);
    if (target) target.classList.add('active');
    if (btn.dataset.tab === 'files') loadWorkspaceFileTree();
    if (btn.dataset.tab === 'tools') {
      loadGeminiVideoConfig();
      loadVoiceConfig();
    }
  };
});

if($('#sidebarFaBtn')){
  $('#sidebarFaBtn').onclick = () => $('#faModal').classList.remove('hidden');
}

function setGeminiVideoConfigStatus(config, errorMessage='') {
  const status = $('#geminiKeyStatus');
  const clear = $('#geminiKeyClear');
  if (!status) return;
  if (errorMessage) {
    status.className = 'video-config-status problem';
    status.textContent = '⚠️ ' + errorMessage;
    return;
  }
  const ready = Boolean(config && config.ready);
  const configured = Boolean(config && config.keyConfigured);
  status.className = 'video-config-status ' + (ready ? 'ready' : 'problem');
  status.textContent = (ready ? '● ' : '⚠️ ') + (config.status || 'Sozlama aniqlanmadi.') + (configured ? ' Kalit saqlangan.' : '');
  if (clear) clear.disabled = !configured;
}

async function loadGeminiVideoConfig() {
  try {
    const response = await fetch('/api/video/config');
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Video sozlamasini o‘qib bo‘lmadi.');
    setGeminiVideoConfigStatus(payload);
  } catch (error) {
    setGeminiVideoConfigStatus(null, error.message || 'Video sozlamasini o‘qib bo‘lmadi.');
  }
}

async function saveGeminiVideoConfig() {
  const input = $('#geminiApiKey');
  const save = $('#geminiKeySave');
  const apiKey = input ? input.value.trim() : '';
  if (!apiKey) {
    setGeminiVideoConfigStatus(null, 'Avval Gemini API kalitini kiriting.');
    return;
  }
  if (save) {
    save.disabled = true;
    save.textContent = 'Saqlanmoqda…';
  }
  try {
    const response = await fetch('/api/video/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({geminiApiKey: apiKey}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Kalitni saqlab bo‘lmadi.');
    input.value = '';
    input.type = 'password';
    $('#geminiKeyReveal').textContent = '👁';
    setGeminiVideoConfigStatus(payload);
  } catch (error) {
    setGeminiVideoConfigStatus(null, error.message || 'Kalitni saqlab bo‘lmadi.');
  } finally {
    if (save) {
      save.disabled = false;
      save.textContent = 'Saqlash va tekshirish';
    }
  }
}

async function clearGeminiVideoConfig() {
  if (!confirm('Gemini API kaliti lokal .env faylidan o‘chirilsinmi?')) return;
  try {
    const response = await fetch('/api/video/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({clear: true}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Kalitni o‘chirib bo‘lmadi.');
    setGeminiVideoConfigStatus(payload);
  } catch (error) {
    setGeminiVideoConfigStatus(null, error.message || 'Kalitni o‘chirib bo‘lmadi.');
  }
}

if ($('#geminiKeySave')) $('#geminiKeySave').onclick = saveGeminiVideoConfig;
if ($('#geminiKeyClear')) $('#geminiKeyClear').onclick = clearGeminiVideoConfig;
if ($('#geminiKeyReveal')) {
  $('#geminiKeyReveal').onclick = () => {
    const input = $('#geminiApiKey');
    if (!input) return;
    const hidden = input.type === 'password';
    input.type = hidden ? 'text' : 'password';
    $('#geminiKeyReveal').textContent = hidden ? '🙈' : '👁';
  };
}
if ($('#geminiApiKey')) {
  $('#geminiApiKey').addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      saveGeminiVideoConfig();
    }
  });
}

let VOICE_STATE = {
  ready: true,
  voice: localStorage.getItem('agv_voice') || 'marin',
  autoSpeak: localStorage.getItem('agv_voice_auto') === '1',
};
let voicePlayback = null;
let voicePlaybackToken = 0;
let voiceRecorder = null;
let voiceCaptureStream = null;
let voiceCaptureTimer = null;

async function previewVoice() {
  return;   // ovoz namunasi olib tashlandi
  /* eslint-disable no-unreachable */
  const select = $('#voiceSelect');
  const btn = $('#voicePreviewBtn');
  if (!select) return;
  const voice = select.value || VOICE_STATE.voice || 'uz-UZ-SardorNeural';
  const sampleText = voice.startsWith('uz-UZ-')
    ? "Salom! Men sizning AI yordamchingizman. Muhasib kassa tizimiga xush kelibsiz!"
    : "Hello! I am your AI assistant. Welcome to Muhasib POS system!";

  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>🔊</span> <span>Tinglanmoqda…</span>';
  }

  try {
    const isEdge = voice.startsWith('uz-UZ-');
    const endpoint = isEdge ? '/api/voice/edge' : '/api/voice/speech';
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: sampleText, voice: voice })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Ovoz audiosi o'qilmadi.");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = () => reject(new Error("Audio ijro etilmadi."));
      audio.play().catch(reject);
    });
    URL.revokeObjectURL(url);
  } catch (error) {
    alert("Ovoz namunasini ijro etib bo'lmadi: " + error.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

function setVoiceConfigStatus(config, errorMessage='') {
  const status = $('#voiceKeyStatus');
  const clear = $('#openaiKeyClear');
  if (!status) return;
  if (errorMessage) {
    status.className = 'video-config-status problem';
    status.textContent = '⚠️ ' + errorMessage;
    return;
  }
  VOICE_STATE.ready = Boolean(config && config.ready);
  status.className = 'video-config-status ' + (VOICE_STATE.ready ? 'ready' : 'problem');
  status.textContent = (VOICE_STATE.ready ? '● ' : '⚠️ ') + ((config && config.status) || 'Ovoz sozlamasi aniqlanmadi.');
  if (clear) clear.disabled = !Boolean(config && config.keyConfigured);

  const selected = (config && Array.isArray(config.voices) && config.voices.includes(VOICE_STATE.voice))
    ? VOICE_STATE.voice
    : VOICE_STATE.voice;

  VOICE_STATE.voice = selected;
  localStorage.setItem('agv_voice', selected);

  const voiceSelect = $('#voiceSelect');
  if (voiceSelect) voiceSelect.value = selected;

  const cgvVoiceSelect = $('#cgvVoiceSelect');
  if (cgvVoiceSelect) cgvVoiceSelect.value = selected;

  const autoSpeak = $('#voiceAutoSpeak');
  if (autoSpeak) autoSpeak.checked = VOICE_STATE.autoSpeak;
}

async function loadVoiceConfig() {
  try {
    const response = await fetch('/api/voice/config');
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Ovoz sozlamasini o‘qib bo‘lmadi.');
    setVoiceConfigStatus(payload);
  } catch (error) {
    setVoiceConfigStatus(null, error.message || 'Ovoz sozlamasini o‘qib bo‘lmadi.');
  }
}

async function saveVoiceConfig() {
  const input = $('#openaiApiKey');
  const save = $('#openaiKeySave');
  const apiKey = input ? input.value.trim() : '';
  if (!apiKey) {
    setVoiceConfigStatus(null, 'Avval OpenAI API kalitini kiriting.');
    return;
  }
  if (save) {
    save.disabled = true;
    save.textContent = 'Saqlanmoqda…';
  }
  try {
    const response = await fetch('/api/voice/config', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({openaiApiKey: apiKey}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Kalitni saqlab bo‘lmadi.');
    input.value = '';
    input.type = 'password';
    $('#openaiKeyReveal').textContent = '👁';
    setVoiceConfigStatus(payload);
  } catch (error) {
    setVoiceConfigStatus(null, error.message || 'Kalitni saqlab bo‘lmadi.');
  } finally {
    if (save) {
      save.disabled = false;
      save.textContent = 'Saqlash';
    }
  }
}

async function clearVoiceConfig() {
  if (!confirm('OpenAI API kaliti lokal .env faylidan o‘chirilsinmi?')) return;
  stopVoicePlayback();
  try {
    const response = await fetch('/api/voice/config', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({clear:true}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Kalitni o‘chirib bo‘lmadi.');
    setVoiceConfigStatus(payload);
  } catch (error) {
    setVoiceConfigStatus(null, error.message || 'Kalitni o‘chirib bo‘lmadi.');
  }
}

function stopVoicePlayback() {
  voicePlaybackToken += 1;
  if (voicePlayback) {
    voicePlayback.pause();
    voicePlayback.removeAttribute('src');
    voicePlayback = null;
  }
}

function voiceSpeechChunks(text) {
  let plain = String(text || '')
    .replace(/\x60\x60\x60[\s\S]*?\x60\x60\x60/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]+\)|\[[^\]]*\]\([^)]+\)/g, ' ')
    .replace(/\x60([^\x60]*)\x60/g, '$1')
    .replace(/[#*_>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!plain || plain.startsWith('⚠️')) return [];
  const sentences = plain.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g) || [plain];
  const chunks = [];
  sentences.forEach(sentence => {
    let remaining = sentence.trim();
    while (remaining.length > 360) {
      const cut = remaining.lastIndexOf(' ', 360);
      chunks.push(remaining.slice(0, cut > 80 ? cut : 360).trim());
      remaining = remaining.slice(cut > 80 ? cut + 1 : 360).trim();
    }
    if (remaining) chunks.push(remaining);
  });
  return chunks.slice(0, 6);
}

function voicePlaybackButton(text) {
  return;   // 8777 ovoz chiqarmaydi — "Ovozda tinglash" tugmasi olib tashlandi
  /* eslint-disable no-unreachable */
  if (!VOICE_STATE.ready || !voiceSpeechChunks(text).length) return;
  const messages = Array.from(document.querySelectorAll('#chatArea .msg.model .bubble'));
  const bubble = messages[messages.length - 1];
  if (!bubble || bubble.querySelector('.voice-replay-btn')) return;
  const button = document.createElement('button');
  button.className = 'voice-replay-btn';
  button.type = 'button';
  button.textContent = '🔊 Ovozda tinglash';
  button.onclick = () => speakAssistantResponse(text, true);
  bubble.appendChild(button);
}

function offerVoicePlayback(text) {
  try {
    if (typeof window.isLiveVoiceModeActive === 'function' && window.isLiveVoiceModeActive()) return;
    if (typeof voicePlaybackButton === 'function') voicePlaybackButton(text);
    if (typeof speakAssistantResponse === 'function') {
      Promise.resolve(speakAssistantResponse(text)).catch(error => {
        console.warn('Voice playback skipped:', error);
      });
    }
  } catch (error) {
    console.warn('Voice controls skipped:', error);
  }
}

async function speakAssistantResponse(text, force=false) {
  return;   // ovoz chiqarish olib tashlandi (/api/voice/speech endpointi ham yo'q)
  /* eslint-disable no-unreachable */
  if (!VOICE_STATE.ready || (!VOICE_STATE.autoSpeak && !force)) return;
  const chunks = voiceSpeechChunks(text);
  if (!chunks.length) return;
  stopVoicePlayback();
  const token = voicePlaybackToken;
  for (const chunk of chunks) {
    if (token !== voicePlaybackToken) return;
    try {
      const response = await fetch('/api/voice/speech', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text:chunk, voice:VOICE_STATE.voice}),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || 'Ovoz yaratilmadi.');
      }
      const url = URL.createObjectURL(await response.blob());
      const player = new Audio(url);
      voicePlayback = player;
      await new Promise((resolve, reject) => {
        player.onended = resolve;
        player.onerror = () => reject(new Error('Audio ijro etilmadi.'));
        player.play().catch(reject);
      });
      URL.revokeObjectURL(url);
    } catch (error) {
      if (force) alert('Ovoz chiqarilmadi: ' + error.message);
      return;
    }
  }
}

function setVoiceCaptureUi(recording) {
  const button = $('#voiceInputBtn');
  if (!button) return;
  button.classList.toggle('recording', recording);
  button.textContent = recording ? '■' : '🎙';
  button.title = recording ? 'Yozishni to‘xtatish' : 'Mikrofondan gapiring';
}

function voiceBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '');
    reader.onerror = () => reject(new Error('Audio o‘qilmadi.'));
    reader.readAsDataURL(blob);
  });
}

async function sendVoiceRecording(blob) {
  const button = $('#voiceInputBtn');
  try {
    if (button) {
      button.disabled = true;
      button.title = 'Ovoz matnga aylantirilmoqda…';
    }
    const response = await fetch('/api/voice/transcribe', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({audio:await voiceBase64(blob), mimeType:blob.type || 'audio/webm'}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Ovoz matnga aylantirilmadi.');
    $('#input').value = payload.text || '';
    $('#input').dispatchEvent(new Event('input'));
    if ($('#input').value.trim()) submit();
  } catch (error) {
    alert('Mikrofon xatosi: ' + error.message);
  } finally {
    if (button) {
      button.disabled = false;
      button.title = 'Mikrofondan gapiring';
    }
  }
}

async function toggleVoiceCapture() {
  if (voiceRecorder && voiceRecorder.state === 'recording') {
    voiceRecorder.stop();
    return;
  }
  if (!VOICE_STATE.ready) {
    alert('Avval Explorer → Sozlamalar ichidan OpenAI Voice API kalitini saqlang.');
    return;
  }
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    alert('Bu brauzer mikrofon yozib olishni qo‘llab-quvvatlamaydi.');
    return;
  }
  try {
    voiceCaptureStream = await navigator.mediaDevices.getUserMedia({
      audio:{echoCancellation:true, noiseSuppression:true, autoGainControl:true},
    });
    const preferred = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg'];
    const mimeType = preferred.find(type => MediaRecorder.isTypeSupported(type)) || '';
    voiceRecorder = new MediaRecorder(voiceCaptureStream, mimeType ? {mimeType} : undefined);
    const chunks = [];
    voiceRecorder.ondataavailable = event => {
      if (event.data && event.data.size) chunks.push(event.data);
    };
    voiceRecorder.onstop = () => {
      clearTimeout(voiceCaptureTimer);
      setVoiceCaptureUi(false);
      if (typeof cgptBeep === 'function') cgptBeep([[620, 0.08]]);  // yozish tugadi
      if (voiceCaptureStream) voiceCaptureStream.getTracks().forEach(track => track.stop());
      voiceCaptureStream = null;
      const blob = new Blob(chunks, {type: voiceRecorder.mimeType || 'audio/webm'});
      voiceRecorder = null;
      if (blob.size > 128) sendVoiceRecording(blob);
    };
    voiceRecorder.start();
    setVoiceCaptureUi(true);
    // mikrofon endi haqiqatan yozayapti — qisqa signal, ekranga qaramasa ham bilinsin
    if (typeof cgptBeep === 'function') cgptBeep([[880, 0.09]]);
    voiceCaptureTimer = setTimeout(() => {
      if (voiceRecorder && voiceRecorder.state === 'recording') voiceRecorder.stop();
    }, 60000);
  } catch (error) {
    setVoiceCaptureUi(false);
    alert('Mikrofonga ruxsat berilmadi: ' + error.message);
  }
}

if ($('#openaiKeySave')) $('#openaiKeySave').onclick = saveVoiceConfig;
if ($('#openaiKeyClear')) $('#openaiKeyClear').onclick = clearVoiceConfig;
if ($('#openaiKeyReveal')) {
  $('#openaiKeyReveal').onclick = () => {
    const input = $('#openaiApiKey');
    if (!input) return;
    const hidden = input.type === 'password';
    input.type = hidden ? 'text' : 'password';
    $('#openaiKeyReveal').textContent = hidden ? '🙈' : '👁';
  };
}
if ($('#openaiApiKey')) {
  $('#openaiApiKey').addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      saveVoiceConfig();
    }
  });
}
if ($('#voiceSelect')) {
  $('#voiceSelect').onchange = event => {
    VOICE_STATE.voice = event.target.value;
    localStorage.setItem('agv_voice', VOICE_STATE.voice);
    if ($('#cgvVoiceSelect')) $('#cgvVoiceSelect').value = VOICE_STATE.voice;
  };
}
if ($('#cgvVoiceSelect')) {
  $('#cgvVoiceSelect').onchange = event => {
    VOICE_STATE.voice = event.target.value;
    localStorage.setItem('agv_voice', VOICE_STATE.voice);
    if ($('#voiceSelect')) $('#voiceSelect').value = VOICE_STATE.voice;
  };
}

/* ══ Ovoz oynasidagi tanlagichlar (sfera ostida) ═══════════════════════════
   Model, nutq→matn modeli va javob tezligi .env ga yoziladi. Bular sessiya
   ochilayotganda yuboriladigan parametrlar, shuning uchun yangi qiymat
   KEYINGI ovozli suhbatda kuchga kiradi — buni izohda aytib turamiz. */
async function initVoiceTune() {
  const mSel = $('#cgvModelSel'), sSel = $('#cgvSttSel');
  const eSel = $('#cgvEagerSel'), vSel = $('#cgvTuneVoice');
  const note = $('#cgvTuneNote');
  if (!mSel || !sSel || !eSel || !vSel) return;

  let cfg;
  try { cfg = await (await fetch('/api/voice/config')).json(); }
  catch (error) { if (note) note.textContent = 'Sozlama o\u2018qilmadi.'; return; }

  const fill = (el, items, current, prefix) => {
    el.innerHTML = '';
    (items || []).forEach(item => {
      const id = typeof item === 'string' ? item : item.id;
      const nm = typeof item === 'string' ? item : (item.name || item.id);
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = prefix + ': ' + nm;
      if (id === current) opt.selected = true;
      el.appendChild(opt);
    });
  };

  fill(mSel, cfg.realtimeModels,   cfg.realtimeModel,      'Model');
  fill(sSel, cfg.transcribeModels, cfg.transcriptionModel, 'Nutq');
  fill(eSel, cfg.eagerLevels,      cfg.eagerness,          'Rejim');
  fill(vSel, cfg.voiceDetails || cfg.voices, VOICE_STATE.voice, 'Ovoz');
  if (note) note.textContent = '';

  const save = async (field, value) => {
    if (note) note.textContent = 'Saqlanmoqda\u2026';
    try {
      const res = await fetch('/api/voice/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      });
      const data = await res.json();
      if (note) {
        note.textContent = data.error
          ? '\u26a0\ufe0f ' + data.error
          : 'Saqlandi \u2014 keyingi ovozli suhbatda kuchga kiradi.';
      }
    } catch (error) {
      if (note) note.textContent = '\u26a0\ufe0f Saqlanmadi: ' + error.message;
    }
  };

  mSel.onchange = event => save('realtimeModel',   event.target.value);
  sSel.onchange = event => save('transcribeModel', event.target.value);
  eSel.onchange = event => save('eagerness',       event.target.value);
  vSel.onchange = event => {
    VOICE_STATE.voice = event.target.value;
    localStorage.setItem('agv_voice', VOICE_STATE.voice);
    if ($('#cgvVoiceSelect')) $('#cgvVoiceSelect').value = VOICE_STATE.voice;
    if ($('#voiceSelect')) $('#voiceSelect').value = VOICE_STATE.voice;
    if (note) note.textContent = 'Ovoz tanlandi \u2014 keyingi suhbatda.';
  };
}
initVoiceTune();


/* ══ DASHBOARD ═════════════════════════════════════════════════════════════
   Ma'lumot manbai: /api/hisob (holat) + /api/hisob/jurnal (zanjir).
   Grafiklar qo'lda chizilgan SVG — tashqi kutubxona yo'q. */
let DASH_JURNAL = [], DASH_VAL = '';

function dashPul(n){
  return Number(n||0).toLocaleString('ru-RU',{maximumFractionDigits:2}).replace(/ /g,' ');
}
function dashSanaqisqa(iso){
  return iso ? iso.slice(8,10) + '.' + iso.slice(5,7) : '';
}

async function dashOchish(){
  document.getElementById('dashOverlay').classList.add('on');
  dashModelToldir();
  await dashYangila();
}
function dashYop(){ document.getElementById('dashOverlay').classList.remove('on'); }

async function dashYangila(){
  try{
    const [hr, jr] = await Promise.all([
      fetch('/api/hisob').then(r=>r.json()),
      fetch('/api/hisob/jurnal?limit=1000').then(r=>r.json()),
    ]);
    if(hr.status!=='ok'||jr.status!=='ok') throw new Error(hr.error||jr.error||'xato');
    DASH_JURNAL = jr.jurnal || [];
    dashChiz(hr.hisob);
  }catch(e){
    document.getElementById('dashSub').textContent = '⚠ ' + e.message;
  }
}

function dashChiz(h){
  const klar = h.kassalar||[], vlar = h.valyutalar||[];
  document.getElementById('dashSub').textContent =
    (h.amallar_soni||0) + ' amal · ' + klar.length + ' kassa · ' + vlar.length + ' valyuta';

  /* — kartalar — */
  const karta = (bolim, sinf, yorliq, qiymat, ost) =>
    '<button type="button" class="dash-card ' + sinf + '" data-bolim="' + esc(bolim) + '">'
    + '<div class="dc-l">' + yorliq + '</div>'
    + '<div class="dc-v">' + qiymat + '</div>'
    + '<div class="dc-s">' + ost + '</div></button>';

  let cards = '';
  klar.forEach(k => {
    cards += karta(k.nom, k.qoldiq<0?'qizil':k.qoldiq>0?'yashil':'',
      '🏦 ' + esc(k.nom), dashPul(k.qoldiq) + ' ' + esc(k.valyuta), 'kassa · harakatlar');
  });
  cards += karta('ombor', '', '📦 Ombor', dashPul(h.ombor.jami_qiymat),
    h.ombor.tur_soni + ' xil tovar · barkodlar');
  cards += karta('qarzdorlar', 'yashil', '↓ Qarzdorlar', dashPul(h.qarzdorlar.jami),
    h.qarzdorlar.odamlar.length + ' kishi');
  cards += karta('qarzlarim', 'qizil', '↑ Qarzlarim', dashPul(h.qarzlarim.jami),
    h.qarzlarim.odamlar.length + ' kishi');
  cards += karta('foyda', h.foyda.sof<0?'qizil':h.foyda.sof>0?'yashil':'',
    '💰 Sof foyda', dashPul(h.foyda.sof),
    'savdo ' + dashPul(h.foyda.savdo)
      + (h.foyda.boshqa_kirim ? ' · kirim ' + dashPul(h.foyda.boshqa_kirim) : ''));
  document.getElementById('dashCards').innerHTML = cards;

  // Kartani bosish — tafsilot ochiladi/yopiladi
  document.querySelectorAll('.dash-card').forEach(c =>
    c.onclick = () => dashTafOch(c.dataset.bolim, h));
  if(DASH_TAF){ const saqlangan = DASH_TAF; DASH_TAF = ''; dashTafOch(saqlangan, h); }

  /* — chiziqli grafik: har valyutaning yig'ma qoldig'i — */
  dashChiziqChiz();

  /* — valyuta tanlovi (ustunlar uchun) — */
  const vset = [...new Set(DASH_JURNAL.map(y=>y.valyuta))];
  if(!DASH_VAL || !vset.includes(DASH_VAL)) DASH_VAL = vset[0]||'';
  document.getElementById('dashValTanlov').innerHTML = vset.map(v =>
    '<button type="button" class="'+(v===DASH_VAL?'on':'')+'" data-val="'+esc(v)+'">'+esc(v)+'</button>').join('');
  document.querySelectorAll('#dashValTanlov button').forEach(b =>
    b.onclick = () => { DASH_VAL = b.dataset.val; dashChiz(h); });
  dashUstunChiz();

  dashJadvalChiz();
}

/* Zanjir jadvali — qidiruv bilan filtrlanadi, klaviatura shu yerda ishlaydi.
   Yangi qo'shilgan amal bir zumga yashil yonib o'tadi. */
let DASH_KORILGAN = new Set();
function dashJadvalChiz(){
  const qidir = (document.getElementById('dashQidir')||{}).value || '';
  const q = qidir.trim().toLowerCase();
  const badge = t => {
    const c = (typeof CHEK_TUR!=='undefined' && CHEK_TUR[t]) || {rang:'#5f6368', belgi:'•', nom:t};
    return '<span class="dash-tur" style="background:'+c.rang+'">'+c.belgi+' '+esc(c.nom)+'</span>';
  };
  const royxat = DASH_JURNAL.slice().reverse().filter(y => {
    if(!q) return true;
    return [y.kim, y.tovar, y.izoh, y.kassa, y.valyuta, y.tur,
            (CHEK_TUR[y.tur]||{}).nom, String(y.summa), String(y.qoldiq)]
      .filter(Boolean).join(' ').toLowerCase().includes(q);
  });

  document.getElementById('dashTana').innerHTML = royxat.map((y, idx) => {
    const taf = [y.kim, y.tovar && (y.tovar+(y.miqdor?' '+y.miqdor+' '+y.birlik:'')), y.izoh]
      .filter(Boolean).join(' · ');
    const oz = y.ozgarish;
    const ozTxt = oz>0 ? '+'+dashPul(oz) : oz<0 ? '−'+dashPul(-oz) : '0';
    const ozCls = oz>0?'musbat':oz<0?'manfiy':'nol';
    const yangi = !DASH_KORILGAN.has(y.id + '|' + y.kassa);
    return '<tr data-idx="'+idx+'" data-id="'+esc(y.id)+'" data-taf="'+esc(taf||y.tur)+'"'
      + (yangi ? ' class="yangi"' : '') + '>'
      +'<td>'+esc((y.sana||'').replace('T',' ').slice(0,16))+'</td>'
      +'<td>'+badge(y.tur)+'</td>'
      +'<td>'+(taf ? esc(taf) : '<span class="dash-muted">—</span>')+'</td>'
      +'<td>'+esc(y.kassa)+'</td>'
      +'<td class="son '+ozCls+'">'+ozTxt+' '+esc(y.valyuta)+'</td>'
      +'<td class="son"><b>'+dashPul(y.qoldiq)+'</b> '+esc(y.valyuta)+'</td></tr>';
  }).join('') || '<tr><td colspan="6" class="dash-muted">'
      + (q ? 'Topilmadi' : 'Hali amallar yo\'q') + '</td></tr>';

  DASH_JURNAL.forEach(y => DASH_KORILGAN.add(y.id + '|' + y.kassa));

  // sichqoncha bilan ham tanlansin
  dashQatorlar().forEach((tr, i) => {
    tr.onclick = () => dashTanla(i);
    tr.ondblclick = () => { dashTanla(i); dashTafsilot(); };
  });
  if(DASH_TANLOV >= 0) dashTanla(Math.min(DASH_TANLOV, dashQatorlar().length - 1));
}

/* chiziqli grafik: jurnal bo'ylab har valyutaning yig'ma yo'li */
function dashChiziqChiz(){
  const box = document.getElementById('dashChiziq');
  const RANG = ['#4ade80','#60a5fa','#f472b6','#fbbf24','#a78bfa'];
  const vset = [...new Set(DASH_JURNAL.map(y=>y.valyuta))];
  if(!DASH_JURNAL.length || !vset.length){ box.innerHTML='<div class="dash-muted">Ma\'lumot yo\'q</div>'; return; }

  // har qadamda har valyutaning yig'indisi (kassalar bo'ylab)
  const run = {}; const seriya = {}; vset.forEach(v => seriya[v]=[]);
  DASH_JURNAL.forEach(y => {
    run[y.valyuta] = (run[y.valyuta]||0) + y.ozgarish;
    vset.forEach(v => seriya[v].push(run[v]||0));
  });
  const N = DASH_JURNAL.length;
  const W=460,H=170,P=34;
  let mn=0,mx=0;
  vset.forEach(v => seriya[v].forEach(q => { mn=Math.min(mn,q); mx=Math.max(mx,q); }));
  if(mn===mx){ mx=mn+1; }
  const X = i => P + (N<2?0:(W-P-8)*i/(N-1));
  const Y = q => 8 + (H-30-8)*(1-(q-mn)/(mx-mn));
  let svg = '<svg viewBox="0 0 '+W+' '+H+'">';
  // gorizontal to'r: 0 chizig'i + min/max
  [mn,0,mx].forEach(q => {
    if(q<mn||q>mx) return;
    svg += '<line x1="'+P+'" y1="'+Y(q)+'" x2="'+(W-6)+'" y2="'+Y(q)
      +'" stroke="currentColor" opacity="'+(q===0?'.3':'.12')+'" stroke-width="1"/>'
      +'<text x="2" y="'+(Y(q)+3)+'" font-size="8.5" fill="currentColor" opacity=".55">'
      +dashPul(q)+'</text>';
  });
  vset.forEach((v,i) => {
    const pts = seriya[v].map((q,j)=>X(j).toFixed(1)+','+Y(q).toFixed(1)).join(' ');
    svg += '<polyline points="'+pts+'" fill="none" stroke="'+RANG[i%RANG.length]
      +'" stroke-width="2" stroke-linejoin="round"/>';
    const oxg = seriya[v][N-1];
    svg += '<circle cx="'+X(N-1)+'" cy="'+Y(oxg)+'" r="3" fill="'+RANG[i%RANG.length]+'"/>';
  });
  // legenda
  let lx = P;
  vset.forEach((v,i) => {
    svg += '<rect x="'+lx+'" y="'+(H-13)+'" width="9" height="9" rx="2" fill="'+RANG[i%RANG.length]+'"/>'
      +'<text x="'+(lx+13)+'" y="'+(H-5)+'" font-size="9.5" fill="currentColor" opacity=".8">'+esc(v)+'</text>';
    lx += 13 + v.length*6.5 + 16;
  });
  svg += '</svg>';
  box.innerHTML = svg;
}

/* ustunlar: tanlangan valyutada kunlik kirim (yashil) / chiqim (qizil) */
function dashUstunChiz(){
  const box = document.getElementById('dashUstun');
  const yoz = DASH_JURNAL.filter(y => y.valyuta===DASH_VAL && y.ozgarish!==0);
  if(!yoz.length){ box.innerHTML='<div class="dash-muted">'+esc(DASH_VAL||'—')+' bo\'yicha harakat yo\'q</div>'; return; }
  const kunlar = {};
  yoz.forEach(y => {
    const k = (y.sana||'').slice(0,10);
    kunlar[k] = kunlar[k] || {kirim:0, chiqim:0};
    if(y.ozgarish>0) kunlar[k].kirim += y.ozgarish; else kunlar[k].chiqim += -y.ozgarish;
  });
  const sanalar = Object.keys(kunlar).sort();
  const W=460,H=170,P=34, tepa=10, past=26;
  const mx = Math.max(...sanalar.map(s=>Math.max(kunlar[s].kirim,kunlar[s].chiqim)),1);
  const bw = Math.min(26, (W-P-10)/sanalar.length/2 - 4);
  let svg = '<svg viewBox="0 0 '+W+' '+H+'">';
  svg += '<line x1="'+P+'" y1="'+(H-past)+'" x2="'+(W-6)+'" y2="'+(H-past)
    +'" stroke="currentColor" opacity=".3"/>';
  [mx/2,mx].forEach(q => {
    const y = H-past-(H-past-tepa)*q/mx;
    svg += '<line x1="'+P+'" y1="'+y+'" x2="'+(W-6)+'" y2="'+y
      +'" stroke="currentColor" opacity=".1"/>'
      +'<text x="2" y="'+(y+3)+'" font-size="8.5" fill="currentColor" opacity=".55">'+dashPul(q)+'</text>';
  });
  sanalar.forEach((s,i) => {
    const cx = P + (W-P-10)*(i+0.5)/sanalar.length;
    const hK = (H-past-tepa)*kunlar[s].kirim/mx;
    const hC = (H-past-tepa)*kunlar[s].chiqim/mx;
    if(kunlar[s].kirim>0)  svg += '<rect x="'+(cx-bw-2)+'" y="'+(H-past-hK)+'" width="'+bw+'" height="'+hK+'" rx="3" fill="#4ade80"/>';
    if(kunlar[s].chiqim>0) svg += '<rect x="'+(cx+2)+'" y="'+(H-past-hC)+'" width="'+bw+'" height="'+hC+'" rx="3" fill="#f87171"/>';
    svg += '<text x="'+cx+'" y="'+(H-past+13)+'" font-size="9" text-anchor="middle" fill="currentColor" opacity=".7">'+dashSanaqisqa(s)+'</text>';
  });
  svg += '</svg>';
  box.innerHTML = svg;
}



/* ══ EAN-13 chizish ════════════════════════════════════════════════════════
   Haqiqiy standart bo'yicha: chap yarmi L/G jadvallaridan (birinchi raqam
   qaysi naqsh ekanini belgilaydi), o'ng yarmi R jadvalidan. Skaner o'qiy
   oladigan chinakam barkod, rasm emas. */
const EAN_L = ['0001101','0011001','0010011','0111101','0100011',
               '0110001','0101111','0111011','0110111','0001011'];
const EAN_G = ['0100111','0110011','0011011','0100001','0011101',
               '0111001','0000101','0010001','0001001','0010111'];
const EAN_R = ['1110010','1100110','1101100','1000010','1011100',
               '1001110','1010000','1000100','1001000','1110100'];
const EAN_NAQSH = ['LLLLLL','LLGLGG','LLGGLG','LLGGGL','LGLLGG',
                   'LGGLLG','LGGGLL','LGLGLG','LGLGGL','LGGLGL'];

function barkodSvg(kod, h){
  const balandlik = h || 34;
  kod = String(kod || '');
  if(!/^\d{13}$/.test(kod)){
    // EAN-13 emas (masalan Code128 yoki ichki kod) — oddiy chiziq sifatida
    return '<svg class="bk-svg" height="'+balandlik+'" width="120">'
      + '<rect width="120" height="'+balandlik+'" fill="#fff"/>'
      + '<text x="60" y="'+(balandlik/2+4)+'" font-size="10" text-anchor="middle" '
      + 'fill="#555" font-family="monospace">' + esc(kod.slice(0,16)) + '</text></svg>';
  }
  const naqsh = EAN_NAQSH[+kod[0]];
  let bitlar = '101';                                   // boshlang'ich qo'riqchi
  for(let i = 1; i <= 6; i++)
    bitlar += (naqsh[i-1] === 'L' ? EAN_L : EAN_G)[+kod[i]];
  bitlar += '01010';                                    // markaziy qo'riqchi
  for(let i = 7; i <= 12; i++) bitlar += EAN_R[+kod[i]];
  bitlar += '101';                                      // yakuniy qo'riqchi

  // Modul kengligi va tinch zona standart nisbatlarda — skaner o'qishi uchun
  // chetlarda kamida 9 modul bo'sh joy qolishi shart.
  const w = (h && h > 60) ? 3 : 2;
  const tinch = 9 * w;                    // chetdagi bo'sh joy (skaner uchun shart)
  const chetPast = Math.round(balandlik * 0.12);   // oddiy chiziqlar shuncha kalta
  const kenglik = bitlar.length * w + tinch * 2;
  let chiziq = '';
  for(let i = 0; i < bitlar.length; i++){
    if(bitlar[i] !== '1') continue;
    // qo'riqchi chiziqlari pastroqqa cho'ziladi — standart shunday
    const qoriq = (i < 3) || (i >= 45 && i < 50) || (i >= bitlar.length - 3);
    chiziq += '<rect x="'+(tinch + i*w).toFixed(2)+'" y="0" width="'+w
      + '" height="'+(balandlik - (qoriq ? 0 : chetPast))+'" fill="#111"/>';
  }
  const fs = Math.max(8, Math.round(balandlik * 0.24));
  const matn = '<text x="'+(tinch - 7*w/2)+'" y="'+balandlik+'" font-size="'+fs
      + '" text-anchor="middle" fill="#111" font-family="monospace">'+kod[0]+'</text>'
    + '<text x="'+(tinch + 3*w + 21*w)+'" y="'+balandlik+'" font-size="'+fs
      + '" text-anchor="middle" fill="#111" font-family="monospace" letter-spacing="'+(w*0.5)+'">'
      + kod.slice(1,7) + '</text>'
    + '<text x="'+(tinch + 50*w + 21*w)+'" y="'+balandlik+'" font-size="'+fs
      + '" text-anchor="middle" fill="#111" font-family="monospace" letter-spacing="'+(w*0.5)+'">'
      + kod.slice(7) + '</text>';
  return '<svg class="bk-svg" width="'+kenglik+'" height="'+(balandlik+fs+2)+'" '
    + 'viewBox="0 0 '+kenglik+' '+(balandlik+fs+2)+'">'
    + '<rect width="'+kenglik+'" height="'+(balandlik+fs+2)+'" fill="#fff"/>'
    + chiziq + matn + '</svg>';
}


/* Barkodni katta qilib ko'rsatadi — telefon skaneri ekrandan o'qishi uchun
   modul kengligi 3px, tinch zonalar joyida. Chop etsa ham yaroqli. */
function barkodKatta(kod, nom){
  if(!kod) return;
  const eski = document.getElementById('bkKatta');
  if(eski) eski.remove();
  const d = document.createElement('div');
  d.id = 'bkKatta';
  d.innerHTML = '<div class="bk-katta-ich">'
    + '<div class="bk-katta-nom">' + esc(nom || '') + '</div>'
    + barkodSvg(kod, 110)
    + '<div class="bk-katta-kod">' + esc(kod) + '</div>'
    + '<div class="bk-katta-izoh">Skaner bilan o\'qish uchun telefonni 15–25 sm masofada tuting</div>'
    + '<div class="bk-katta-tugma">'
      + '<button type="button" id="bkChop">🖨 Chop etish</button>'
      + '<button type="button" id="bkYop">Yopish</button>'
    + '</div></div>';
  document.body.appendChild(d);
  d.onclick = e => { if(e.target === d) d.remove(); };
  d.querySelector('#bkYop').onclick = () => d.remove();
  d.querySelector('#bkChop').onclick = () => {
    const w = window.open('', '_blank', 'width=420,height=320');
    w.document.write('<body style="margin:0;display:flex;align-items:center;'
      + 'justify-content:center;height:100vh;font-family:monospace">'
      + '<div style="text-align:center">' + barkodSvg(kod, 110)
      + '<div style="margin-top:6px;font-size:13px">' + esc(nom || '') + '</div></div></body>');
    w.document.close();
    setTimeout(() => w.print(), 250);
  };
}

/* ══ Karta bosilganda tafsilot ═════════════════════════════════════════════ */
let DASH_TAF = '';
let OMBOR_LOK = '';   // ombor tafsilotida tanlangan joy

function dashTafYop(){
  DASH_TAF = '';
  document.getElementById('dashTafsilot').classList.remove('on');
  document.querySelectorAll('.dash-card').forEach(c => c.classList.remove('faol'));
}

function dashTafOch(bolim, h){
  if(DASH_TAF === bolim){ dashTafYop(); return; }
  DASH_TAF = bolim;
  const box = document.getElementById('dashTafsilot');
  document.querySelectorAll('.dash-card').forEach(c =>
    c.classList.toggle('faol', c.dataset.bolim === bolim));

  let sarlavha = '', ichi = '';

  if(bolim === 'ombor'){
    sarlavha = '📦 Ombor qoldig\'i';
    const tv = (h.ombor && h.ombor.tovarlar) || [];
    const loks = (h.ombor && h.ombor.lokatsiyalar) || [];

    if(!tv.length){
      ichi = '<div class="dash-muted">Omborda tovar yo\'q.</div>';
    } else {
      // Lokatsiya chiplari: qayerda qancha turibdi. Bosilsa shu joy bo'yicha filtr.
      const jamiQiymat = tv.reduce((a,t) => a + (t.qiymat||0), 0);
      let chiplar = '<button type="button" class="lok-chip'
        + (OMBOR_LOK ? '' : ' on') + '" data-lok="">Hammasi'
        + '<b>' + dashPul(jamiQiymat) + '</b></button>';
      loks.forEach(l => {
        chiplar += '<button type="button" class="lok-chip'
          + (OMBOR_LOK === l.nom ? ' on' : '') + '" data-lok="' + esc(l.nom) + '">'
          + esc(l.nom) + '<b>' + dashPul(l.jami_qiymat) + '</b></button>';
      });

      // Tanlangan joyga qarab ro'yxat
      let qatorlar;
      if(OMBOR_LOK){
        const lok = loks.find(l => l.nom === OMBOR_LOK);
        qatorlar = ((lok && lok.tovarlar) || []).map(t => {
          const toliq = tv.find(x => x.nom === t.nom) || {};
          return Object.assign({}, toliq, t, {joylar: null});
        });
      } else {
        qatorlar = tv.map(t => Object.assign({}, t, {
          joylar: (t.lokatsiyalar || []).filter(x => Math.abs(x.miqdor) > 0.0001)
        }));
      }

      const qatorHtml = qatorlar.map(t => {
        const joy = t.joylar && t.joylar.length
          ? '<div class="lok-taqsim">' + t.joylar.map(j =>
              '<span>' + esc(j.lokatsiya) + ' <b>' + dashPul(j.miqdor) + '</b></span>').join('')
            + '</div>'
          : '';
        const rasm = t.rasm
          ? '<img class="omb-rasm" src="' + esc(t.rasm) + '" alt="" loading="lazy" '
            + 'onerror="this.outerHTML=\'<div class=&quot;omb-rasm yoq&quot;>📦</div>\'">'
          : '<div class="omb-rasm yoq">📦</div>';
        return '<tr>'
          + '<td class="omb-rasm-td"><button class="omb-rasm-btn" data-rasm="' + esc(t.nom)
            + '" title="Rasm qo\'yish yoki o\'zgartirish">' + rasm + '</button></td>'
          + '<td><div class="omb-nom">' + esc(t.nom) + '</div>' + joy + '</td>'
          + '<td><div class="bk-hujayra">'
            + '<button class="bk-katta" data-katta="' + esc(t.barkod||'') + '" '
            + 'data-nom="' + esc(t.nom) + '" title="Kattalashtirish · chop etish">'
            + barkodSvg(t.barkod, 30) + '</button>'
            + '<button class="bk-tahrir" data-bk="' + esc(t.nom) + '" '
            + 'title="Barkodni o\'zgartirish">✎</button></div>'
            + '<div class="bk-raqam">' + esc(t.barkod || '—') + '</div></td>'
          + '<td class="son"><b>' + dashPul(t.miqdor) + '</b> '
            + '<span class="dash-muted">' + esc(t.birlik||'') + '</span></td>'
          + '<td class="son">' + dashPul(t.tan_narx) + '</td>'
          + '<td class="son">' + (t.sotuv_narx ? dashPul(t.sotuv_narx)
              : '<span class="dash-muted">—</span>') + '</td>'
          + '<td class="son"><b>' + dashPul(t.qiymat) + '</b></td></tr>';
      }).join('');

      const jamiKorinadigan = qatorlar.reduce((a,t) => a + (t.qiymat||0), 0);
      ichi = '<div class="lok-chiplar">' + chiplar + '</div>'
        + '<table class="dash-taf-jadval omb-jadval"><thead><tr>'
        + '<th></th>'
        + '<th>Tovar' + (OMBOR_LOK ? '' : ' · qayerda') + '</th><th>Barkod</th>'
        + '<th class="son">Qoldiq</th><th class="son">Tan narx</th>'
        + '<th class="son">Sotuv narx</th><th class="son">Qiymat</th></tr></thead>'
        + '<tbody>' + qatorHtml + '</tbody>'
        + '<tfoot><tr><td colspan="6" class="son"><b>JAMI</b></td>'
        + '<td class="son"><b>' + dashPul(jamiKorinadigan) + '</b></td></tr></tfoot>'
        + '</table>';
    }
  }
  else if(bolim === 'qarzdorlar' || bolim === 'qarzlarim'){
    sarlavha = bolim === 'qarzdorlar' ? '↓ Menga qarzdorlar' : '↑ Mening qarzlarim';
    const odamlar = (h[bolim] && h[bolim].odamlar) || [];
    ichi = odamlar.length
      ? '<table class="dash-taf-jadval"><thead><tr><th>Kim</th>'
        + '<th class="son">Summa</th></tr></thead><tbody>'
        + odamlar.map(o => '<tr><td>' + esc(o.kim) + '</td>'
            + '<td class="son"><b>' + dashPul(o.summa) + '</b></td></tr>').join('')
        + '</tbody></table>'
      : '<div class="dash-muted">Ro\'yxat bo\'sh.</div>';
  }
  else if(bolim === 'foyda'){
    sarlavha = '💰 Foyda tarkibi';
    const f = h.foyda || {};
    const qator = (n, v, b) => '<tr><td>' + esc(n) + '</td><td class="son"'
      + (b ? '><b>' : '>') + dashPul(v) + (b ? '</b>' : '') + '</td></tr>';
    ichi = '<table class="dash-taf-jadval"><tbody>'
      + qator('Savdo tushumi', f.savdo)
      + qator('Tannarx', -f.tannarx)
      + qator('Yalpi foyda', f.yalpi, true)
      + qator('Xarajat', -f.xarajat)
      + qator('SOF FOYDA', f.sof, true)
      + '</tbody></table>'
      + (f.boshqa_kirim ? '<div class="dash-muted" style="margin-top:8px">Kassaga solingan pul ('
          + dashPul(f.boshqa_kirim) + ') foydaga kirmaydi — u alohida hisoblanadi.</div>' : '');
  }
  else {
    // kassa kartasi — o'sha kassaning harakatlari
    sarlavha = '🏦 ' + bolim;
    const yoz = DASH_JURNAL.filter(y => y.kassa === bolim).slice().reverse();
    ichi = yoz.length
      ? '<table class="dash-taf-jadval"><thead><tr><th>Sana</th><th>Amal</th>'
        + '<th class="son">O\'zgarish</th><th class="son">Qoldiq</th></tr></thead><tbody>'
        + yoz.map(y => {
            const c = (CHEK_TUR[y.tur]||{});
            const oz = y.ozgarish;
            return '<tr><td>' + esc((y.sana||'').replace('T',' ').slice(0,16)) + '</td>'
              + '<td><span class="dash-tur" style="background:' + (c.rang||'#5f6368') + '">'
                + (c.belgi||'•') + ' ' + esc(c.nom||y.tur) + '</span></td>'
              + '<td class="son ' + (oz>0?'musbat':oz<0?'manfiy':'nol') + '">'
                + (oz>0?'+':oz<0?'−':'') + dashPul(Math.abs(oz)) + '</td>'
              + '<td class="son"><b>' + dashPul(y.qoldiq) + '</b> ' + esc(y.valyuta) + '</td></tr>';
          }).join('')
        + '</tbody></table>'
      : '<div class="dash-muted">Bu kassada harakat yo\'q.</div>';
  }

  box.innerHTML = '<div class="dash-taf-bosh"><b>' + sarlavha + '</b>'
    + '<button class="yop" type="button" title="Yopish">✕</button></div>' + ichi;
  box.classList.add('on');
  box.querySelector('.yop').onclick = dashTafYop;

  // lokatsiya chiplari
  box.querySelectorAll('[data-lok]').forEach(c => c.onclick = () => {
    OMBOR_LOK = c.dataset.lok;
    DASH_TAF = '';
    dashTafOch('ombor', h);
  });

  // barkodni kattalashtirish — skaner uchun
  box.querySelectorAll('[data-katta]').forEach(b => b.onclick = () =>
    barkodKatta(b.dataset.katta, b.dataset.nom));

  // rasm qo'yish
  box.querySelectorAll('[data-rasm]').forEach(b => b.onclick = async () => {
    const tovar = b.dataset.rasm;
    const joriy = (h.ombor.tovarlar.find(t => t.nom === tovar) || {}).rasm || '';
    const manzil = prompt('«' + tovar + '» uchun rasm manzili:\n'
      + '(fayl yo\'li yoki to\'liq URL · bo\'sh qoldirsangiz o\'chiriladi)', joriy);
    if(manzil === null) return;
    try{
      const r = await fetch('/api/hisob/rasm', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(manzil.trim()
          ? {amal:'biriktirish', tovar: tovar, rasm: manzil.trim()}
          : {amal:'ochirish', tovar: tovar})
      });
      const d = await r.json();
      if(d.status !== 'ok'){ alert('Bajarilmadi: ' + (d.error||'')); return; }
      HISOB = d.hisob; paintHisob();
      await dashYangila();
      DASH_TAF = ''; dashTafOch('ombor', HISOB);
    }catch(e){ alert('Serverga ulanib bo\'lmadi: ' + e.message); }
  });

  // barkodni tahrirlash
  box.querySelectorAll('[data-bk]').forEach(b => b.onclick = async () => {
    const tovar = b.dataset.bk;
    const joriy = (h.ombor.tovarlar.find(t => t.nom === tovar) || {}).barkod || '';
    const yangi = prompt('«' + tovar + '» uchun barkod:\n(bo\'sh qoldirsangiz avtomatik yasaladi)', joriy);
    if(yangi === null) return;
    try{
      const r = await fetch('/api/hisob/barkod', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({amal:'biriktirish', tovar: tovar, barkod: yangi.trim()})
      });
      const d = await r.json();
      if(d.status !== 'ok'){ alert('Biriktirilmadi: ' + (d.error||'')); return; }
      HISOB = d.hisob; paintHisob();
      await dashYangila();
      dashTafOch('ombor', HISOB); DASH_TAF = 'ombor';
    }catch(e){ alert('Serverga ulanib bo\'lmadi: ' + e.message); }
  });

  box.scrollIntoView({block:'nearest', behavior:'smooth'});
}

/* ══ Dashboard suhbati ═════════════════════════════════════════════════════
   Asosiy chat quvuridan (/api/chat) foydalanadi, lekin alohida sessiyada —
   shunda dashboarddagi yozishmalar asosiy suhbatni chalkashtirmaydi.
   Agent ma'lumot yetishmasa savol beradi (tizim ko'rsatmasida shunday);
   amal yozilsa chek chiqadi va panel darrov yangilanadi. */
const DASH_SID = 'dashboard';
let dashBusy = false;

const DASH_TEZ = [
  'Tovar sotib oldim',
  'Tovar sotdim',
  'Qarz berdim',
  'Qarz oldim',
  'Xarajat qildim',
  'Pul o\'tkazdim',
];

function dashChatQator(matn, sinf){
  const box = document.getElementById('dashChat');
  const d = document.createElement('div');
  d.className = 'dmsg ' + (sinf || 'a');
  d.textContent = matn;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
  return d;
}

function dashTezChiz(){
  const box = document.getElementById('dashTez');
  if(!box) return;
  box.innerHTML = DASH_TEZ.map(t => '<button type="button">' + esc(t) + '</button>').join('');
  box.querySelectorAll('button').forEach(b => b.onclick = () => {
    const inp = document.getElementById('dashInput');
    inp.value = b.textContent;
    inp.focus();
  });
}

async function dashYubor(){
  const inp = document.getElementById('dashInput');
  const btn = document.getElementById('dashSend');
  const matn = inp.value.trim();
  if(!matn || dashBusy) return;

  dashBusy = true;
  btn.disabled = true;
  inp.value = '';
  inp.style.height = 'auto';
  dashChatQator(matn, 'u');

  const kutish = dashChatQator('…', 'step');
  let javob = '';
  let chekBor = false;

  try{
    const r = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        prompt: matn,
        model: (document.getElementById('dashModel')||{}).value || '',
        cont: true,
        folder: (document.getElementById('folder')||{}).value || '',
        session: DASH_SID,
      })
    });
    if(!r.ok) throw new Error('Server xatosi ' + r.status);

    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = '';
    while(true){
      const {value, done} = await reader.read();
      if(done) break;
      buf += dec.decode(value, {stream:true});
      let i;
      while((i = buf.indexOf('\n\n')) >= 0){
        const chunk = buf.slice(0, i); buf = buf.slice(i+2);
        for(const ln of chunk.split('\n')){
          if(!ln.startsWith('data:')) continue;
          let o; try{ o = JSON.parse(ln.slice(5).trim()); }catch(e){ continue; }

          if(o.action) kutish.textContent = o.action + (o.detail ? ' — ' + o.detail : '');
          if(o.delta)  javob += o.delta;
          if(o.chek){ chekBor = true; dashChekChiz(o.chek); }
          if(o.error){ kutish.remove(); dashChatQator('⚠️ ' + o.error, 'a'); }
          if(o.done){
            const t = (o.text || javob || '').trim();
            javob = t || javob;          // yakuniy matn ham "javob" deb sanalsin
            kutish.remove();
            if(t){
              // savol bo'lsa boshqacha rangda — ko'zga tashlansin
              dashChatQator(t, /\?\s*$/.test(t) ? 'q' : 'a');
            }
          }
        }
      }
    }
    if(kutish.isConnected) kutish.remove();
    if(!chekBor && !javob.trim()) dashChatQator('(javob bo\'sh)', 'a');
  }catch(e){
    if(kutish.isConnected) kutish.remove();
    dashChatQator('⚠️ ' + e.message, 'a');
  }finally{
    dashBusy = false;
    btn.disabled = false;
    inp.focus();
    await dashYangila();          // panel, grafik va zanjir yangilanadi
  }
}

/* chekni dashboard suhbatiga chizadi (chatArea o'rniga) */
function dashChekChiz(chek){
  const box = document.getElementById('dashChat');
  const asl = chatArea;
  try{
    // chekChiz chatArea ga yozadi — vaqtincha yo'naltiramiz
    window.chatArea = box;
    chekChiz(chek);
  }finally{
    window.chatArea = asl;
  }
  box.scrollTop = box.scrollHeight;
}

/* ── Excel uslubidagi klaviatura ── */
let DASH_TANLOV = -1;

function dashQatorlar(){
  return Array.from(document.querySelectorAll('#dashTana tr[data-idx]'));
}
function dashTanla(i){
  const qs = dashQatorlar();
  if(!qs.length) return;
  DASH_TANLOV = Math.max(0, Math.min(qs.length - 1, i));
  qs.forEach((tr, j) => tr.classList.toggle('tanlangan', j === DASH_TANLOV));
  const tr = qs[DASH_TANLOV];
  if(tr) tr.scrollIntoView({block:'nearest'});
}
function dashTanlangan(){
  const qs = dashQatorlar();
  return (DASH_TANLOV >= 0 && DASH_TANLOV < qs.length) ? qs[DASH_TANLOV] : null;
}

async function dashOchir(){
  const tr = dashTanlangan();
  if(!tr) return;
  const id = tr.dataset.id, taf = tr.dataset.taf || '';
  if(!confirm('Shu amal o\'chirilsinmi?\n\n' + taf
              + '\n\nQoldiqlar avtomatik qayta hisoblanadi.')) return;
  try{
    const r = await fetch('/api/hisob/amal', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({amal:'ochirish', id: id})
    });
    const d = await r.json();
    if(d.status !== 'ok'){ alert('O\'chirilmadi: ' + (d.error||'')); return; }
    HISOB = d.hisob; paintHisob();
    await dashYangila();
  }catch(e){ alert('Serverga ulanib bo\'lmadi: ' + e.message); }
}

function dashTafsilot(){
  const tr = dashTanlangan();
  if(!tr) return;
  const y = DASH_JURNAL.find(x => x.id === tr.dataset.id);
  if(!y) return;
  const q = [];
  q.push('Sana: ' + (y.sana||'').replace('T',' ').slice(0,19));
  q.push('Amal: ' + ((CHEK_TUR[y.tur]||{}).nom || y.tur));
  if(y.kim)   q.push('Kim: ' + y.kim);
  if(y.tovar) q.push('Tovar: ' + y.tovar + (y.miqdor ? ' — ' + y.miqdor + ' ' + y.birlik : ''));
  if(y.tolov) q.push('To\'lov: ' + y.tolov);
  if(y.izoh)  q.push('Izoh: ' + y.izoh);
  q.push('Kassa: ' + y.kassa);
  q.push('O\'zgarish: ' + (y.ozgarish>0?'+':'') + dashPul(y.ozgarish) + ' ' + y.valyuta);
  q.push('Keyingi qoldiq: ' + dashPul(y.qoldiq) + ' ' + y.valyuta);
  q.push('ID: ' + y.id);
  alert(q.join('\n'));
}

document.addEventListener('keydown', e => {
  const ov = document.getElementById('dashOverlay');
  if(!ov || !ov.classList.contains('on')) return;
  const inp = document.getElementById('dashInput');
  const qid = document.getElementById('dashQidir');
  const yozayapti = document.activeElement === inp || document.activeElement === qid;

  if(e.key === '/' && !yozayapti){ e.preventDefault(); qid.focus(); qid.select(); return; }
  if(e.key === 'Escape' && yozayapti){ document.activeElement.blur(); return; }
  if(yozayapti) return;

  if(e.key === 'ArrowDown' || e.key === 'j'){ e.preventDefault(); dashTanla(DASH_TANLOV + 1); }
  else if(e.key === 'ArrowUp' || e.key === 'k'){ e.preventDefault(); dashTanla(DASH_TANLOV - 1); }
  else if(e.key === 'Home'){ e.preventDefault(); dashTanla(0); }
  else if(e.key === 'End'){ e.preventDefault(); dashTanla(dashQatorlar().length - 1); }
  else if(e.key === 'PageDown'){ e.preventDefault(); dashTanla(DASH_TANLOV + 10); }
  else if(e.key === 'PageUp'){ e.preventDefault(); dashTanla(DASH_TANLOV - 10); }
  else if(e.key === 'Enter'){ e.preventDefault(); dashTafsilot(); }
  else if(e.key === 'Delete' || e.key === 'Backspace'){ e.preventDefault(); dashOchir(); }
  else if(e.key === 'n'){ e.preventDefault(); inp.focus(); }
});

if(document.getElementById('dashBtn'))    document.getElementById('dashBtn').onclick = dashOchish;
if(document.getElementById('dashSend'))   document.getElementById('dashSend').onclick = dashYubor;
if(document.getElementById('dashInput')){
  const di = document.getElementById('dashInput');
  di.addEventListener('keydown', e => {
    if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); dashYubor(); }
  });
  di.addEventListener('input', () => {
    di.style.height = 'auto';
    di.style.height = Math.min(di.scrollHeight, 120) + 'px';
  });
}
if(document.getElementById('dashQidir')){
  document.getElementById('dashQidir').addEventListener('input', () => dashJadvalChiz());
}
dashTezChiz();

if(document.getElementById('dashYopish')) document.getElementById('dashYopish').onclick = dashYop;
if(document.getElementById('dashYangila'))document.getElementById('dashYangila').onclick = dashYangila;
document.addEventListener('keydown', e => {
  if(e.key==='Escape' && document.getElementById('dashOverlay').classList.contains('on')) dashYop();
});

/* ══ CHEK ══════════════════════════════════════════════════════════════════
   Daftarga amal yozilganda suhbatga haqiqiy kassa cheki ko'rinishida chiqadi:
   tishli qirralar, monoshirift, nuqtali ajratgichlar. Ma'lumot to'g'ridan-
   to'g'ri hisob.py qaytargan yozuvdan olinadi — hech narsa o'ylab topilmaydi. */
function chekPul(n, valyuta) {
  const v = Number(n || 0);
  const s = v.toLocaleString('ru-RU', {maximumFractionDigits: 2}).replace(/ /g, ' ');
  return valyuta ? s + ' ' + valyuta : s;
}

function chekSana(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return String(iso).replace('T', ' ').slice(0, 16);
  const p = n => String(n).padStart(2, '0');
  return p(d.getDate()) + '.' + p(d.getMonth() + 1) + '.' + d.getFullYear()
       + '  ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

/* Har amal turining o'z cheki: rangi, sarlavhasi, belgisi va qaysi
   qatorlar chiqishi. Bo'sh maydon chekka umuman tushmaydi. */
const CHEK_TUR = {
  sotuv:           {nom: 'SOTUV',                rang: '#1a7f4b', belgi: '↗',
                    izoh: 'tovar chiqdi'},
  xarid:           {nom: 'XARID',                rang: '#1f5fa8', belgi: '↙',
                    izoh: 'tovar kirdi'},
  qarz_berdim:     {nom: 'QARZ BERDIM',          rang: '#b4530f', belgi: '→',
                    izoh: 'pul chiqdi'},
  qarz_oldim:      {nom: 'QARZ OLDIM',           rang: '#6b3fa0', belgi: '←',
                    izoh: 'pul kirdi'},
  qarz_qaytardim:  {nom: 'QARZIMNI QAYTARDIM',   rang: '#1a7f4b', belgi: '✓',
                    izoh: 'qarzim kamaydi'},
  qarz_qaytarildi: {nom: 'QARZDOR QAYTARDI',     rang: '#1a7f4b', belgi: '✓',
                    izoh: 'qarzdorlik kamaydi'},
  xarajat:         {nom: 'XARAJAT',              rang: '#b3261e', belgi: '−',
                    izoh: 'pul chiqdi'},
  kirim:           {nom: 'BOSHQA KIRIM',         rang: '#1a7f4b', belgi: '+',
                    izoh: 'pul kirdi'},
  boshlangich:     {nom: "BOSHLANG'ICH QOLDIQ",  rang: '#5f6368', belgi: '≡',
                    izoh: 'dastlabki holat'},
  otkazma:         {nom: 'AYIRBOSHLASH',         rang: '#0e7490', belgi: '⇄',
                    izoh: 'kassadan kassaga'},
  ombor_otkazma:   {nom: "OMBORDAN O'TKAZMA",   rang: '#7c5cbf', belgi: '⇉',
                    izoh: 'tovar joyi o\'zgardi'},
};

/* Qaysi turda kim/ta'minotchi qanday ataladi */
const CHEK_KIM = {
  sotuv: 'Xaridor', xarid: "Ta'minotchi",
  qarz_berdim: 'Kimga', qarz_oldim: 'Kimdan',
  qarz_qaytardim: 'Kimga', qarz_qaytarildi: 'Kimdan',
};

/* Turga qarab qaysi qoldiqlar ko'rsatilsin */
const CHEK_QOLDIQ = {
  sotuv:           ['kassa', 'qarzdorlar', 'ombor'],
  xarid:           ['kassa', 'qarzlarim', 'ombor'],
  qarz_berdim:     ['kassa', 'qarzdorlar'],
  qarz_oldim:      ['kassa', 'qarzlarim'],
  qarz_qaytardim:  ['kassa', 'qarzlarim'],
  qarz_qaytarildi: ['kassa', 'qarzdorlar'],
  xarajat:         ['kassa'],
  kirim:           ['kassa'],
  boshlangich:     ['kassa', 'qarzdorlar', 'qarzlarim', 'ombor'],
  ombor_otkazma:   ['ombor'],
};

const QOLDIQ_NOMI = {
  kassa: 'Kassa', qarzdorlar: 'Qarzdorlar',
  qarzlarim: 'Qarzlarim', ombor: 'Ombor',
};
const QOLDIQ_KALIT = {
  kassa: 'kassa', qarzdorlar: 'qarzdorlar_jami',
  qarzlarim: 'qarzlarim_jami', ombor: 'ombor_qiymati',
};

function chekChiz(data) {
  const a = data && data.amal;
  if (!a || !chatArea) return;
  const h = data.holat || {};
  const val = a.valyuta || data.valyuta || '';
  const cfg = CHEK_TUR[a.tur] || {nom: (a.tur || '').toUpperCase(), rang: '#5f6368', belgi: '•'};

  const qator = (chap, ong, kuchli) =>
    '<div class="chek-row' + (kuchli ? ' strong' : '') + '">' +
    '<span>' + esc(chap) + '</span><b>' + esc(ong) + '</b></div>';

  // ── turga mos qatorlar ──
  let ichi = '';
  if (a.kim) ichi += qator(CHEK_KIM[a.tur] || 'Kim', a.kim);
  if (a.tovar) {
    ichi += qator('Tovar', a.tovar);
    if (a.miqdor) ichi += qator('Miqdor', (+a.miqdor) + ' ' + (a.birlik || ''));
    if (a.narx)   ichi += qator('Narx', chekPul(a.narx, val));
  }
  if (a.tur === 'ombor_otkazma') {
    if (a.tovar)  ichi += qator('Tovar', a.tovar
      + (a.miqdor ? ' — ' + (+a.miqdor) + ' ' + (a.birlik||'') : ''));
    if (a.dan_ombor) ichi += qator('Qayerdan', a.dan_ombor);
    if (a.ga_ombor)  ichi += qator('Qayerga', a.ga_ombor);
  }
  if (a.tur === 'otkazma') {
    ichi += qator('Chiqim', chekPul(a.summa, a.valyuta));
    ichi += qator('Kassa', a.kassa_nomi || '');
    ichi += qator('Kirim', chekPul(a.kirim_summa, a.kirim_valyuta));
    ichi += qator('Kassa', a.kirim_kassa || '');
    if (a.summa && a.kirim_summa && a.valyuta !== a.kirim_valyuta)
      ichi += qator('Kurs', (a.kirim_summa / a.summa).toFixed(4));
  }
  if (a.tur === 'boshlangich') {
    if (a.kassa)   ichi += qator('Kassada', chekPul(a.kassa, val));
    if (a.qarzdor) ichi += qator('Menga qarzdor', chekPul(a.qarzdor, val));
    if (a.qarzim)  ichi += qator('Mening qarzim', chekPul(a.qarzim, val));
  }
  if (a.izoh) ichi += qator('Izoh', a.izoh);
  if (a.tur !== 'otkazma' && a.kassa_nomi && a.kassa_nomi !== 'Asosiy')
    ichi += qator('Kassa', a.kassa_nomi);

  // ── to'lov nishoni (faqat pul harakat qiladigan turlarda) ──
  let payHtml = '';
  if (a.tur === 'sotuv' || a.tur === 'xarid') {
    const nasiya = (a.tolov || '').toLowerCase() === 'qarz';
    payHtml = '<div class="chek-pay"><span class="chek-badge ' +
      (nasiya ? 'qarz' : 'naqd') + '">' + (nasiya ? 'NASIYA' : 'NAQD') + '</span></div>';
  }

  // ── turga mos yangi qoldiqlar ──
  let holatlar = '';
  if (a.tur === 'otkazma' && data.kassalar) {
    // ikkala qatnashgan kassaning yangi qoldig'i
    data.kassalar.filter(k => k.nom === a.kassa_nomi || k.nom === a.kirim_kassa)
      .forEach(k => { holatlar += qator(k.nom, chekPul(k.qoldiq, k.valyuta)); });
  } else {
    (CHEK_QOLDIQ[a.tur] || ['kassa']).forEach(k => {
      const v = h[QOLDIQ_KALIT[k]];
      if (v !== undefined) holatlar += qator(QOLDIQ_NOMI[k], chekPul(v, val));
    });
  }

  const el = document.createElement('div');
  el.className = 'chek-wrap';
  el.innerHTML =
    '<div class="chek" style="--chek-rang:' + cfg.rang + '">' +
      '<div class="chek-top"></div>' +
      '<div class="chek-body">' +
        '<div class="chek-brand">MUHASIB</div>' +
        '<div class="chek-kind"><span class="chek-glyph">' + esc(cfg.belgi) + '</span>' +
          esc(cfg.nom) + '</div>' +
        (cfg.izoh ? '<div class="chek-tag">' + esc(cfg.izoh) + '</div>' : '') +
        '<div class="chek-meta">' + esc(chekSana(a.sana)) +
          '<br>№ ' + esc(String(a.id || '').slice(0, 10).toUpperCase()) + '</div>' +
        '<div class="chek-cut"></div>' +
        (ichi || qator('Amal', cfg.nom)) +
        '<div class="chek-cut"></div>' +
        (a.tur === 'otkazma'
          ? qator('OLINDI', chekPul(a.kirim_summa, a.kirim_valyuta), true)
          : (a.summa ? qator('SUMMA', chekPul(a.summa, val), true) : '')) +
        payHtml +
        (holatlar ? '<div class="chek-cut"></div>' +
                    '<div class="chek-after">YANGI QOLDIQ</div>' + holatlar : '') +
        '<div class="chek-foot">daftarga yozildi ✓</div>' +
      '</div>' +
      '<div class="chek-bot"></div>' +
    '</div>';

  chatArea.appendChild(el);
  chatArea.scrollTop = chatArea.scrollHeight;
}

/* ══ ChatGPT ovozi + MUHASIB daftari ═══════════════════════════════════════
   8779 dagi ko'prik ChatGPT'ning haqiqiy Advanced Voice rejimini boshqaradi —
   u tez va tabiiy, lekin lokal vositalarni chaqira olmaydi. Shuning uchun
   suhbat boshlanishidan OLDIN daftardagi hozirgi holatni matn sifatida
   suhbatga yuboramiz: shundan keyin u raqamlarni biladi va ular haqida
   gaplasha oladi. Yozish (amal_yozish) baribir MUHASIB tomonida qoladi. */
const CGPT_BRIDGE = 'http://127.0.0.1:8779';
let cgptEvtAbort = null;

function son(n) {
  return Number(n || 0).toLocaleString('ru-RU').replace(/ /g, ' ');
}

function daftarKonteksti(h) {
  const L = [];
  L.push('[MUHASIB — mening hisob daftarim, hozirgi holat]');
  L.push('Valyuta: ' + ((h.biznes && h.biznes.valyuta) || '—'));
  L.push('Kassa: ' + son(h.kassa));
  const omb = h.ombor || {};
  L.push('Ombor: ' + (omb.tur_soni || 0) + ' xil tovar, jami qiymati ' + son(omb.jami_qiymat));
  (omb.tovarlar || []).slice(0, 12).forEach(t =>
    L.push('   · ' + t.nom + ' — ' + son(t.miqdor) + ' ' + t.birlik + ', tan narx ' + son(t.tan_narx)));
  const qd = h.qarzdorlar || {};
  L.push('Menga qarzdorlar: jami ' + son(qd.jami));
  (qd.odamlar || []).slice(0, 15).forEach(o => L.push('   · ' + o.kim + ' — ' + son(o.summa)));
  const qm = h.qarzlarim || {};
  L.push('Mening qarzlarim: jami ' + son(qm.jami));
  (qm.odamlar || []).slice(0, 15).forEach(o => L.push('   · ' + o.kim + ' — ' + son(o.summa)));
  const f = h.foyda || {};
  L.push('Foyda: sof ' + son(f.sof) + ' (savdo ' + son(f.savdo) + ', xarajat ' + son(f.xarajat) + ')');
  L.push('Jami amallar: ' + (h.amallar_soni || 0));
  L.push('');
  L.push('Shu ma\'lumot asosida men bilan O\'ZBEK TILIDA, qisqa gaplar bilan gaplash.');
  L.push('Raqamlarni o\'ylab topma — faqat yuqoridagi ro\'yxatdan foydalan.');
  L.push('Agar men yangi amal aytsam, tushunganingni bir gapda tasdiqla.');
  L.push('Javob berish shart emas — shunchaki o\'qib ol, men hozir gapira boshlayman.');
  return L.join('\n');
}

/* Qisqa signal ovozi — ekranga qaramasdan ham mikrofon yoqilganini bilish uchun. */
function cgptBeep(pattern) {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = new AC();
    let t = ctx.currentTime + 0.01;
    pattern.forEach(([freq, dur]) => {
      const osc = ctx.createOscillator(), g = ctx.createGain();
      osc.type = 'sine'; osc.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.16, t + 0.015);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      osc.connect(g); g.connect(ctx.destination);
      osc.start(t); osc.stop(t + dur + 0.02);
      t += dur + 0.03;
    });
    setTimeout(() => { try { ctx.close(); } catch (e) {} }, 1200);
  } catch (e) { /* audio bo'lmasa ham ish to'xtamasin */ }
}

let cgptStepTimer = null, cgptStepT0 = 0;

function cgptStep(n) {
  const box = document.getElementById('cgptSteps');
  if (!box) return;
  box.classList.add('on');
  document.getElementById('cgptReady').classList.remove('on');
  box.querySelectorAll('.cgpt-step').forEach(el => {
    const i = Number(el.dataset.step);
    el.className = 'cgpt-step' + (i < n ? ' done' : i === n ? ' now' : '');
    const b = el.querySelector('b');
    if (i < n) {
      // bajarildi: qancha vaqt olganini saqlab, yoniga belgi qo'yamiz
      b.textContent = /^\d+s$/.test(b.textContent) ? '✓ ' + b.textContent : '✓';
    } else if (i > n) {
      b.textContent = '';
    }
  });
  // joriy bosqichda soniya sanab turadi — qotib qolgandek tuyulmasin
  clearInterval(cgptStepTimer);
  cgptStepT0 = Date.now();
  const cur = box.querySelector('.cgpt-step.now b');
  if (cur) {
    cur.textContent = '0s';
    cgptStepTimer = setInterval(() => {
      cur.textContent = Math.round((Date.now() - cgptStepT0) / 1000) + 's';
    }, 500);
  }
}

function cgptReady(on) {
  clearInterval(cgptStepTimer);
  const st = document.getElementById('cgptSteps');
  const rd = document.getElementById('cgptReady');
  const dot = document.getElementById('cgptDot');
  if (st) st.classList.toggle('on', !on);
  if (rd) rd.classList.toggle('on', on);
  if (dot) dot.className = 'cgpt-dot' + (on ? ' live' : '');
  if (on) cgptBeep([[660, 0.10], [990, 0.13]]);   // ko'tarilgan ikki nota = "gapiring"
}

/* Xatoni panelda ko'rsatadi. Login kerak bo'lsa — ChatGPT login oynasini
   ochadigan tugma qo'shadi (Chrome oynasi oldinga chiqadi, siz kirasiz). */
function cgptFail(message, loginKerak) {
  clearInterval(cgptStepTimer);
  const st = document.getElementById('cgptState');
  const steps = document.getElementById('cgptSteps');
  const fix = document.getElementById('cgptFix');
  const fixText = document.getElementById('cgptFixText');
  const fixBtn = document.getElementById('cgptFixBtn');
  if (st) st.textContent = 'To‘xtadi';
  // qaysi bosqichda to'xtaganini qoldiramiz — aylanish o'rniga qizil belgi
  if (steps) {
    const now = steps.querySelector('.cgpt-step.now');
    if (now) { now.className = 'cgpt-step fail'; now.querySelector('b').textContent = '✕'; }
  }
  cgptReady(false);
  if (steps) steps.classList.add('on');
  cgptBeep([[420, 0.16], [300, 0.20]]);

  if (!fix) return;
  fix.classList.add('on');
  fixText.textContent = '⚠️ ' + message;
  if (!loginKerak) { fixBtn.style.display = 'none'; return; }

  fixBtn.style.display = '';
  fixBtn.disabled = false;
  fixBtn.textContent = 'ChatGPT login oynasini ochish';
  fixBtn.onclick = async () => {
    fixBtn.disabled = true;
    fixBtn.textContent = 'Ochilmoqda…';
    try {
      const r = await (await fetch(CGPT_BRIDGE + '/api/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).json();
      if (r.error) {
        fixText.textContent = '⚠️ ' + r.error;
        fixBtn.textContent = 'Qayta urinish';
      } else {
        fixText.textContent = 'Chrome oynasi ochildi — o‘sha yerda ChatGPT‘ga kiring, '
                            + 'keyin «ChatGPT ovozi» tugmasini qayta bosing.';
        fixBtn.textContent = 'Ochildi ✓';
      }
    } catch (e) {
      fixText.textContent = '⚠️ 8779 ko‘prigiga ulanib bo‘lmadi.';
      fixBtn.textContent = 'Qayta urinish';
    }
    fixBtn.disabled = false;
  };
}

async function startChatGptVoice() {
  const btn = document.getElementById('cgptVoiceBtn');
  const st = document.getElementById('cgptState');
  const panel = document.getElementById('cgptPanel');
  if (btn) btn.disabled = true;
  if (panel) panel.classList.add('on');
  const fixBox = document.getElementById('cgptFix');
  if (fixBox) fixBox.classList.remove('on');
  const say = t => { if (st) st.textContent = t; };
  say('Ishga tushmoqda…');

  try {
    cgptStep(0);                                   // daftar
    const hres = await (await fetch('/api/hisob')).json();
    const ctx = daftarKonteksti(hres.hisob || {});

    cgptStep(1);                                   // ChatGPT'ga uzatish
    const r = await fetch(CGPT_BRIDGE + '/api/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: ctx }),
    });
    const reader = r.body.getReader();
    while (true) { const { done } = await reader.read(); if (done) break; }

    cgptStep(2);                                   // ovozli rejim
    const d = await (await fetch(CGPT_BRIDGE + '/api/voice/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    })).json();
    if (d.error) {
      cgptFail(d.error, d.needsLogin || d.needsBrowser);
      if (btn) btn.disabled = false;
      return;
    }

    cgptStep(3);                                   // mikrofon haqiqatan yoqilishini kutamiz
    const kutish = Date.now() + 20000;
    let tayyor = d.micOn === true;
    while (!tayyor && Date.now() < kutish) {
      await new Promise(res => setTimeout(res, 400));
      try {
        const stt = await (await fetch(CGPT_BRIDGE + '/api/state')).json();
        tayyor = stt.voiceActive === true && stt.micOn === true;
      } catch (e) { /* qayta urinamiz */ }
    }

    if (!tayyor) {
      cgptFail('Mikrofon yoqilmadi — qayta urinib ko‘ring.', false);
      if (btn) btn.disabled = false;
      return;
    }

    cgptReady(true);
    say('Eshitilmoqda');
    streamChatGptVoice();
  } catch (error) {
    cgptFail('8779 ko‘prigi javob bermadi. chgpt papkasida chatgpt_server.py ishlayaptimi?', false);
    if (btn) btn.disabled = false;
  }
}

/* Panelga suhbatni chizadi: mavjud puffaklarni yangilaydi, faqat yangisini
   qo'shadi — shuning uchun matn yozilib borganda oyna titramaydi. */
let cgptNodes = [];
function cgptRender(msgs) {
  const box = document.getElementById('cgptLog');
  if (!box) return;
  box.classList.add('on');
  while (cgptNodes.length > msgs.length) cgptNodes.pop().remove();
  msgs.forEach((m, i) => {
    const isUser = m.role === 'user';
    let el = cgptNodes[i];
    if (!el) {
      el = document.createElement('div');
      el.innerHTML = '<span class="who"></span><span class="txt"></span>';
      box.appendChild(el);
      cgptNodes[i] = el;
    }
    const cls = 'cgpt-msg ' + (isUser ? 'u' : 'a');
    if (el.className !== cls) el.className = cls;
    const who = isUser ? 'Siz' : 'ChatGPT';
    if (el.firstChild.textContent !== who) el.firstChild.textContent = who;
    const txt = el.lastChild;
    if (txt.textContent !== m.text) txt.textContent = m.text;
  });
  // pastda turgan bo'lsak, avtomatik pastga suramiz
  const yaqin = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
  if (yaqin) box.scrollTop = box.scrollHeight;
}

async function streamChatGptVoice() {
  const st = document.getElementById('cgptState');
  const dot = document.getElementById('cgptDot');
  const typing = document.getElementById('cgptTyping');
  cgptNodes = [];
  const log = document.getElementById('cgptLog');
  if (log) log.innerHTML = '';

  if (cgptEvtAbort) cgptEvtAbort.abort();
  cgptEvtAbort = new AbortController();
  try {
    const res = await fetch(CGPT_BRIDGE + '/api/voice/events', { signal: cgptEvtAbort.signal });
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const raw = buf.slice(0, i); buf = buf.slice(i + 2);
        if (!raw.startsWith('data:')) continue;
        const ev = JSON.parse(raw.slice(5).trim());

        if (ev.msgs && ev.msgs.length) cgptRender(ev.msgs);
        if (typing) typing.classList.toggle('on', Boolean(ev.speaking && ev.active));
        if (st) st.textContent = ev.speaking ? 'ChatGPT gapiryapti'
                : !ev.active ? 'Tugadi'
                : ev.micOn === false ? 'Mikrofon o‘chiq' : 'Eshitilmoqda';
        if (dot) dot.className = 'cgpt-dot' + (ev.active ? ' live' : '');

        if (!ev.active) {
          cgptReady(false);
          if (typing) typing.classList.remove('on');
          const b = document.getElementById('cgptVoiceBtn'); if (b) b.disabled = false;
        }
      }
    }
  } catch (e) { /* to'xtatildi */ }
  if (typing) typing.classList.remove('on');
  const b = document.getElementById('cgptVoiceBtn');
  if (b) b.disabled = false;
}

if (document.getElementById('cgptVoiceBtn')) {
  document.getElementById('cgptVoiceBtn').onclick = startChatGptVoice;
}
if (document.getElementById('cgptCloseBtn')) {
  document.getElementById('cgptCloseBtn').onclick = async () => {
    if (cgptEvtAbort) { cgptEvtAbort.abort(); cgptEvtAbort = null; }
    try {
      await fetch(CGPT_BRIDGE + '/api/voice/end', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    } catch (e) {}
    cgptReady(false);
    const lg = document.getElementById('cgptLog');
    if (lg) { lg.innerHTML = ''; lg.classList.remove('on'); }
    cgptNodes = [];
    const tp = document.getElementById('cgptTyping'); if (tp) tp.classList.remove('on');
    const pn = document.getElementById('cgptPanel'); if (pn) pn.classList.remove('on');
    const b = document.getElementById('cgptVoiceBtn'); if (b) b.disabled = false;
  };
}

/* 🎙 tugmasi endi DIKTOVKA qiladi — ovozli rejim olib tashlangani uchun
   uni hech kim o'ziga olib qo'ymaydi. Gapirasiz -> o'zbekcha matn
   yozuv maydoniga tushadi va yuboriladi. */
if (document.getElementById('voiceInputBtn')) {
  document.getElementById('voiceInputBtn').onclick = event => {
    event.preventDefault();
    event.stopPropagation();
    toggleVoiceCapture();
  };
}
if ($('#voicePreviewBtn')) {
  $('#voicePreviewBtn').onclick = previewVoice;
}
if ($('#voiceAutoSpeak')) {
  $('#voiceAutoSpeak').onchange = event => {
    VOICE_STATE.autoSpeak = Boolean(event.target.checked);
    localStorage.setItem('agv_voice_auto', VOICE_STATE.autoSpeak ? '1' : '0');
  };
}
async function loadWorkspaceFileTree() {
  const treeContainer = $('#fileTreeList');
  if (!treeContainer) return;
  const folderPath = $('#folder') ? $('#folder').value : '';
  try {
    const res = await fetch('/api/tree?path=' + encodeURIComponent(folderPath));
    const data = await res.json();
    renderFileTree(data.tree || [], treeContainer);
  } catch(e) {
    treeContainer.innerHTML = '<div style="padding:16px;color:#ea4335">Fayllarni yuklashda xato</div>';
  }
}

function getFileIcon(name, isDir) {
  if (isDir) return '📁';
  const ext = name.split('.').pop().toLowerCase();
  if (['py', 'js', 'html', 'css', 'json', 'sh', 'md'].includes(ext)) return '📄';
  if (['mp4', 'mov', 'webm', 'm4v'].includes(ext)) return '🎬';
  if (['mp3', 'm4a', 'wav', 'aiff'].includes(ext)) return '🎵';
  if (['jpg', 'png', 'gif', 'svg', 'webp'].includes(ext)) return '🖼️';
  if (['xlsx', 'xls', 'csv'].includes(ext)) return '📊';
  return '📃';
}

function renderFileTree(nodes, container, depth = 0) {
  if (!nodes || !nodes.length) {
    container.innerHTML = '<div style="padding:16px;color:var(--muted);font-size:12.5px">(fayllar yo\'q)</div>';
    return;
  }
  container.innerHTML = nodes.map(node => `
    <div class="tree-item ${node.isDir ? 'is-dir' : 'is-file'}" style="padding:6px 10px;padding-left:${10 + depth * 14}px;cursor:pointer;border-radius:8px;font-size:13px;display:flex;align-items:center;gap:6px;margin:2px 0" onclick="onFileItemClick('${esc(node.path).replace(/'/g,"\\'")}', ${node.isDir})">
      <span style="font-size:14px">${getFileIcon(node.name, node.isDir)}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(node.name)}</span>
      ${node.size ? `<span style="font-size:10px;color:var(--muted)">${formatBytes(node.size)}</span>` : ''}
    </div>
    ${node.children && node.children.length ? `<div class="tree-sub">${node.children.map(c => renderFileNode(c, depth + 1)).join('')}</div>` : ''}
  `).join('');
}

function renderFileNode(node, depth) {
  return `
    <div class="tree-item ${node.isDir ? 'is-dir' : 'is-file'}" style="padding:6px 10px;padding-left:${10 + depth * 14}px;cursor:pointer;border-radius:8px;font-size:13px;display:flex;align-items:center;gap:6px;margin:2px 0" onclick="onFileItemClick('${esc(node.path).replace(/'/g,"\\'")}', ${node.isDir})">
      <span style="font-size:14px">${getFileIcon(node.name, node.isDir)}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(node.name)}</span>
      ${node.size ? `<span style="font-size:10px;color:var(--muted)">${formatBytes(node.size)}</span>` : ''}
    </div>
  `;
}

function formatBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

async function onFileItemClick(path, isDir) {
  if (isDir) return;
  const ext = path.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) {
    openLightbox('/api/file?path=' + encodeURIComponent(path));
    return;
  }
  try {
    const r = await fetch('/api/file/read?path=' + encodeURIComponent(path));
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    $('#cvFileName').textContent = d.name;
    $('#cvFilePath').textContent = d.path;
    $('#cvCodeText').textContent = d.content;
    $('#codeViewerModal').classList.remove('hidden');
  } catch(e) {
    alert('Faylni ochishda xato: ' + e.message);
  }
}

if($('#cvClose')) $('#cvClose').onclick = () => $('#codeViewerModal').classList.add('hidden');
if($('#cvCopyBtn')) $('#cvCopyBtn').onclick = () => {
  const code = $('#cvCodeText').textContent;
  navigator.clipboard.writeText(code).then(() => {
    const old = $('#cvCopyBtn').textContent;
    $('#cvCopyBtn').textContent = '✓ Nusxalandi!';
    setTimeout(() => $('#cvCopyBtn').textContent = old, 2000);
  });
};

function openLightbox(src) {
  $('#lightboxImg').src = src;
  $('#lightboxModal').classList.remove('hidden');
}
function closeLightbox() {
  $('#lightboxModal').classList.add('hidden');
}

/* --- COMMAND PALETTE LOGIC --- */
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    toggleCmdPalette(true);
  }
});

const cmdPaletteBtn = $('#cmdPaletteBtn');
if (cmdPaletteBtn) cmdPaletteBtn.onclick = () => toggleCmdPalette(true);

function toggleCmdPalette(show) {
  const modal = $('#cmdPaletteModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
    $('#cmdInput').value = '';
    $('#cmdInput').focus();
    renderCmdList();
  } else {
    modal.classList.add('hidden');
  }
}

const COMMANDS = [
  { icon: '✨', title: 'Yangi suhbat boshlash', action: () => { createNewSession(); toggleCmdPalette(false); } },
  { icon: '📁', title: 'Fayllar Explorer-ni ochish', action: () => { toggleSidebar(true); document.querySelector('.sb-tab[data-tab="files"]').click(); toggleCmdPalette(false); } },
  { icon: '🎬', title: 'Multik / Reklama video tayyorlash', action: () => { useQuickPrompt('🎬 Avvalgi MP4 fayllarni ko‘rsatma: Uzbek Neural ovozi bilan yangi, alohida nomli video reklama rolik tayyorla'); toggleCmdPalette(false); } },
  { icon: '🔓', title: 'Full Access rejimini sozlash', action: () => { $('#faModal').classList.remove('hidden'); toggleCmdPalette(false); } },
  { icon: '🌌', title: 'Zero-G Physics rejimi', action: () => { $('#zeroGBtn').click(); toggleCmdPalette(false); } },
  { icon: '🌙', title: 'Dark / Light mavzuni almashtirish', action: () => { $('#theme').click(); toggleCmdPalette(false); } },
];

function renderCmdList(filter = '') {
  const container = $('#cmdList');
  if (!container) return;
  const q = filter.toLowerCase().trim();
  const filtered = COMMANDS.filter(c => c.title.toLowerCase().includes(q));
  if (!filtered.length) {
    container.innerHTML = '<div style="padding:14px;color:var(--muted);text-align:center;font-size:13px">Buyruq topilmadi</div>';
    return;
  }
  container.innerHTML = filtered.map((c, i) => `
    <div class="cmd-item" style="padding:10px 14px;border-radius:12px;cursor:pointer;display:flex;align-items:center;gap:12px;font-size:13.5px;color:var(--text);background:var(--panel-solid);border:1px solid var(--border)" onclick="COMMANDS[${COMMANDS.indexOf(c)}].action()">
      <span style="font-size:18px">${c.icon}</span>
      <span style="flex:1;font-weight:500">${esc(c.title)}</span>
      <span style="font-size:11px;color:var(--muted);background:var(--field);padding:2px 8px;border-radius:6px">Bajarish</span>
    </div>
  `).join('');
}

if ($('#cmdInput')) {
  $('#cmdInput').oninput = (e) => renderCmdList(e.target.value);
}

// ChatGPT Voice Mode Controller
(function() {
  const overlay = document.getElementById('chatgptVoiceOverlay');
  const orbCanvas = document.getElementById('cgvOrbCanvas');
  const orbGlow = document.getElementById('cgvOrbGlow');
  const statusText = document.getElementById('cgvStatusText');
  const transcriptText = document.getElementById('cgvTranscript');
  const micBtn = document.getElementById('cgvMicBtn');
  const endBtn = document.getElementById('cgvEndBtn');
  const closeBtn = document.getElementById('voiceOverlayClose');
  const voiceInputBtn = document.getElementById('voiceInputBtn');
  const floatBtn = document.getElementById('cgvFloatingLauncher');

  if (!overlay || !orbCanvas) return;
  window.isLiveVoiceModeActive = () => overlay.classList.contains('active');

  const ctx = orbCanvas.getContext('2d');
  let animationId = null;
  let voiceState = 'idle'; // 'idle', 'listening', 'thinking', 'speaking'
  let audioLevel = 0;
  let orbLevel = 0;   // silliqlangan ovoz darajasi (sfera uchun)
  let recognition = null;
  let mediaRecorder = null;
  let mediaStream = null;
  let audioContext = null;
  let analyser = null;
  let currentAudio = null;
  let isMuted = false;
  let realtime = null;
  let realtimeOpening = false;
  let realtimeGeneration = 0;
  let fallbackVoiceMeter = null;
  let spokenTurnInFlight = false;
  let listeningRun = 0;

  function cleanTextForSpeech(text) {
    if (!text) return "";
    let clean = text
      .replace(/```[\s\S]*?```/g, " kod bloki ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/!?\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/<[^>]+>/g, "")
      .replace(/[#*_\~|\$\\]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return clean;
  }

  function readAudioMeter(meter) {
    if (!meter) return 0;
    try {
      const values = new Uint8Array(meter.fftSize);
      meter.getByteTimeDomainData(values);
      let total = 0;
      for (const value of values) total += Math.abs(value - 128);
      return Math.min(1, (total / values.length) / 26);
    } catch (error) {
      return 0;
    }
  }

  function currentVoiceLevel() {
    const meter = realtime && voiceState === 'speaking'
      ? realtime.remoteMeter
      : realtime && voiceState === 'listening'
        ? realtime.micMeter
        : fallbackVoiceMeter && voiceState === 'listening'
          ? fallbackVoiceMeter.micMeter
          : null;
    return Math.max(audioLevel * 0.55, readAudioMeter(meter));
  }

  function attachAudioMeter(stream, active, name) {
    if (!stream || !active || !window.AudioContext) return;
    try {
      if (!audioContext) audioContext = new AudioContext();
      if (audioContext.state === 'suspended') audioContext.resume().catch(() => {});
      const source = audioContext.createMediaStreamSource(stream);
      const meter = audioContext.createAnalyser();
      meter.fftSize = 64;
      source.connect(meter);
      active[`${name}Source`] = source;
      active[`${name}Meter`] = meter;
    } catch (error) {
      console.warn('Live Voice audio meter ulanmagan:', error);
    }
  }

  function detachAudioMeters(active) {
    if (!active) return;
    for (const name of ['micSource', 'remoteSource']) {
      try { if (active[name]) active[name].disconnect(); } catch (error) {}
    }
  }

  async function startFallbackSpeechMeter() {
    if (realtime || fallbackVoiceMeter || !navigator.mediaDevices) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      if (realtime || !overlay.classList.contains('active')) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      fallbackVoiceMeter = { stream };
      attachAudioMeter(stream, fallbackVoiceMeter, 'mic');
    } catch (error) {
      console.warn('Fallback Voice audio meter ulanmagan:', error);
    }
  }

  function stopFallbackSpeechMeter() {
    if (!fallbackVoiceMeter) return;
    detachAudioMeters(fallbackVoiceMeter);
    try { fallbackVoiceMeter.stream.getTracks().forEach(track => track.stop()); } catch (error) {}
    fallbackVoiceMeter = null;
  }

  function realtimeTranscript(event) {
    const direct = String(event.transcript || event.text || '').trim();
    if (direct) return direct;
    const output = event.response && Array.isArray(event.response.output) ? event.response.output : [];
    return output.flatMap(item => Array.isArray(item.content) ? item.content : [])
      .map(part => String(part.transcript || part.text || '').trim())
      .filter(Boolean)
      .join(' ')
      .trim();
  }

  function publishRealtimeTurn(role, text) {
    const clean = cleanTextForSpeech(text);
    if (!clean) return;
    addMsg(role, clean);
    if (role !== 'user') convo = true;
  }

  function finishRealtimeResponse() {
    if (!realtime || realtime.responseInterrupted || realtime.responsePosted) return;
    const text = cleanTextForSpeech(realtime.responseText || '');
    if (!text) return;
    realtime.responsePosted = true;
    publishRealtimeTurn('model', text);
  }

  /* Ovoz rejimidagi vosita chaqirig'i: serverga yuboramiz, natijani modelga
     qaytaramiz va u ovozda tasdiqlaydi. Panel ham darhol yangilanadi. */
  async function handleVoiceToolCall(event) {
    const current = realtime;
    if (!current || !current.channel) return;
    const nomi = String(event.name || '');
    if (statusText) statusText.textContent = 'Daftarga yozilmoqda…';
    let output = '{"xato":"bajarilmadi"}';
    try {
      const r = await fetch('/api/voice/tool', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nomi, arguments: event.arguments || '{}' }),
      });
      const d = await r.json();
      output = String(d.output || output);
    } catch (e) {
      output = JSON.stringify({ xato: String(e && e.message || e) });
    }
    if (realtime !== current || current.channel.readyState !== 'open') return;
    try {
      current.channel.send(JSON.stringify({
        type: 'conversation.item.create',
        item: { type: 'function_call_output', call_id: event.call_id, output: output },
      }));
      current.channel.send(JSON.stringify({ type: 'response.create' }));
    } catch (e) {}
    if (typeof loadHisob === 'function') loadHisob();   // panel darhol yangilansin
  }

  function handleRealtimeEvent(event) {
    if (!realtime || !event || !event.type) return;
    if (event.type === 'input_audio_buffer.speech_started') {
      realtime.responseInterrupted = true;
      realtime.responseText = '';
      spokenTurnInFlight = false;
      try {
        if (realtime.channel && realtime.channel.readyState === 'open') {
          realtime.channel.send(JSON.stringify({ type: 'response.cancel' }));
        }
      } catch (error) {}
      try { if (typeof stopVoicePlayback === 'function') stopVoicePlayback(); } catch (error) {}
      stopAudio();
      voiceState = 'listening';
      if (realtime) realtime.partialUserText = '';
      if (statusText) statusText.textContent = 'Eshitilmoqda — avvalgi javob to‘xtatildi';
      if (transcriptText) transcriptText.textContent = 'Yangi gapni eshitayapman…';
      return;
    }
    if (event.type === 'input_audio_buffer.speech_stopped') {
      voiceState = 'thinking';
      if (statusText) statusText.textContent = 'Tushundim, darhol javob tayyorlanmoqda…';
      return;
    }
    /* ══ Gapirayotganda matn jonli chiqadi ══
       Realtime API bo'lak-bo'lak (.delta) transkript yuboradi; ilgari faqat
       .completed ushlanardi, shuning uchun gap tugamaguncha hech narsa
       ko'rinmasdi. Endi so'zlar aytilgan sayin yozilib boradi. */
    if (event.type === 'conversation.item.input_audio_transcription.delta') {
      realtime.partialUserText = (realtime.partialUserText || '') + String(event.delta || '');
      voiceState = 'listening';
      if (statusText) statusText.textContent = 'Eshitilmoqda…';
      if (transcriptText) transcriptText.textContent = realtime.partialUserText.slice(-260);
      return;
    }
    if (event.type === 'conversation.item.input_audio_transcription.completed') {
      const text = realtimeTranscript(event) || (realtime.partialUserText || '').trim();
      realtime.partialUserText = '';
      if (text && text !== realtime.lastUserText) {
        realtime.lastUserText = text;
        publishRealtimeTurn('user', text);
      }
      return;
    }
    /* ══ Ovoz vosita chaqirdi — daftarga yozish yoki hisobot olish ══
       ChatGPT Voice'dagi "delegate work" shu: gapirasiz, u haqiqatan bajaradi. */
    if (event.type === 'response.function_call_arguments.done') {
      handleVoiceToolCall(event);
      return;
    }
    if (event.type === 'response.created') {
      realtime.responseInterrupted = false;
      realtime.responsePosted = false;
      realtime.responseText = '';
      voiceState = 'thinking';
      if (statusText) statusText.textContent = 'Live Voice javob bermoqda…';
      return;
    }
    if (event.type === 'response.output_audio_transcript.delta') {
      realtime.responseText += String(event.delta || '');
      voiceState = 'speaking';
      if (statusText) statusText.textContent = 'Live Voice gapirmoqda…';
      if (transcriptText) transcriptText.textContent = realtime.responseText.slice(-220);
      return;
    }
    if (event.type === 'response.output_audio_transcript.done') {
      realtime.responseText = realtimeTranscript(event) || realtime.responseText;
      finishRealtimeResponse();
      return;
    }
    if (event.type === 'response.done') {
      realtime.responseText = realtimeTranscript(event) || realtime.responseText;
      finishRealtimeResponse();
      if (!realtime.responseInterrupted) {
        voiceState = 'listening';
        if (statusText) statusText.textContent = 'Eshitilmoqda…';
      }
      return;
    }
    if (event.type === 'error') {
      console.warn('Realtime Voice event error:', event.error || event);
      if (statusText) statusText.textContent = 'Live Voice xatosi yuz berdi';
    }
  }

  function waitForIceGathering(connection) {
    return new Promise(resolve => {
      if (connection.iceGatheringState === 'complete') return resolve();
      let timeout = null;
      const finish = () => {
        if (timeout) clearTimeout(timeout);
        connection.removeEventListener('icegatheringstatechange', complete);
        resolve();
      };
      const complete = () => {
        if (connection.iceGatheringState === 'complete') finish();
      };
      connection.addEventListener('icegatheringstatechange', complete);
      timeout = setTimeout(finish, 1800);
    });
  }

  function stopRealtimeVoice() {
    realtimeGeneration++;
    const active = realtime;
    realtime = null;
    if (!active) return;
    try { if (active.channel) active.channel.close(); } catch(e) {}
    try { if (active.connection) active.connection.close(); } catch(e) {}
    try { active.stream.getTracks().forEach(track => track.stop()); } catch(e) {}
    try { active.audio.pause(); active.audio.srcObject = null; active.audio.remove(); } catch(e) {}
    detachAudioMeters(active);
  }

  async function startRealtimeVoice() {
    if (realtime) return true;
    if (realtimeOpening || isMuted || !navigator.mediaDevices || !window.RTCPeerConnection) return false;
    realtimeOpening = true;
    const generation = ++realtimeGeneration;
    let active = null;
    try {
      if (statusText) statusText.textContent = 'Live Voice ulanmoqda…';
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const connection = new RTCPeerConnection();
      const audio = document.createElement('audio');
      audio.autoplay = true;
      audio.playsInline = true;
      audio.style.display = 'none';
      document.body.appendChild(audio);
      active = { connection, stream, audio, channel: null, responseText: '', responseInterrupted: false, responsePosted: false, lastUserText: '' };
      attachAudioMeter(stream, active, 'mic');
      connection.ontrack = event => {
        if (!realtime || realtime !== active) return;
        audio.srcObject = event.streams[0];
        attachAudioMeter(event.streams[0], active, 'remote');
        audio.play().catch(() => {});
      };
      connection.onconnectionstatechange = () => {
        if (!realtime || realtime !== active || connection.connectionState !== 'failed') return;
        if (statusText) statusText.textContent = 'Live Voice uzildi — odatiy Voice ishlaydi';
      };
      const channel = connection.createDataChannel('oai-events');
      active.channel = channel;
      channel.onmessage = message => {
        try { handleRealtimeEvent(JSON.parse(message.data)); } catch(e) {}
      };
      stream.getAudioTracks().forEach(track => connection.addTrack(track, stream));
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);
      await waitForIceGathering(connection);
      const response = await fetch('/api/voice/realtime/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: connection.localDescription.sdp,
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.error || 'Realtime sessiya yaratilolmadi.');
      }
      const answer = await response.text();
      if (!answer) throw new Error('Realtime SDP javobi bo‘sh.');
      if (!overlay.classList.contains('active') || generation !== realtimeGeneration) {
        try { connection.close(); } catch(e) {}
        stream.getTracks().forEach(track => track.stop());
        audio.remove();
        return false;
      }
      realtime = active;
      await connection.setRemoteDescription({ type: 'answer', sdp: answer });
      voiceState = 'listening';
      if (statusText) statusText.textContent = 'Live Voice eshitmoqda…';
      if (transcriptText) transcriptText.textContent = 'Gapiring — sukutdan keyin darhol javob beradi.';
      if (micBtn) micBtn.classList.add('active');
      return true;
    } catch (error) {
      console.warn('Realtime Voice ulanmagan, odatiy ovozga qaytilmoqda:', error);
      if (active) {
        try { if (active.channel) active.channel.close(); } catch(e) {}
        try { active.connection.close(); } catch(e) {}
        try { active.stream.getTracks().forEach(track => track.stop()); } catch(e) {}
        try { active.audio.remove(); } catch(e) {}
        detachAudioMeters(active);
      }
      return false;
    } finally {
      realtimeOpening = false;
    }
  }

  /* ══ Voice Orb ══════════════════════════════════════════════════════════
     Ko'k-oq sfera: yuqori-o'ngda to'q ko'k, pastki-chapda oqqa o'tadi.
     Ichida to'rtta yumshoq "tutun" qatlami sekin suzadi. Ovoz balandligi
     ularning tezligini, quyuqligini va rangini o'zgartiradi — gapirganda
     binafshaga og'adi, tinglaganda ko'kroq turadi. Daraja silliqlanadi
     (orbLevel), shuning uchun sfera sakramaydi, nafas olgandek harakatlanadi. */
  function drawOrb(timestamp = 0) {
    const W = orbCanvas.width, H = orbCanvas.height;
    const cx = W / 2, cy = H / 2;
    const R = Math.min(W, H) / 2 - 14;
    const t = timestamp / 1000;
    const active = voiceState === 'listening' || voiceState === 'speaking';
    const speaking = voiceState === 'speaking';

    const target = active ? Math.min(1, currentVoiceLevel()) : 0;
    orbLevel += (target - orbLevel) * 0.16;
    const lv = orbLevel;

    ctx.clearRect(0, 0, W, H);

    // tashqi yumshoq nur
    const halo = ctx.createRadialGradient(cx, cy, R * 0.84, cx, cy, R * 1.32);
    halo.addColorStop(0, 'rgba(120,140,255,' + (0.14 + lv * 0.18).toFixed(3) + ')');
    halo.addColorStop(1, 'rgba(120,140,255,0)');
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, W, H);

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.clip();

    // asos gradient
    const hue = speaking ? 256 : 232;
    const base = ctx.createRadialGradient(
      cx + R * 0.36, cy - R * 0.44, R * 0.05,
      cx, cy, R * 1.14);
    base.addColorStop(0.00, 'hsl(' + hue + ' 94% ' + (63 + lv * 7) + '%)');
    base.addColorStop(0.24, 'hsl(' + hue + ' 92% ' + (71 + lv * 5) + '%)');
    base.addColorStop(0.50, 'hsl(' + (hue - 4) + ' 88% 86%)');
    base.addColorStop(0.76, 'hsl(' + (hue - 8) + ' 80% 94%)');
    base.addColorStop(1.00, '#fbfcff');
    ctx.fillStyle = base;
    ctx.fillRect(cx - R, cy - R, R * 2, R * 2);

    // tutun qatlamlari
    const speed = 0.13 + lv * 0.55;
    const puffs = [
      { r: 0.88, a: 0.28 + lv * 0.24, h: hue,      ph: 0.0, d: 0.34 },
      { r: 0.72, a: 0.30 + lv * 0.22, h: hue + 18, ph: 2.1, d: 0.44 },
      { r: 0.64, a: 0.42,             h: null,     ph: 4.2, d: 0.38 },
      { r: 0.54, a: 0.24 + lv * 0.22, h: hue - 20, ph: 5.6, d: 0.30 },
    ];
    for (let i = 0; i < puffs.length; i++) {
      const pf = puffs[i];
      const ang = t * speed * (i % 2 ? -1 : 1) + pf.ph;
      const dist = R * pf.d * (0.58 + 0.42 * Math.sin(t * 0.47 + pf.ph));
      const px = cx + Math.cos(ang) * dist;
      const py = cy + Math.sin(ang * 0.82) * dist;
      const g = ctx.createRadialGradient(px, py, 0, px, py, R * pf.r);
      if (pf.h === null) {
        g.addColorStop(0, 'rgba(255,255,255,' + pf.a.toFixed(3) + ')');
        g.addColorStop(1, 'rgba(255,255,255,0)');
      } else {
        g.addColorStop(0, 'hsla(' + pf.h + ',92%,68%,' + pf.a.toFixed(3) + ')');
        g.addColorStop(1, 'hsla(' + pf.h + ',92%,68%,0)');
      }
      ctx.fillStyle = g;
      ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
    }

    // pastki-chapdagi oq yorug'lik — hajm beradi
    const lift = ctx.createRadialGradient(
      cx - R * 0.32, cy + R * 0.46, R * 0.04,
      cx - R * 0.32, cy + R * 0.46, R * 1.02);
    lift.addColorStop(0.00, 'rgba(255,255,255,.88)');
    lift.addColorStop(0.52, 'rgba(255,255,255,.22)');
    lift.addColorStop(1.00, 'rgba(255,255,255,0)');
    ctx.fillStyle = lift;
    ctx.fillRect(cx - R, cy - R, R * 2, R * 2);

    ctx.restore();

    // yupqa chekka
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,255,255,.5)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // ovozga qarab yengil kattalashish
    orbCanvas.style.transform = 'scale(' + (1 + lv * 0.10).toFixed(3) + ')';

    if (orbGlow) {
      orbGlow.style.background =
        'radial-gradient(circle, rgba(150,165,255,.30) 0%, rgba(182,208,255,.13) 55%, transparent 74%)';
      orbGlow.style.opacity = String(0.34 + (active ? lv * 0.32 : 0));
    }
    animationId = requestAnimationFrame(drawOrb);
  }

  // 2. Suhbat ichidagi Live Voice kartasi
  function setVoiceLauncherState(active) {
    if (!voiceInputBtn) return;
    voiceInputBtn.classList.toggle('voice-mode-active', active);
    voiceInputBtn.textContent = active ? '■' : '🎙';
    voiceInputBtn.title = active ? 'Ovozli suhbatni tugatish' : 'Mikrofondan gapiring';
  }

  function mountVoiceCard() {
    if (!chatArea) return;
    if (overlay.parentElement !== chatArea) chatArea.appendChild(overlay);
    overlay.classList.add('active');
    requestAnimationFrame(() => scrollDown(true));
  }

  async function openVoiceMode() {
    if (overlay.classList.contains('active')) {
      scrollDown(true);
      return;
    }
    mountVoiceCard();
    setVoiceLauncherState(true);
    voiceState = 'idle';
    if (statusText) statusText.textContent = "Live Voice tayyorlanmoqda...";
    if (transcriptText) transcriptText.textContent = "Siz gapiring, men eshitayapman...";
    if (!animationId) drawOrb();
    const connected = await startRealtimeVoice();
    if (!connected && overlay.classList.contains('active')) startListening();
  }

  function closeVoiceMode() {
    overlay.classList.remove('active');
    setVoiceLauncherState(false);
    spokenTurnInFlight = false;
    stopRealtimeVoice();
    stopListening();
    stopAudio();
    voiceState = 'idle';
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
  }

  // 3. Dual Speech Recognition & Recording Engine (WebSpeech + MediaRecorder Whisper)
  function startListening() {
    if (realtime || isMuted || spokenTurnInFlight || voiceState === 'thinking') return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
      if (recognition) {
        try { recognition.abort(); } catch(e){}
      }
      recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'uz-UZ';
      const run = ++listeningRun;

      recognition.onstart = function() {
        if (run !== listeningRun) return;
        voiceState = 'listening';
        void startFallbackSpeechMeter();
        if (statusText) statusText.textContent = "Eshitilmoqda...";
        if (transcriptText) transcriptText.textContent = "Gapirishingizni kutayapman...";
        if (micBtn) micBtn.classList.add('active');
      };

      recognition.onresult = function(event) {
        if (run !== listeningRun || spokenTurnInFlight) return;
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        if (transcriptText) transcriptText.textContent = final || interim || "...";
        audioLevel = Math.min(1, (interim.length || final.length) / 30 + 0.2);

        if (final.trim()) {
          void sendSpokenText(final.trim());
        }
      };

      recognition.onerror = function(event) {
        if (run !== listeningRun || spokenTurnInFlight || event.error === 'aborted') return;
        if (event.error !== 'no-speech') {
          console.warn('Speech recognition fallback to MediaRecorder:', event.error);
          listeningRun++;
          recognition = null;
          startMediaRecorderFallback();
        }
      };

      recognition.onend = function() {
        if (run !== listeningRun) return;
        recognition = null;
        if (voiceState === 'listening' && !isMuted) {
          setTimeout(() => {
            if (overlay.classList.contains('active') && voiceState === 'listening' && !spokenTurnInFlight) startListening();
          }, 400);
        }
      };

      try {
        recognition.start();
        return;
      } catch(e) {
        console.warn("Recognition start error, using fallback:", e);
      }
    }

    startMediaRecorderFallback();
  }

  async function startMediaRecorderFallback() {
    if (isMuted || spokenTurnInFlight || !navigator.mediaDevices) return;
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const preferred = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', 'audio/mp4'];
      const mimeType = preferred.find(type => MediaRecorder.isTypeSupported(type)) || '';
      mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined);
      if (!fallbackVoiceMeter) {
        fallbackVoiceMeter = { stream: mediaStream };
        attachAudioMeter(mediaStream, fallbackVoiceMeter, 'mic');
      }
      const chunks = [];
      voiceState = 'listening';
      if (statusText) statusText.textContent = "Ovoz yozilmoqda (Whisper)...";
      if (transcriptText) transcriptText.textContent = "Gapiring, tugatgach avtomatik tahlil qilinadi...";
      if (micBtn) micBtn.classList.add('active');

      mediaRecorder.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
      mediaRecorder.onstop = async () => {
        if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        if (blob.size > 200) {
          voiceState = 'thinking';
          if (statusText) statusText.textContent = "ChatGPT tahlil qilmoqda...";
          try {
            const reader = new FileReader();
            reader.readAsDataURL(blob);
            reader.onloadend = async () => {
              const base64 = reader.result.split(',')[1];
              const res = await fetch('/api/voice/transcribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ audio: base64, mimeType: blob.type })
              });
              const data = await res.json();
              if (data.text && data.text.trim()) {
                void sendSpokenText(data.text.trim());
              } else {
                voiceState = 'idle';
                setTimeout(startListening, 1000);
              }
            };
          } catch(e) {
            voiceState = 'idle';
            setTimeout(startListening, 1000);
          }
        }
      };

      mediaRecorder.start();
      setTimeout(() => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
          mediaRecorder.stop();
        }
      }, 7000);
    } catch(err) {
      if (statusText) statusText.textContent = "Mikrofonga ruxsat berilmadi";
    }
  }

  function stopListening() {
    listeningRun++;
    if (recognition) {
      try { recognition.abort(); } catch(e){}
      recognition = null;
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      try { mediaRecorder.stop(); } catch(e){}
      mediaRecorder = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.stop());
      mediaStream = null;
    }
    stopFallbackSpeechMeter();
    if (micBtn) micBtn.classList.remove('active');
  }

  // 4. Send Spoken Text & AI Response Processing
  async function sendSpokenText(text) {
    const clean = cleanTextForSpeech(text);
    if (!clean || spokenTurnInFlight) return;
    spokenTurnInFlight = true;
    stopListening();
    voiceState = 'thinking';
    if (statusText) statusText.textContent = "ChatGPT o'ylamoqda...";
    if (transcriptText) transcriptText.textContent = clean;

    const inputElem = $('#input');
    if (inputElem) {
      inputElem.value = clean;
      inputElem.dispatchEvent(new Event('input'));
    }

    const responseStartedAt = Date.now();
    try {
      if (typeof submit === 'function') {
        submit();
      }
      await waitForAiResponse(responseStartedAt);
    } catch(e) {
      if (statusText) statusText.textContent = "Xatolik yuz berdi";
      voiceState = 'idle';
      spokenTurnInFlight = false;
      setTimeout(startListening, 1500);
    }
  }

  // 5. Fast Audio Synthesis & Audio Analyzer
  async function speakAiResponse(text) {
    const isOverlayActive = overlay.classList.contains('active');
    if (!isOverlayActive && !VOICE_STATE.autoSpeak) return;

    const clean = cleanTextForSpeech(text);
    if (!clean) return;

    voiceState = 'speaking';
    if (statusText) statusText.textContent = "ChatGPT gapirmoqda...";
    if (transcriptText) transcriptText.textContent = clean.slice(0, 180) + (clean.length > 180 ? '...' : '');

    try {
      const selectedVoice = VOICE_STATE.voice || 'uz-UZ-SardorNeural';
      const endpoint = selectedVoice.startsWith('uz-UZ-') ? '/api/voice/edge' : '/api/voice/speech';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: clean.slice(0, 700),
          voice: selectedVoice,
          rate: '+20%'
        })
      });

      if (!res.ok) throw new Error("TTS audio error");
      const blob = await res.blob();
      const audioUrl = URL.createObjectURL(blob);

      stopAudio();
      currentAudio = new Audio(audioUrl);
      currentAudio.playbackRate = 1.04;

      if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaElementSource(currentAudio);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 64;
      source.connect(analyser);
      analyser.connect(audioContext.destination);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateLevel = () => {
        if (voiceState === 'speaking' && analyser) {
          analyser.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
          audioLevel = Math.min(1, (sum / dataArray.length) / 120);
          requestAnimationFrame(updateLevel);
        }
      };

      currentAudio.onplay = () => {
        if (audioContext && audioContext.state === 'suspended') audioContext.resume();
        updateLevel();
      };

      currentAudio.onended = () => {
        voiceState = 'idle';
        audioLevel = 0;
        spokenTurnInFlight = false;
        if (statusText) statusText.textContent = "ChatGPT Voice tayyor...";
        if (isOverlayActive) {
          setTimeout(() => {
            if (overlay.classList.contains('active')) startListening();
          }, 400);
        }
      };

      await currentAudio.play();

    } catch(e) {
      console.warn("Audio playback fallback:", e);
      if ('speechSynthesis' in window) {
        const synth = window.speechSynthesis;
        const utter = new SpeechSynthesisUtterance(clean.slice(0, 350));
        utter.rate = 1.15;
        utter.onend = () => {
          voiceState = 'idle';
          spokenTurnInFlight = false;
          if (statusText) statusText.textContent = "ChatGPT Voice tayyor...";
          if (isOverlayActive) setTimeout(startListening, 500);
        };
        synth.speak(utter);
      } else {
        voiceState = 'idle';
        spokenTurnInFlight = false;
        if (isOverlayActive) setTimeout(startListening, 1000);
      }
    }
  }

  window.speakSingleText = function(text) {
    const clean = cleanTextForSpeech(text);
    if (!clean) return;
    fetch('/api/voice/speech', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: clean.slice(0, 700), voice: VOICE_STATE.voice || 'uz-UZ-SardorNeural' })
    }).then(r => r.blob()).then(blob => {
      const audio = new Audio(URL.createObjectURL(blob));
      audio.play();
    }).catch(e => console.warn('Speech playback error:', e));
  };

  function stopAudio() {
    if (currentAudio) {
      try { currentAudio.pause(); } catch(e){}
      currentAudio = null;
    }
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }

  function waitForAiResponse(notBefore) {
    return new Promise((resolve) => {
      let attempts = 0;
      const checkInterval = setInterval(() => {
        attempts++;
        const inline = window.__voiceInlineResponse;
        if (inline && Number(inline.createdAt || 0) >= Number(notBefore || 0) && inline.text) {
          window.__voiceInlineResponse = null;
          clearInterval(checkInterval);
          speakAiResponse(inline.text);
          resolve(inline.text);
          return;
        }
        const completed = Array.from(document.querySelectorAll('#chatArea .msg.model[data-agent-complete="true"], #chatArea .msg.assistant[data-agent-complete="true"]'))
          .reverse()
          .find(message => Number(message.dataset.agentCompletedAt || 0) >= Number(notBefore || 0));
        const text = completed ? String(completed.dataset.agentText || '').trim() : '';

        if (text) {
          clearInterval(checkInterval);
          speakAiResponse(text);
          resolve(text);
        } else if (attempts > 90) {
          clearInterval(checkInterval);
          voiceState = 'idle';
          spokenTurnInFlight = false;
          if (statusText) statusText.textContent = "Javob belgilangan vaqtda kelmadi";
          setTimeout(startListening, 1000);
          resolve(null);
        }
      }, 250);
    });
  }

  if (voiceInputBtn) {
    voiceInputBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (overlay.classList.contains('active')) closeVoiceMode();
      else openVoiceMode();
    });
  }

  if (floatBtn) {
    floatBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openVoiceMode();
    });
  }

  if (closeBtn) closeBtn.onclick = closeVoiceMode;
  if (endBtn) endBtn.onclick = closeVoiceMode;

  const floatMicBtn = document.getElementById('cgvFloatMicBtn');
  const floatSolBtn = document.getElementById('cgvFloatSolBtn');
  const floatCloseBtn = document.getElementById('cgvFloatCloseBtn');
  const floatMinBtn = document.getElementById('cgvFloatMinBtn');
  const floatSpeakerBtn = document.getElementById('cgvFloatSpeakerBtn');

  // Sol tugmasi: ChatGPT Desktop ilovasida "Start voice chat" ni terminal orqali bosadi
  if (floatSolBtn) {
    floatSolBtn.onclick = async (e) => {
      e.stopPropagation();
      floatSolBtn.textContent = '⏳';
      floatSolBtn.disabled = true;
      try {
        const res = await fetch('/api/voice/trigger_chatgpt_desktop', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({prompt: ''})
        });
        const data = await res.json();
        if (data.ok) {
          floatSolBtn.textContent = '✅';
          setTimeout(() => { floatSolBtn.textContent = 'Sol 🎙'; floatSolBtn.disabled = false; }, 2000);
        } else {
          floatSolBtn.textContent = '❌';
          setTimeout(() => { floatSolBtn.textContent = 'Sol 🎙'; floatSolBtn.disabled = false; }, 2000);
        }
      } catch(err) {
        floatSolBtn.textContent = '❌';
        setTimeout(() => { floatSolBtn.textContent = 'Sol 🎙'; floatSolBtn.disabled = false; }, 2000);
      }
    };
  }

  if (floatCloseBtn) floatCloseBtn.onclick = (e) => { e.stopPropagation(); closeVoiceMode(); };
  if (floatMinBtn) floatMinBtn.onclick = (e) => {
    e.stopPropagation();
    const launcher = document.getElementById('cgvFloatingLauncher');
    if (launcher) launcher.classList.toggle('minimized');
  };
  if (floatSpeakerBtn) floatSpeakerBtn.onclick = (e) => {
    e.stopPropagation();
    floatSpeakerBtn.classList.toggle('active');
    stopAudio();
  };

  const toggleMicState = () => {
    isMuted = !isMuted;
    if (micBtn) micBtn.classList.toggle('active', !isMuted);
    if (floatMicBtn) floatMicBtn.classList.toggle('active', !isMuted);
    if (realtime) {
      realtime.stream.getAudioTracks().forEach(track => { track.enabled = !isMuted; });
      voiceState = isMuted ? 'idle' : 'listening';
      if (statusText) statusText.textContent = isMuted ? 'Mikrofon o‘chirildi' : 'Live Voice eshitmoqda…';
      return;
    }
    if (isMuted) {
      stopListening();
      if (statusText) statusText.textContent = "Mikrofon o'chirildi";
    } else {
      if (statusText) statusText.textContent = "Mikrofon yoqilmoqda...";
      startListening();
    }
  };

  if (micBtn) micBtn.onclick = toggleMicState;
  if (floatMicBtn) floatMicBtn.onclick = (e) => { e.stopPropagation(); toggleMicState(); };

  document.addEventListener('keydown', (e) => {
    if (e.altKey && (e.code === 'KeyV' || e.key === 'v' || e.key === 'V')) {
      e.preventDefault();
      if (overlay.classList.contains('active')) closeVoiceMode();
      else openVoiceMode();
    }
  });
})();

init();
</script></body></html>"""


def _oauth_qaytish(handler):
    """Google shu manzilga qaytaradi. Host so'rovdan olinadi — telefondan
    kirilgan bo'lsa ham to'g'ri manzil chiqadi."""
    host = handler.headers.get("Host") or ("localhost:%d" % PORT)
    return "http://%s/api/ulanish/sheets/callback" % host


def _ulanish_sahifasi(ok, xabar):
    """OAuth dan qaytgandan keyin ko'rinadigan kichik sahifa."""
    rang = "#34a853" if ok else "#ea4335"
    belgi = "✓" if ok else "✕"
    return ("""<!doctype html><meta charset="utf-8">
<title>MuhasibPro</title>
<style>
 body{margin:0;height:100vh;display:grid;place-items:center;background:#0e1116;
   color:#e8eef9;font:15px -apple-system,'Segoe UI',sans-serif}
 .q{max-width:420px;padding:30px;text-align:center}
 .b{width:56px;height:56px;margin:0 auto 16px;border-radius:50%%;display:grid;
   place-items:center;font-size:26px;background:%s22;color:%s}
 h1{margin:0 0 8px;font-size:18px}
 p{margin:0;color:#9aa8bd;font-size:13.5px;line-height:1.6}
 small{display:block;margin-top:18px;color:#6b7688;font-size:12px}
</style>
<div class="q"><div class="b">%s</div><h1>%s</h1>
<p>%s</p><small>Bu oynani yopishingiz mumkin.</small></div>
<script>setTimeout(()=>{try{window.close()}catch(e){}}, 2500)</script>""" %
            (rang, rang, belgi,
             "Ulandi" if ok else "Ulanmadi",
             ("Endi MuhasibPro jadvallaringiz bilan ishlaydi." if ok else _esc_html(xabar)))
            ).encode("utf-8")


def _esc_html(matn):
    return (str(matn).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def capture_desktop_frame():
    with DESKTOP_CAPTURE_LOCK:
        fd, frame_path = tempfile.mkstemp(prefix="agy_desktop_", suffix=".jpg")
        os.close(fd)
        try:
            result = subprocess.run(
                ["screencapture", "-x", "-m", "-t", "jpg", frame_path],
                capture_output=True,
                timeout=8,
            )
            if result.returncode != 0 or not os.path.isfile(frame_path) or os.path.getsize(frame_path) < 128:
                detail = (result.stderr or b"").decode("utf-8", "ignore").strip()
                raise RuntimeError(detail or "macOS Screen Recording ruxsati topilmadi.")
            with open(frame_path, "rb") as frame_file:
                return frame_file.read(), ""
        except Exception as exc:
            return b"", str(exc)
        finally:
            try:
                os.unlink(frame_path)
            except OSError:
                pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, body, content_type, code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _desktop_stream(self, first_frame, fps):
        boundary = b"desktop-live-frame"
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=" + boundary.decode("ascii"))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        frame = first_frame
        interval = 1 / fps
        try:
            while frame:
                started = time.monotonic()
                self.wfile.write(
                    b"--" + boundary + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode("ascii") + b"\r\n\r\n"
                    + frame + b"\r\n"
                )
                self.wfile.flush()
                wait_for = interval - (time.monotonic() - started)
                if wait_for > 0:
                    time.sleep(wait_for)
                frame, error = capture_desktop_frame()
                if error:
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _brauzer_oqim(self, birinchi_kadr, fps):
        chegara = b"brauzer-live-frame"
        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=" + chegara.decode("ascii"))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        kadr = birinchi_kadr
        oraliq = 1 / fps
        try:
            while kadr:
                boshlandi = time.monotonic()
                self.wfile.write(
                    b"--" + chegara + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(kadr)).encode("ascii") + b"\r\n\r\n"
                    + kadr + b"\r\n"
                )
                self.wfile.flush()
                kutish = oraliq - (time.monotonic() - boshlandi)
                if kutish > 0:
                    time.sleep(kutish)
                kadr, xato = brauzer.oxirgi_kadr()
                if xato:
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _sse(self, events):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            for ev in events:
                self.wfile.write(("data: " + json.dumps(ev) + "\n\n").encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass          # brauzer uzildi — job fonda davom etaveradi
        except Exception as e:
            try:
                self.wfile.write(("data: " + json.dumps({"done": True, "error": str(e)}) + "\n\n").encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def _read_body(self, maximum_size=1024 * 1024):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        if not length or length > maximum_size:
            return b""
        return self.rfile.read(length)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/status":
            signed, models = status_probe()
            account = find_google_account() if signed else {}
            local_ip = get_local_ip()
            self._json({
                "signedIn": signed,
                "email": account.get("email", ""),
                "pro": False,
                "account": account,
                "models": models,
                "codex": codex_cli_status(),
                "sol": {
                    "ready": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
                    "model": SOL_MODEL,
                    "id": SOL_MODEL_ID,
                },
                "port": PORT,
                "ip": local_ip,
                "networkUrl": f"http://{local_ip}:{PORT}",
                "home": HOME,
            })
            return

        if path == "/api/desktop/frame":
            frame, error = capture_desktop_frame()
            if error:
                self._json(
                    {
                        "error": "Desktop Live ekranini olish imkoni bo'lmadi. "
                        "System Settings → Privacy & Security → Screen Recording ichida "
                        "Terminal yoki Python uchun ruxsat bering. " + error
                    },
                    503,
                )
                return
            self._bytes(frame, "image/jpeg")
            return

        if path == "/api/desktop/stream":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                fps = float(qs.get("fps", ["8"])[0])
            except (TypeError, ValueError):
                fps = 8
            fps = max(1, min(10, fps))
            frame, error = capture_desktop_frame()
            if error:
                self._json(
                    {
                        "error": "Desktop Live oqimi ishga tushmadi. "
                        "System Settings → Privacy & Security → Screen Recording ichida "
                        "Terminal yoki Python uchun ruxsat bering. " + error
                    },
                    503,
                )
                return
            self._desktop_stream(frame, fps)
            return

        if path == "/api/ulanish/holat":
            try:
                self._json(ulanish.holat())
            except Exception as exc:
                self._json({"error": str(exc)[:200]}, 500)
            return

        if path == "/api/ulanish/qurilmalar":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                soniya = int(qs.get("soniya", ["6"])[0])
            except ValueError:
                soniya = 6
            try:
                self._json({"qurilmalar": ulanish.qurilmalar(soniya)})
            except Exception as exc:
                self._json({"error": str(exc)[:200]}, 500)
            return

        if path == "/api/ulanish/sheets/skript":
            # Foydalanuvchi Google Sheets ichiga joylaydigan kod va maxfiy so'z.
            try:
                import jadval
                sir = os.environ.get("SHEETS_SCRIPT_SIR") or jadval.skript_siri()
                if not os.environ.get("SHEETS_SCRIPT_SIR"):
                    _update_env_values({"SHEETS_SCRIPT_SIR": sir})
                    os.environ["SHEETS_SCRIPT_SIR"] = sir
                self._json({"ok": True, "kod": jadval.skript_kodi(sir),
                            "url": jadval.skript_url()})
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:220]}, 500)
            return

        if path == "/api/ulanish/sheets/oauth":
            # Ruxsat sahifasining manzilini beradi — u brauzer panelida ochiladi.
            try:
                import jadval
                self._json({"ok": True, "url": jadval.oauth_havola(_oauth_qaytish(self))})
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:220]}, 400)
            return

        if path == "/api/ulanish/sheets/callback":
            # Google shu yerga qaytaradi. Kodni doimiy tokenga almashtiramiz.
            qs = urllib.parse.parse_qs(parsed.query)
            xato = (qs.get("error") or [""])[0]
            code = (qs.get("code") or [""])[0]
            try:
                import jadval
                if xato or not code:
                    raise RuntimeError(xato or "Google kod qaytarmadi.")
                yangilanish = jadval.oauth_almashish(code, _oauth_qaytish(self))
                _update_env_values({"GOOGLE_OAUTH_REFRESH": yangilanish})
                os.environ["GOOGLE_OAUTH_REFRESH"] = yangilanish
                self._bytes(_ulanish_sahifasi(True, "Google Sheets ulandi"),
                            "text/html; charset=utf-8")
            except Exception as exc:
                self._bytes(_ulanish_sahifasi(False, str(exc)[:300]),
                            "text/html; charset=utf-8")
            return

        if path == "/api/ulanish/telegram/suhbatlar":
            try:
                self._json({"suhbatlar": ulanish.telegram_suhbatlar()})
            except Exception as exc:
                self._json({"error": str(exc)[:200]}, 500)
            return

        if path == "/api/brauzer/holat":
            # Panel shu bilan "Chrome ochiqmi" ni biladi — ochilmagan bo'lsa
            # bu so'rov Chrome'ni ishga TUSHIRMAYDI.
            try:
                ochiq = brauzer.tirikmi()
                sessiya = brauzer.sessiya()
                # Chrome ochiq bo'lsa manzilni jonli o'qiymiz — foydalanuvchi
                # panelda o'zi bosib boshqa sahifaga o'tsa ham manzil qatori
                # to'g'ri ko'rsatadi. Ochiq bo'lmasa tegmaymiz: aks holda bu
                # so'rovning o'zi Chrome'ni ishga tushirib qo'yardi.
                if ochiq:
                    try:
                        sessiya.holat()
                    except Exception:
                        pass
                self._json({"ochiq": ochiq,
                            "url": sessiya.oxirgi_url,
                            "sarlavha": sessiya.oxirgi_sarlavha,
                            "login": dict(LOGIN_SO_ROV)})
            except Exception as exc:
                self._json({"ochiq": False, "error": str(exc)[:200]})
            return

        if path == "/api/brauzer/kadr":
            kadr, xato = brauzer.oxirgi_kadr()
            if not kadr:
                self._json({"error": xato or "Brauzer kadri yo'q."}, 503)
                return
            self._bytes(kadr, "image/jpeg")
            return

        if path == "/api/brauzer/oqim":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                fps = float(qs.get("fps", ["2"])[0])
            except (TypeError, ValueError):
                fps = 2
            fps = max(0.5, min(4, fps))
            kadr, xato = brauzer.oxirgi_kadr()
            if not kadr:
                self._json({"error": xato or "Brauzer ochilmagan."}, 503)
                return
            self._brauzer_oqim(kadr, fps)
            return

        if path == "/api/video/config":
            try:
                self._json(video_configuration_status())
            except Exception as exc:
                self._json({"error": "Video sozlamasini o'qib bo'lmadi: " + str(exc)}, 500)
            return

        if path == "/api/voice/config":
            self._json(voice_configuration_status())
            return

        if path == "/api/login/state":
            with LOGIN.lock:
                url, term = LOGIN.url, LOGIN.buf[-4000:]
            signed, models = status_probe()
            account = find_google_account() if signed else {}
            self._json({
                "url": url,
                "term": term,
                "signedIn": signed,
                "email": account.get("email", ""),
                "pro": False,
                "account": account,
                "models": models,
                "codex": codex_cli_status(),
                "port": PORT,
            })
            return

        if path == "/api/excel/data":
            qs = urllib.parse.parse_qs(parsed.query)
            fp = os.path.abspath(os.path.expanduser(qs.get("path", [""])[0]))
            if not fp.startswith(HOME) or not os.path.isfile(fp):
                self._json({"status": "error", "error": "File not found"}, code=404)
                return
            try:
                sheet_title = "Sheet1"
                rows = []
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(fp, data_only=True)
                    sheet = wb.active
                    sheet_title = sheet.title
                    for r in sheet.iter_rows(values_only=True):
                        row = [str(val) if val is not None else "" for val in r]
                        if any(row):
                            rows.append(row)
                except Exception:
                    import zipfile, xml.etree.ElementTree as ET
                    with zipfile.ZipFile(fp, 'r') as z:
                        strings = []
                        if 'xl/sharedStrings.xml' in z.namelist():
                            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                            for si in tree.findall('.//s:si', ns):
                                txts = [t.text for t in si.findall('.//s:t', ns) if t.text]
                                strings.append("".join(txts))
                        sheet_path = 'xl/worksheets/sheet1.xml'
                        if sheet_path not in z.namelist():
                            sheets = [f for f in z.namelist() if f.startswith('xl/worksheets/sheet')]
                            if sheets: sheet_path = sheets[0]
                        tree = ET.fromstring(z.read(sheet_path))
                        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        for r_elem in tree.findall('.//s:row', ns):
                            row = []
                            for c_elem in r_elem.findall('s:c', ns):
                                t_type = c_elem.attrib.get('t', '')
                                v_elem = c_elem.find('s:v', ns)
                                val = v_elem.text if v_elem is not None else ''
                                if t_type == 's' and val.isdigit() and int(val) < len(strings):
                                    val = strings[int(val)]
                                row.append(val)
                            if any(row):
                                rows.append(row)
                self._json({
                    "status": "ok",
                    "filename": os.path.basename(fp),
                    "sheet": sheet_title,
                    "rows": rows
                })
            except Exception as e:
                self._json({"status": "error", "error": str(e)}, code=500)
            return

        if path == "/api/file":
            qs = urllib.parse.parse_qs(parsed.query)
            fp = os.path.abspath(os.path.expanduser(qs.get("path", [""])[0]))
            if not fp.startswith(HOME) or not os.path.isfile(fp):
                self.send_response(404)
                self.end_headers()
                return
            size = os.path.getsize(fp)
            start, end, status = 0, size - 1, 200
            rng = self.headers.get("Range") or ""
            if rng.startswith("bytes="):
                try:
                    a, _, b = rng[6:].partition("-")
                    start = int(a) if a else 0
                    end = min(int(b), size - 1) if b else size - 1
                    status = 206
                except Exception:
                    start, end, status = 0, size - 1, 200
            length = max(0, end - start + 1)
            self.send_response(status)
            self.send_header("Content-Type", mimetypes.guess_type(fp)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            if status == 206:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.end_headers()
            try:
                with open(fp, "rb") as fh:
                    fh.seek(start)
                    left = length
                    while left > 0:
                        chunk = fh.read(min(262144, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if path == "/api/jobs":
            _prune_jobs()
            with JOBS_LOCK:
                jobs = [{
                    "id": j["id"], "session": j["session"], "prompt": j["prompt"][:200],
                    "folder": j["folder"], "started": j["started"], "state": j["state"],
                    "steps": len(j["events"]), "visual": j.get("visual", False),
                    "trueMotion": j.get("trueMotion", False),
                } for j in JOBS.values()]
            jobs.sort(key=lambda j: j["started"], reverse=True)
            self._json({"jobs": jobs})
            return

        if path == "/api/job":
            qs = urllib.parse.parse_qs(parsed.query)
            jid = qs.get("id", [""])[0]
            frm = qs.get("from", ["0"])[0]
            with JOBS_LOCK:
                job = JOBS.get(jid)
            if not job:
                self._sse(iter([{"done": True, "error": "Bu ish topilmadi (server qayta ishga tushgan bo'lishi mumkin)."}]))
                return
            try:
                frm = int(frm)
            except Exception:
                frm = 0
            self._sse(follow_job(job, frm))
            return

        if path == "/api/file/read":
            qs = urllib.parse.parse_qs(parsed.query)
            fp = os.path.abspath(os.path.expanduser(qs.get("path", [""])[0]))
            if not fp.startswith(HOME) or not os.path.isfile(fp):
                self._json({"error": "Fayl topilmadi yoki ruxsat yo'q"}, 404)
                return
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(500000)
                self._json({"path": fp, "name": os.path.basename(fp), "content": content, "size": os.path.getsize(fp)})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/tree":
            qs = urllib.parse.parse_qs(parsed.query)
            p = os.path.expanduser(qs.get("path", [""])[0] or HOME) or HOME
            if not os.path.isdir(p):
                p = HOME
            p = os.path.abspath(p)
            def scan_tree(root, depth=0):
                if depth > 2: return []
                res = []
                try:
                    entries = sorted(os.listdir(root))
                    for e in entries:
                        if e.startswith(".") and e not in (".venv", ".claude"):
                            continue
                        if e in ("node_modules", "__pycache__", ".git", "build", "dist"):
                            continue
                        full = os.path.join(root, e)
                        is_d = os.path.isdir(full)
                        item = {
                            "name": e,
                            "path": full,
                            "isDir": is_d,
                            "size": 0 if is_d else os.path.getsize(full)
                        }
                        if is_d and depth < 2:
                            item["children"] = scan_tree(full, depth + 1)
                        res.append(item)
                except Exception:
                    pass
                return res
            self._json({"path": p, "tree": scan_tree(p)})
            return

        if path == "/api/ls":
            qs = urllib.parse.parse_qs(parsed.query)
            p = os.path.expanduser(qs.get("path", [""])[0] or HOME) or HOME
            if not os.path.isdir(p):
                p = HOME
            p = os.path.abspath(p)
            try:
                dirs = sorted(
                    e for e in os.listdir(p)
                    if not e.startswith(".") and os.path.isdir(os.path.join(p, e))
                )
            except Exception:
                dirs = []
            self._json({"path": p, "parent": os.path.dirname(p) or "/", "dirs": dirs})
            return

        if path.startswith("/images/") or path.startswith("/images_real/"):
            # Tovar rasmlari. Faqat shu ikki papka ichi — yo'l normallashtirilib
            # tekshiriladi, aks holda ../ bilan boshqa fayllarni o'qib olish mumkin.
            try:
                ildiz = os.path.dirname(os.path.abspath(__file__))
                nisbiy = urllib.parse.unquote(path.lstrip("/"))
                toliq = os.path.realpath(os.path.join(ildiz, nisbiy))
                ruxsat = [os.path.realpath(os.path.join(ildiz, d))
                          for d in ("images", "images_real")]
                if not any(toliq.startswith(r + os.sep) for r in ruxsat):
                    self._json({"error": "Ruxsat yo'q"}, code=403)
                    return
                if not os.path.isfile(toliq):
                    self._json({"error": "Topilmadi"}, code=404)
                    return
                with open(toliq, "rb") as fh:
                    tana = fh.read()
                tur = mimetypes.guess_type(toliq)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", tur)
                self.send_header("Content-Length", str(len(tana)))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(tana)
            except Exception as exc:
                self._json({"error": str(exc)}, code=500)
            return

        if path == "/api/hisob":
            # Jonli panel shu yerdan oziqlanadi — hammasi jurnaldan hisoblanadi.
            try:
                self._json({"status": "ok", "hisob": hisob.hisobot()})
            except Exception as exc:
                self._json({"status": "error", "error": str(exc)}, code=500)
            return

        if path == "/api/hisob/jurnal":
            # Dashboard zanjiri: har amal, o'zgarish va keyingi qoldiq
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                limit = int((q.get("limit") or ["1000"])[0])
                self._json({"status": "ok", "jurnal": hisob.jurnal(limit)})
            except Exception as exc:
                self._json({"status": "error", "error": str(exc)}, code=500)
            return

        if path == "/api/hisob/amallar":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self._json({"status": "ok", "amallar": hisob.amallar(
                    limit=int((qs.get("limit") or ["40"])[0]),
                    kim=(qs.get("kim") or [""])[0],
                    tur=(qs.get("tur") or [""])[0],
                )})
            except Exception as exc:
                self._json({"status": "error", "error": str(exc)}, code=500)
            return
        # ── Ulashilgan sessiyalar GET API ──

        if path == "/api/session/shared":
            try:
                self._json(list_shared_sessions())
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return

        if path.startswith("/api/session/shared/"):
            share_id = path.replace("/api/session/shared/", "", 1)
            if share_id and share_id != "delete":
                data = get_shared_session(share_id)
                if data:
                    self._json(data)
                else:
                    self._json({"error": "Sessiya topilmadi"}, 404)
                return

        if path.startswith("/shared/"):
            # Ulashilgan sessiya URL — asosiy sahifani qaytaradi, JS o'zi yuklaydi
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        global _EMAIL, CONVO
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/switch":
            LOGIN.stop()
            clear_google_account_cache()
            LOGIN.start()
            time.sleep(0.5)
            with LOGIN.lock:
                url = LOGIN.url
            self._json({"url": url})
            return

        if path == "/api/login/start":
            signed, models = status_probe()
            if signed:
                account = find_google_account()
                self._json({
                    "signedIn": True,
                    "email": account.get("email", ""),
                    "pro": False,
                    "account": account,
                    "models": models,
                    "codex": codex_cli_status(),
                    "port": PORT,
                })
                return
            LOGIN.start()
            time.sleep(0.5)
            with LOGIN.lock:
                url = LOGIN.url
            self._json({"signedIn": False, "url": url})
            return

        if path == "/api/login/input":
            data = self._read_json()
            LOGIN.write_line(str(data.get("text", "")))
            self._json({"ok": True})
            return

        if path == "/api/new-chat":
            CONVO = False
            self._json({"ok": True})
            return

        if path == "/api/brauzer/amal":
            # Paneldagi bosish/yozish to'g'ridan-to'g'ri Chrome'ga uzatiladi.
            # Shu tufayli foydalanuvchi saytga o'zi kirib, parolini o'zi
            # kiritadi — agent uni ko'rmaydi ham, yozmaydi ham.
            try:
                data = self._read_json()
                sahifa = brauzer.sessiya()
                tur = str(data.get("tur") or "")
                if tur == "bos":
                    javob = sahifa.xom_bos(data.get("x"), data.get("y"), bool(data.get("ikki")))
                elif tur == "yoz":
                    javob = sahifa.xom_yoz(data.get("matn") or "")
                elif tur == "tugma":
                    javob = sahifa.tugma(data.get("tugma") or "Enter")
                elif tur == "scroll":
                    javob = sahifa.xom_aylantir(data.get("x") or 0, data.get("y") or 0,
                                                data.get("delta") or 0)
                elif tur == "olcham":
                    en, boy = sahifa.olcham()
                    javob = {"ok": True, "en": en, "boy": boy}
                else:
                    self._json({"ok": False, "error": "Noma'lum amal"}, 400)
                    return
                self._json(javob)
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)[:200]}, 500)
            return

        if path == "/api/brauzer/davom":
            # "Kirdim, davom et" tugmasi — kutib turgan agentni uyg'otadi.
            LOGIN_KUTISH.set()
            self._json({"ok": True})
            return

        if path == "/api/ulanish/tv/boshla":
            # TV ekranida 6 xonali kod chiqadi — bu tasdiqlashning o'zi.
            try:
                data = self._read_json()
                self._json(ulanish.tv_ulanish_boshla(str(data.get("host") or "")))
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:200]}, 500)
            return

        if path == "/api/ulanish/tv/tasdiq":
            try:
                data = self._read_json()
                self._json(ulanish.tv_ulanish_tugat(str(data.get("kod") or "")))
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:200]}, 500)
            return

        if path == "/api/ulanish/telegram":
            # Bot tokeni .env ga yoziladi — parol emas, xohlagan payt bekor qilinadi.
            try:
                data = self._read_json()
                token = "" if data.get("clear") else str(data.get("token") or "").strip()
                if token and not re.match(r"^\d{6,}:[A-Za-z0-9_-]{30,}$", token):
                    self._json({"ok": False, "sabab": "Token noto'g'ri ko'rinishda. "
                                "@BotFather bergan to'liq tokenni joylang."}, 400)
                    return
                _update_env_values({"TELEGRAM_BOT_TOKEN": token})
                os.environ["TELEGRAM_BOT_TOKEN"] = token
                self._json({"ok": True, **ulanish.telegram_holat()})
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:200]}, 500)
            return

        if path == "/api/ulanish/sheets":
            # Kalit `.env` da yo'l yoki JSON matni sifatida saqlanadi.
            try:
                import jadval
                data = self._read_json()
                if data.get("clear"):
                    _update_env_values({"GOOGLE_SA_JSON": ""})
                    os.environ["GOOGLE_SA_JSON"] = ""
                    jadval._TOKEN.update({"qiymat": "", "tugaydi": 0})
                    self._json({"ok": True, "ulangan": False})
                    return
                kalit = str(data.get("kalit") or "").strip()
                _update_env_values({"GOOGLE_SA_JSON": kalit})
                os.environ["GOOGLE_SA_JSON"] = kalit
                jadval._TOKEN.update({"qiymat": "", "tugaydi": 0})
                if not jadval.sozlangan():
                    self._json({"ok": False, "sabab": "Kalit o'qilmadi. JSON fayl yo'lini yoki "
                                "faylning to'liq mazmunini joylang."}, 400)
                    return
                try:
                    jadval.royxat(1)          # kalit haqiqatan ishlayaptimi
                except Exception as exc:
                    self._json({"ok": False, "sabab": str(exc)[:260]}, 400)
                    return
                self._json({"ok": True, "pochta": jadval.hisob_pochtasi()})
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:220]}, 500)
            return

        if path == "/api/ulanish/sheets/skript":
            # Deploy qilingan web app manzili. Darrov sinab ko'ramiz.
            try:
                import jadval
                data = self._read_json()
                if data.get("clear"):
                    _update_env_values({"SHEETS_SCRIPT_URL": ""})
                    os.environ["SHEETS_SCRIPT_URL"] = ""
                    self._json({"ok": True, "ulangan": False})
                    return
                url = str(data.get("url") or "").strip()
                if "/exec" not in url:
                    self._json({"ok": False, "sabab": "Manzil `/exec` bilan tugashi kerak. "
                                "Deploy oynasidagi «Web app URL» ni nusxalang."}, 400)
                    return
                _update_env_values({"SHEETS_SCRIPT_URL": url})
                os.environ["SHEETS_SCRIPT_URL"] = url
                try:
                    jadval.skript_tekshir()
                except Exception as exc:
                    _update_env_values({"SHEETS_SCRIPT_URL": ""})
                    os.environ["SHEETS_SCRIPT_URL"] = ""
                    self._json({"ok": False, "sabab": str(exc)[:280]}, 400)
                    return
                self._json({"ok": True, "ulangan": True})
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:220]}, 500)
            return

        if path == "/api/ulanish/sheets/mijoz":
            # client_secret.json — yo'li yoki mazmuni.
            try:
                import jadval
                data = self._read_json()
                if data.get("clear"):
                    _update_env_values({"GOOGLE_OAUTH_CLIENT": "", "GOOGLE_OAUTH_REFRESH": ""})
                    os.environ["GOOGLE_OAUTH_CLIENT"] = ""
                    os.environ["GOOGLE_OAUTH_REFRESH"] = ""
                    jadval._TOKEN.update({"qiymat": "", "tugaydi": 0})
                    self._json({"ok": True, "mijoz_bor": False})
                    return
                xom = str(data.get("mijoz") or "").strip()
                _update_env_values({"GOOGLE_OAUTH_CLIENT": xom})
                os.environ["GOOGLE_OAUTH_CLIENT"] = xom
                if not jadval.oauth_sozlangan():
                    self._json({"ok": False, "sabab": "Fayl o'qilmadi. Google Cloud'dan "
                                "yuklangan client_secret.json yo'lini yoki mazmunini joylang."}, 400)
                    return
                self._json({"ok": True, "mijoz_bor": True})
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:220]}, 500)
            return

        if path == "/api/ulanish/sheets/avto":
            # Qaysi jadvalga avtomatik yozilsin.
            try:
                import jadval
                data = self._read_json()
                manba = str(data.get("jadval") or "").strip()
                varaq = str(data.get("varaq") or "").strip() or "Amallar"
                holat = jadval.avto_sozla(manba, varaq)
                _update_env_values({"SHEETS_AVTO_ID": holat["id"],
                                    "SHEETS_AVTO_VARAQ": holat["varaq"]})
                os.environ["SHEETS_AVTO_ID"] = holat["id"]
                os.environ["SHEETS_AVTO_VARAQ"] = holat["varaq"]
                javob = {"ok": True, **holat}
                if holat["id"]:
                    javob["sinxron"] = jadval.sinxronla()   # darrov bir marta yuboramiz
                self._json(javob)
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:220]}, 500)
            return

        if path == "/api/ulanish/sheets/sinxron":
            try:
                import jadval
                self._json(jadval.sinxronla(kuchli=True))
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:220]}, 500)
            return

        if path == "/api/ulanish/sinov":
            # Paneldagi "Sinab ko'rish" tugmasi — foydalanuvchi o'zi bosadi.
            try:
                data = self._read_json()
                tur = str(data.get("tur") or "")
                if tur == "printer":
                    javob = ulanish.chop_et(
                        matn="MuhasibPro\n--------------------\nSinov cheki\n"
                             + time.strftime("%Y-%m-%d %H:%M") + "\nUlanish ishlayapti.\n\n\n",
                        printer=str(data.get("printer") or ""))
                elif tur == "telegram":
                    javob = ulanish.telegram_yuborish(
                        data.get("kimga"), "MuhasibPro: ulanish sinovi ✅")
                elif tur == "tv":
                    javob = ulanish.tv_buyruq(nom="uy")
                else:
                    javob = {"ok": False, "sabab": "noma'lum sinov"}
                self._json(javob)
            except Exception as exc:
                self._json({"ok": False, "sabab": str(exc)[:200]}, 500)
            return

        if path == "/api/brauzer/och":
            # Paneldagi manzil qatori: foydalanuvchi o'zi sayt ochadi, keyin
            # agentga "shu sahifada shuni qil" deb ayta oladi.
            try:
                data = self._read_json()
                sahifa = brauzer.sessiya()
                holat = sahifa.orqaga() if data.get("orqaga") else sahifa.och(str(data.get("url") or ""))
                self._json({"ok": True, **holat})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)[:220]}, 400)
            return

        if path == "/api/video/config":
            try:
                data = self._read_json()
                if data.get("clear"):
                    clear_gemini_api_key()
                else:
                    save_gemini_api_key(data.get("geminiApiKey"))
                self._json(video_configuration_status())
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
            except Exception as exc:
                self._json({"error": "Video sozlamasini saqlab bo'lmadi: " + str(exc)}, 500)
            return

        if path == "/api/voice/config":
            try:
                data = self._read_json()
                if data.get("clear"):
                    clear_openai_api_key()
                elif data.get("openaiApiKey"):
                    save_openai_api_key(data.get("openaiApiKey"))
                else:
                    # Ovoz oynasidagi tanlagichlar: model / nutq / rejim.
                    # .env ga yoziladi va joriy jarayonga darhol qo'llanadi;
                    # yangi qiymat KEYINGI ovozli sessiyada kuchga kiradi.
                    allowed = {
                        "realtimeModel":   ("OPENAI_REALTIME_MODEL",
                                            {"gpt-realtime-2.1", "gpt-realtime"}),
                        "transcribeModel": ("OPENAI_TRANSCRIBE_MODEL",
                                            {"gpt-live-transcribe", "gpt-4o-transcribe",
                                             "gpt-4o-mini-transcribe", "whisper-1"}),
                        "eagerness":       ("OPENAI_REALTIME_EAGERNESS",
                                            {"high", "medium", "low"}),
                    }
                    changes = {}
                    for field, (env_key, valid) in allowed.items():
                        val = str(data.get(field) or "").strip()
                        if not val:
                            continue
                        if val not in valid:
                            raise ValueError(f"'{val}' — bu yerda ruxsat etilmagan qiymat.")
                        changes[env_key] = val
                        os.environ[env_key] = val
                    if changes:
                        _update_env_values(changes)
                self._json(voice_configuration_status())
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
            except Exception as exc:
                self._json({"error": "OpenAI ovoz sozlamasini saqlab bo'lmadi: " + str(exc)}, 500)
            return

        if path == "/api/voice/edge":
            try:
                # Bu endpoint 8777 interfeysida ISHLATILMAYDI — u yerdagi barcha
                # ovozlar olib tashlangan. Faqat 8779 dagi "O'zbekcha suhbat"
                # rejimi uchun zaxira sifatida qoldirilgan: edge-tts, o'zbekcha.
                data = self._read_json()
                text = data.get("text")
                voice = str(data.get("voice") or "uz-UZ-SardorNeural").strip()
                rate = str(data.get("rate") or "+25%").strip()
                female = {"marin", "coral", "shimmer", "nova", "sage", "uz-uz-madinaneural"}
                edge_voice = voice if voice.startswith("uz-UZ-") else (
                    "uz-UZ-MadinaNeural" if voice.lower() in female else "uz-UZ-SardorNeural")
                audio = generate_edge_tts_speech(text, voice=edge_voice, rate=rate)
                self._bytes(audio, "audio/mpeg")
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
            except Exception as exc:
                self._json({"error": "Edge-TTS ovoz yaratilmadi: " + str(exc)}, 500)
            return


        if path == "/api/hisob/rasm":
            try:
                data = self._read_json()
                amal = str(data.get("amal") or "").strip()
                if amal == "biriktirish":
                    natija = hisob.rasm_biriktirish(data.get("tovar"), data.get("rasm"))
                elif amal == "ochirish":
                    natija = {"ochirildi": bool(hisob.rasm_ochirish(data.get("tovar")))}
                else:
                    raise ValueError("Noma'lum amal: " + (amal or "(bo'sh)"))
                self._json({"status": "ok", "natija": natija, "hisob": hisob.hisobot()})
            except ValueError as exc:
                self._json({"status": "error", "error": str(exc)}, code=400)
            except Exception as exc:
                self._json({"status": "error", "error": str(exc)}, code=500)
            return

        if path == "/api/hisob/barkod":
            try:
                data = self._read_json()
                amal = str(data.get("amal") or "").strip()
                if amal == "biriktirish":
                    natija = hisob.barkod_biriktirish(data.get("tovar"), data.get("barkod") or "")
                elif amal == "ochirish":
                    natija = {"ochirildi": bool(hisob.barkod_ochirish(data.get("tovar")))}
                elif amal == "topish":
                    natija = hisob.barkod_topish(data.get("barkod"))
                else:
                    raise ValueError("Noma'lum amal: " + (amal or "(bo'sh)"))
                self._json({"status": "ok", "natija": natija, "hisob": hisob.hisobot()})
            except ValueError as exc:
                self._json({"status": "error", "error": str(exc)}, code=400)
            except Exception as exc:
                self._json({"status": "error", "error": str(exc)}, code=500)
            return

        if path == "/api/hisob/amal":
            # Dashboarddan amalni o'chirish (Delete tugmasi)
            try:
                data = self._read_json()
                if str(data.get("amal") or "") != "ochirish":
                    raise ValueError("Faqat 'ochirish' amali qo'llab-quvvatlanadi.")
                if not hisob.amal_ochirish(data.get("id")):
                    self._json({"status": "error", "error": "Amal topilmadi."}, code=404)
                    return
                self._json({"status": "ok", "hisob": hisob.hisobot()})
            except ValueError as exc:
                self._json({"status": "error", "error": str(exc)}, code=400)
            except Exception as exc:
                self._json({"status": "error", "error": str(exc)}, code=500)
            return

        if path == "/api/hisob/kassa":
            # Panel ichidan kassa ochish / nomlash / o'chirish
            try:
                data = self._read_json()
                amal = str(data.get("amal") or "").strip()
                if amal == "ochish":
                    natija = hisob.kassa_ochish(data.get("nom"), data.get("valyuta"))
                elif amal == "nomlash":
                    natija = hisob.kassa_nomlash(data.get("eski_nom"), data.get("yangi_nom"))
                elif amal == "ochirish":
                    natija = {"ochirildi": bool(hisob.kassa_ochirish(data.get("nom")))}
                else:
                    raise ValueError("Noma'lum amal: " + (amal or "(bo'sh)"))
                self._json({"status": "ok", "natija": natija, "hisob": hisob.hisobot()})
            except ValueError as exc:
                self._json({"status": "error", "error": str(exc)}, code=400)
            except Exception as exc:
                self._json({"status": "error", "error": str(exc)}, code=500)
            return

        if path == "/api/voice/transcribe":
            try:
                data = self._read_json()
                text = transcribe_openai_audio(
                    data.get("audio"),
                    str(data.get("mimeType") or "").lower(),
                )
                self._json({"text": text})
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
        if path == "/api/voice/trigger_chatgpt_desktop":
            try:
                data = self._read_json()
                prompt = str(data.get("prompt") or "").strip()
                ok = trigger_chatgpt_desktop_voice_session(prompt)
                self._json({"ok": ok, "message": "ChatGPT Desktop Voice mode faollashtirildi!"})
            except Exception as exc:
                self._json({"error": "ChatGPT Desktop Voice rejimi ishga tushmadi: " + str(exc)}, 500)
            return

        if path == "/api/job/stop":
            data = self._read_json()
            self._json({"ok": stop_job(data.get("id") or "")})
            return

        # ── Ulashilgan sessiyalar POST API ──

        if path == "/api/session/share":
            try:
                data = self._read_json()
                result = share_session(data)
                self._json(result)
            except Exception as exc:
                self._json({"error": "Ulashishda xato: " + str(exc)}, 500)
            return

        if path == "/api/session/shared/delete":
            try:
                data = self._read_json()
                share_id = data.get("id") or ""
                ok = delete_shared_session(share_id)
                self._json({"ok": ok})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return

        if path == "/api/chat":
            try:
                data = self._read_json()
                prompt = data.get("prompt") or ""
                model = data.get("model") or ""
                cont = bool(data.get("cont"))
                folder = data.get("folder") or ""
                session = data.get("session") or ""
                attachment_path = persist_attached_image(data.get("image"))
                if data.get("image") and not attachment_path:
                    self._json({"error": "Biriktirilgan rasmni o'qib bo'lmadi. PNG, JPG, WEBP yoki GIF rasm yuboring."}, 400)
                    return
                job = start_job(prompt, model, cont, folder, session, attachment_path)
            except Exception as exc:
                self._json({"error": "Chat ishini boshlashda xato: " + str(exc)}, 500)
                return
            self._sse(follow_job(job, 0))
            return

        if path == "/api/mkdir":
            data = self._read_json()
            parent = data.get("parent") or data.get("path") or ""
            name = (data.get("name") or "").strip()
            if not name or not parent:
                self._json({"error": "Papka nomi ko'rsatilmadi"}, 400)
                return
            parent_dir = os.path.abspath(os.path.expanduser(parent))
            if not os.path.isdir(parent_dir):
                self._json({"error": "Asosiy papka topilmadi"}, 400)
                return
            new_dir = os.path.join(parent_dir, name)
            try:
                os.makedirs(new_dir, exist_ok=True)
                self._json({"ok": True, "path": new_dir})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()


def _sheets_avtosini_tikla():
    """Dastur qayta ishga tushganda avto-sinxron sozlamasi tiklanadi va
    daftar kuzatuvchisi ulanadi — foydalanuvchi qayta sozlamasligi kerak."""
    try:
        import jadval
        jadval.avto_sozla(os.environ.get("SHEETS_AVTO_ID") or "",
                          os.environ.get("SHEETS_AVTO_VARAQ") or "Amallar")
        jadval.kuzatuvni_yoq()
    except Exception:
        pass


def main():
    _sheets_avtosini_tikla()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    local_ip = get_local_ip()
    url_local = f"http://localhost:{PORT}"
    url_network = f"http://{local_ip}:{PORT}"
    print(f"agy_app tayyor:")
    print(f"  Local:   {url_local}")
    print(f"  Network: {url_network}")
    threading.Timer(0.6, lambda: webbrowser.open(url_local)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        LOGIN.stop()


if __name__ == "__main__":
    main()
