#!/usr/bin/env python3
"""Generate a real image-to-video clip and mix it with Uzbek neural narration."""
from __future__ import annotations

import argparse
import asyncio
import math
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import edge_tts

from ai_video_generator import VideoGenerationError, generate_real_human_video, provider_ready

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = Path(__file__).resolve().parent
DEFAULT_MOTION_PROMPT = (
    "The person in the reference photo moves like a real human: natural breathing, subtle blinking, "
    "a warm genuine smile, realistic face and hand gestures while speaking toward a modern POS scanner. "
    "Preserve the person's identity, clothing, store environment, and camera composition. "
    "Cinematic photorealistic footage, stable camera, coherent full-body anatomy, natural biological motion."
)
DEFAULT_NARRATION = "Assalomu alaykum! MUHASIB POS kassa dasturi bilan do'koningiz savdosini to'liq nazorat qiling!"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini Veo, Fal yoki Replicate bilan haqiqiy inson motion videosi tayyorlash")
    parser.add_argument("image", nargs="?", help="Reference JPG/PNG rasm yo'li")
    parser.add_argument("--motion-prompt", default=DEFAULT_MOTION_PROMPT, help="Inglizcha aniq harakat tasviri")
    parser.add_argument("--speech", default=DEFAULT_NARRATION, help="Videoga qo'shiladigan o'zbekcha matn")
    parser.add_argument("--voice", default="uz-UZ-SardorNeural", help="edge-tts ovozi")
    parser.add_argument("--duration", type=int, default=5, help="AI video uzunligi (3–15 soniya)")
    parser.add_argument("--aspect-ratio", default="16:9", help="V1.5 kabi eski Fal modellari uchun")
    parser.add_argument("--provider", choices=("gemini", "fal", "replicate"), help=".env dagi provayderni vaqtincha almashtiradi")
    parser.add_argument("--model", help="Provayder modelini vaqtincha almashtiradi")
    parser.add_argument("--output", help="Tayyor MP4 yo'li; standart holatda loyiha ildiziga yoziladi")
    parser.add_argument("--check-config", action="store_true", help="Kalit va kutubxonalarni API chaqirmasdan tekshiradi")
    return parser.parse_args()


def command_path(command: str) -> str:
    path = shutil.which(command)
    if not path:
        raise RuntimeError(f"{command} topilmadi. Homebrew yoki tizim orqali o'rnating.")
    return path


def media_duration(path: Path) -> float:
    result = subprocess.run(
        [command_path("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


async def synthesize_voice(text: str, voice: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(text, voice).save(str(output))


def mix_narration(video: Path, audio: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            command_path("ffmpeg"), "-y", "-i", str(video), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
            "-shortest", "-movflags", "+faststart", str(output),
        ],
        check=True,
    )


def unique_paths(output: str | None) -> tuple[Path, Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_dir = VIDEO_DIR / "outputs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_video = raw_dir / f"ai_real_motion_{stamp}_raw.mp4"
    narration = VIDEO_DIR / "audio" / f"ai_real_motion_{stamp}.mp3"
    final = Path(output).expanduser().resolve() if output else ROOT / f"muhasib_ai_real_motion_{stamp}.mp4"
    return raw_video, narration, final


def build_full_ai_promo(
    image_path: str,
    action_prompt: str,
    uzbek_text: str,
    voice: str,
    requested_duration: int,
    aspect_ratio: str,
    provider: str | None,
    model: str | None,
    output: str | None,
) -> str:
    raw_video, audio_path, final_video = unique_paths(output)
    print("1) O'zbek Neural ovozi yaratilmoqda…", flush=True)
    asyncio.run(synthesize_voice(uzbek_text, voice, audio_path))
    narration_seconds = media_duration(audio_path)
    effective_duration = max(requested_duration, math.ceil(narration_seconds + 0.35))
    if effective_duration > 15:
        raise ValueError("Ovoz 15 soniyadan uzun. Matnni qisqartiring yoki videoni bo'laklarga ajrating.")

    print("2) Haqiqiy inson harakati AI orqali sintez qilinmoqda…", flush=True)
    generate_real_human_video(
        image_path=image_path,
        prompt=action_prompt,
        output_mp4_path=str(raw_video),
        duration=effective_duration,
        aspect_ratio=aspect_ratio,
        provider=provider,
        model=model,
    )
    video_seconds = media_duration(raw_video)
    if narration_seconds > video_seconds + 0.08:
        raise RuntimeError("AI video ovozdan qisqa chiqdi. Matnni qisqartiring yoki uzunroq duration tanlang.")

    print("3) Video va o'zbekcha ovoz birlashtirilmoqda…", flush=True)
    mix_narration(raw_video, audio_path, final_video)
    print(f"🎉 Tayyor haqiqiy AI motion video: {final_video}", flush=True)
    return str(final_video)


def main() -> None:
    args = parse_args()
    ready, message = provider_ready(args.provider)
    if args.check_config:
        print(("✅ " if ready else "❌ ") + message)
        return
    if not ready:
        raise RuntimeError(message)
    if not args.image:
        raise SystemExit("Reference rasm yo'lini kiriting. Masalan: images_real/real_1.jpg")
    build_full_ai_promo(
        image_path=args.image,
        action_prompt=args.motion_prompt,
        uzbek_text=args.speech,
        voice=args.voice,
        requested_duration=args.duration,
        aspect_ratio=args.aspect_ratio,
        provider=args.provider,
        model=args.model,
        output=args.output,
    )


if __name__ == "__main__":
    try:
        main()
    except VideoGenerationError as exc:
        print(f"❌ {exc}", flush=True)
        sys.exit(1)
    except Exception as exc:
        print(f"❌ {type(exc).__name__}: {exc}", flush=True)
        sys.exit(1)
