#!/usr/bin/env python3
"""Rasm yuborish va tahlil qilish skripti (Send Image Script).

Ishlatish usullari:
  1. Terminal orqali:
     python3 send_image.py <rasm_yo'li> [savol_yoki_topshiriq]
     Masalan:
     python3 send_image.py my_photo.png "Rasmdagi matnni o'qib ber"

  2. Python kodingiz ichidan:
     from send_image import send_image
     res = send_image("my_photo.png", "Rasmni tahlil qil")
     print(res)
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time

AGY = os.path.expanduser("~/.local/bin/agy")
if not os.path.exists(AGY):
    AGY = shutil.which("agy") or "agy"

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()


def send_image_via_gemini_sdk(image_path: str, prompt: str = "", model: str = "gemini-2.5-flash") -> str:
    """Gemini Direct API SDK yordamida rasm yuborish."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=API_KEY)
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/png"
        if ext in (".jpg", ".jpeg"):
            mime_type = "image/jpeg"
        elif ext == ".webp":
            mime_type = "image/webp"
        elif ext == ".gif":
            mime_type = "image/gif"

        part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
        user_prompt = prompt or "Ushbu rasmni diqqat bilan tahlil qiling va batafsil tushuntirib bering."

        response = client.models.generate_content(
            model=model,
            contents=[part, user_prompt]
        )
        return response.text
    except Exception as e:
        return f"Gemini SDK orqali yuborishda xatolik: {e}"


def send_image_via_agy_cli(image_path: str, prompt: str = "") -> str:
    """AGY (Google Antigravity CLI) orqali rasm yuborish va tahlil qilish."""
    abs_path = os.path.abspath(image_path)
    if not os.path.exists(abs_path):
        return f"Xatolik: Fayl topilmadi: {image_path}"

    cwd = os.path.dirname(abs_path) or os.getcwd()
    user_prompt = prompt or "Ushbu rasmni ko'rib chiqing va unda nimalar tasvirlanganini batafsil tushuntirib bering."
    full_prompt = f"[Biriktirilgan rasm: {abs_path}]\n{user_prompt}"

    args = [
        AGY,
        "-p", full_prompt,
        "--output-format", "text",
        "--dangerously-skip-permissions",
        "--add-dir", cwd
    ]

    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=300, cwd=cwd)
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        if out:
            return out
        if err:
            return f"AGY CLI xabari: {err}"
        return "(Javob bo'sh)"
    except Exception as e:
        return f"AGY CLI bajarishda xatolik: {e}"


def send_image(image_path: str, prompt: str = "", model: str = "gemini-2.5-flash") -> str:
    """Rasm yuborish asosi - API Key bo'lsa Gemini SDK, bo'lmasa AGY CLI ishlatadi."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Rasm fayli topilmadi: {image_path}")

    if API_KEY:
        print("🔑 GEMINI_API_KEY topildi, Gemini SDK orqali yuborilmoqda...")
        return send_image_via_gemini_sdk(image_path, prompt, model)
    else:
        print("🚀 Google Antigravity CLI (AGY) orqali rasm yuborilmoqda...")
        return send_image_via_agy_cli(image_path, prompt)


def main():
    if len(sys.argv) < 2:
        print("Foydalanish: python3 send_image.py <rasm_fayli_yo'li> [savol_yoki_topshiriq]")
        print("Masalan:    python3 send_image.py screenshot.png \"Ushbu rasmdagi xatoni tushuntir\"")
        sys.exit(1)

    img_path = sys.argv[1]
    prompt_text = sys.argv[2] if len(sys.argv) > 2 else ""

    print(f"📸 Rasm tahlil qilinmoqda: {img_path}")
    if prompt_text:
        print(f"💬 Savol: {prompt_text}")
    print("-" * 50)

    try:
        result = send_image(img_path, prompt_text)
        print("\n🤖 AI Javobi:\n")
        print(result)
    except Exception as e:
        print(f"\n❌ Xatolik yuz berdi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
