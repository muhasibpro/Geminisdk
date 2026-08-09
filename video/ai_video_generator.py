#!/usr/bin/env python3
"""Server-side clients for genuine image-to-video generation providers."""
from __future__ import annotations

import os
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAL_MODEL = "fal-ai/kling-video/v3/pro/image-to-video"
DEFAULT_GEMINI_MODEL = "veo-3.1-generate-preview"
DEFAULT_GEMINI_RESOLUTION = "720p"
ProgressCallback = Callable[[str], None]


class VideoGenerationError(RuntimeError):
    """Raised when a provider cannot produce a usable local video."""


class VideoConfigurationError(VideoGenerationError):
    """Raised when a required provider setting is missing."""


def _load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise VideoConfigurationError(
            "python-dotenv o'rnatilmagan. `uv pip install --python .venv/bin/python "
            "fal-client replicate google-genai python-dotenv` buyrug'ini ishlating."
        ) from exc
    load_dotenv(ROOT / ".env", override=False)


def _emit(progress: ProgressCallback | None, message: str) -> None:
    print(message, flush=True)
    if progress:
        progress(message)


def _require_file(image_path: str | os.PathLike[str]) -> Path:
    source = Path(image_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Rasm topilmadi: {source}")
    if source.stat().st_size == 0:
        raise VideoGenerationError(f"Rasm bo'sh: {source}")
    return source


def _require_duration(duration: int) -> int:
    try:
        value = int(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError("Video davomiyligi son bo'lishi kerak.") from exc
    if value < 3 or value > 15:
        raise ValueError("Kling V3 uchun davomiylik 3–15 soniya bo'lishi kerak.")
    return value


def _prepare_destination(output_mp4_path: str | os.PathLike[str]) -> Path:
    destination = Path(output_mp4_path).expanduser().resolve()
    if destination.suffix.lower() != ".mp4":
        raise ValueError("Natija yo'li .mp4 bilan tugashi kerak.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _selected_provider(provider: str | None = None) -> str:
    return (provider or os.environ.get("AI_VIDEO_PROVIDER", "gemini")).strip().lower()


def provider_label(provider: str | None = None) -> str:
    return {
        "gemini": "Gemini Veo",
        "fal": "Fal AI",
        "replicate": "Replicate",
    }.get(_selected_provider(provider), "AI video provayderi")


def provider_setup_hint(provider: str | None = None) -> str:
    selected = _selected_provider(provider)
    env_path = ROOT / ".env"
    if selected == "gemini":
        return (
            f"`{env_path}` ichiga Google AI Studio'dan olingan GEMINI_API_KEY yozing. "
            "8777 ichidagi Google login API kaliti o'rnini bosa olmaydi."
        )
    if selected == "fal":
        return f"`{env_path}` ichiga FAL_KEY yozing."
    if selected == "replicate":
        return f"`{env_path}` ichiga REPLICATE_API_TOKEN va AI_VIDEO_REPLICATE_MODEL yozing."
    return f"`{env_path}` ichida AI_VIDEO_PROVIDER ni gemini, fal yoki replicate qiling."


def _download_video(url: str, destination: Path) -> Path:
    if not url.startswith(("https://", "http://")):
        raise VideoGenerationError("Provayder video uchun yaroqsiz URL qaytardi.")
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Muhasib-AI-Video/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size == 0:
            raise VideoGenerationError("Provayder bo'sh video fayl qaytardi.")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def _extract_fal_video_url(result: Mapping[str, Any]) -> str:
    data: Any = result.get("data", result)
    if isinstance(data, Mapping):
        video = data.get("video")
        if isinstance(video, Mapping) and isinstance(video.get("url"), str):
            return video["url"]
        for key in ("video_url", "output_url"):
            if isinstance(data.get(key), str):
                return data[key]
    raise VideoGenerationError("Fal AI javobida video URL topilmadi.")


def _fal_arguments(model: str, image_url: str, prompt: str, duration: int, aspect_ratio: str) -> dict[str, Any]:
    if "/v3/" in model:
        return {
            "start_image_url": image_url,
            "prompt": prompt,
            "duration": str(duration),
            "generate_audio": False,
            "negative_prompt": "jerky motion, frozen face, warped limbs, flicker, blur, distorted hands, text overlay",
        }
    if "v1.5" in model and duration not in (5, 10):
        raise ValueError("Kling V1.5 uchun davomiylik faqat 5 yoki 10 soniya bo'lishi kerak.")
    return {
        "image_url": image_url,
        "prompt": prompt,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
        "negative_prompt": "jerky motion, frozen face, warped limbs, flicker, blur, distorted hands, text overlay",
    }


def _generate_with_fal(
    source: Path,
    prompt: str,
    destination: Path,
    duration: int,
    aspect_ratio: str,
    model: str,
    progress: ProgressCallback | None,
) -> Path:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        raise VideoConfigurationError("FAL_KEY topilmadi. Loyihaning .env fayliga Fal API kalitingizni yozing.")
    try:
        import fal_client
    except ImportError as exc:
        raise VideoConfigurationError("fal-client o'rnatilmagan. Kerakli kutubxonalarni o'rnating.") from exc

    _emit(progress, "🎬 Fal AI ga reference rasm yuklanmoqda…")
    image_url = fal_client.upload_file(str(source))
    arguments = _fal_arguments(model, image_url, prompt, duration, aspect_ratio)

    def on_queue_update(update: Any) -> None:
        status = getattr(update, "status", "")
        logs = getattr(update, "logs", []) or []
        if status or logs:
            messages = []
            for log in logs:
                if isinstance(log, Mapping) and log.get("message"):
                    messages.append(str(log["message"]))
            suffix = ": " + " | ".join(messages[-2:]) if messages else ""
            _emit(progress, f"🎞️ Fal AI jarayoni {status or 'davom etmoqda'}{suffix}")

    _emit(progress, f"🎞️ Fal AI ({model}) haqiqiy inson harakatini sintez qilmoqda…")
    result = fal_client.subscribe(
        model,
        arguments=arguments,
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    video_url = _extract_fal_video_url(result)
    _emit(progress, "📥 Yangi AI video mahalliy diskka saqlanmoqda…")
    return _download_video(video_url, destination)


def _first_replicate_output(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        if not value:
            raise VideoGenerationError("Replicate bo'sh natija qaytardi.")
        return value[0]
    return value


def _save_replicate_output(value: Any, destination: Path) -> Path:
    output = _first_replicate_output(value)
    if hasattr(output, "read"):
        content = output.read()
        with destination.open("wb") as file:
            file.write(content)
        if destination.stat().st_size == 0:
            raise VideoGenerationError("Replicate bo'sh video fayl qaytardi.")
        return destination
    url = getattr(output, "url", output)
    if not isinstance(url, str):
        raise VideoGenerationError("Replicate javobida video fayl topilmadi.")
    return _download_video(url, destination)


def _generate_with_replicate(
    source: Path,
    prompt: str,
    destination: Path,
    duration: int,
    model: str,
    progress: ProgressCallback | None,
) -> Path:
    if not os.environ.get("REPLICATE_API_TOKEN", "").strip():
        raise VideoConfigurationError("REPLICATE_API_TOKEN topilmadi. Uni .env fayliga yozing.")
    if not model:
        raise VideoConfigurationError("AI_VIDEO_REPLICATE_MODEL .env ichida ko'rsatilmagan.")
    try:
        import replicate
    except ImportError as exc:
        raise VideoConfigurationError("replicate o'rnatilmagan. Kerakli kutubxonalarni o'rnating.") from exc

    image_field = os.environ.get("AI_VIDEO_REPLICATE_IMAGE_FIELD", "input_image").strip() or "input_image"
    prompt_field = os.environ.get("AI_VIDEO_REPLICATE_PROMPT_FIELD", "prompt").strip()
    duration_field = os.environ.get("AI_VIDEO_REPLICATE_DURATION_FIELD", "").strip()
    inputs: dict[str, Any] = {}
    with source.open("rb") as image_file:
        inputs[image_field] = image_file
        if prompt_field:
            inputs[prompt_field] = prompt
        if duration_field:
            inputs[duration_field] = duration
        _emit(progress, f"🎞️ Replicate ({model}) haqiqiy inson harakatini sintez qilmoqda…")
        result = replicate.run(model, input=inputs)
    _emit(progress, "📥 Yangi AI video mahalliy diskka saqlanmoqda…")
    return _save_replicate_output(result, destination)


def _gemini_operation_error(operation: Any) -> str:
    error = getattr(operation, "error", None)
    if not error:
        return ""
    message = getattr(error, "message", None)
    code = getattr(error, "code", None)
    if message and code:
        return f"{code}: {message}"
    return str(message or error)


def _gemini_api_error(exc: Exception) -> VideoGenerationError:
    detail = str(exc)
    normalized = detail.upper()
    if "RESOURCE_EXHAUSTED" in normalized or "429" in normalized or "QUOTA" in normalized:
        return VideoGenerationError(
            "Gemini Veo quota tugagan yoki bu API project uchun billing yoqilmagan. "
            "Google AI Studio → Billing ichida shu API project uchun kredit/billing va Veo ruxsatini tekshiring."
        )
    if "PERMISSION_DENIED" in normalized or "403" in normalized:
        return VideoGenerationError(
            "Bu Gemini API kalitida Veo modeliga ruxsat yo'q. Google AI Studio'da API key project va billing holatini tekshiring."
        )
    concise = " ".join(detail.split())
    return VideoGenerationError("Gemini Veo so'rovini boshlab bo'lmadi: " + concise[:500])


def _generate_with_gemini(
    source: Path,
    prompt: str,
    destination: Path,
    aspect_ratio: str,
    model: str,
    progress: ProgressCallback | None,
) -> Path:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise VideoConfigurationError("GEMINI_API_KEY topilmadi. Uni .env fayliga yozing.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise VideoConfigurationError(
            "google-genai o'rnatilmagan. `uv pip install --python .venv/bin/python google-genai` ni ishlating."
        ) from exc

    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(source.suffix.lower(), "image/jpeg")
    resolution = os.environ.get("AI_VIDEO_GEMINI_RESOLUTION", DEFAULT_GEMINI_RESOLUTION).strip() or DEFAULT_GEMINI_RESOLUTION
    timeout_seconds = int(os.environ.get("AI_VIDEO_GEMINI_TIMEOUT", "900"))
    poll_seconds = max(2, int(os.environ.get("AI_VIDEO_GEMINI_POLL_SECONDS", "10")))
    client = genai.Client(api_key=api_key)
    image = types.Image.from_file(location=str(source), mime_type=mime_type)
    config = types.GenerateVideosConfig(
        number_of_videos=1,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        person_generation="allow_adult",
        negative_prompt="frozen face, warped limbs, distorted hands, flicker, blur, text overlay, cartoon, 2D animation",
    )

    _emit(progress, f"🎞️ Gemini Veo ({model}) haqiqiy inson harakatini sintez qilmoqda…")
    try:
        operation = client.models.generate_videos(
            model=model,
            source=types.GenerateVideosSource(prompt=prompt, image=image),
            config=config,
        )
        deadline = time.monotonic() + max(60, timeout_seconds)
        while not operation.done:
            if time.monotonic() >= deadline:
                raise VideoGenerationError("Gemini Veo video yaratishni belgilangan vaqtda tugatmadi.")
            _emit(progress, "⏳ Gemini Veo video kadrlarini yaratmoqda…")
            time.sleep(poll_seconds)
            operation = client.operations.get(operation=operation)

        error = _gemini_operation_error(operation)
        if error:
            raise _gemini_api_error(RuntimeError(error))
        result = getattr(operation, "result", None) or getattr(operation, "response", None)
        videos = getattr(result, "generated_videos", None) if result else None
        if not videos or not getattr(videos[0], "video", None):
            raise VideoGenerationError("Gemini Veo tayyor video fayl qaytarmadi.")

        _emit(progress, "📥 Gemini Veo videosi mahalliy diskka saqlanmoqda…")
        content = client.files.download(file=videos[0].video)
        if not isinstance(content, bytes) or not content:
            raise VideoGenerationError("Gemini Veo bo'sh video fayl qaytardi.")
        with destination.open("wb") as output:
            output.write(content)
    except VideoGenerationError:
        raise
    except Exception as exc:
        raise _gemini_api_error(exc) from exc
    return destination


def generate_real_human_video(
    image_path: str,
    prompt: str,
    output_mp4_path: str,
    duration: int = 5,
    aspect_ratio: str = "16:9",
    provider: str | None = None,
    model: str | None = None,
    progress: ProgressCallback | None = None,
) -> str:
    """Generate a new photorealistic MP4 from one reference image."""
    _load_environment()
    source = _require_file(image_path)
    destination = _prepare_destination(output_mp4_path)
    text = (prompt or "").strip()
    if not text:
        raise ValueError("Harakat prompti bo'sh bo'lishi mumkin emas.")
    seconds = _require_duration(duration)
    selected_provider = _selected_provider(provider)

    if selected_provider == "gemini":
        selected_model = model or os.environ.get("AI_VIDEO_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        output = _generate_with_gemini(source, text, destination, aspect_ratio, selected_model, progress)
    elif selected_provider == "fal":
        selected_model = model or os.environ.get("AI_VIDEO_FAL_MODEL", DEFAULT_FAL_MODEL)
        output = _generate_with_fal(source, text, destination, seconds, aspect_ratio, selected_model, progress)
    elif selected_provider == "replicate":
        selected_model = model or os.environ.get("AI_VIDEO_REPLICATE_MODEL", "")
        output = _generate_with_replicate(source, text, destination, seconds, selected_model, progress)
    else:
        raise VideoConfigurationError("AI_VIDEO_PROVIDER faqat gemini, fal yoki replicate bo'lishi mumkin.")

    _emit(progress, f"✅ Haqiqiy AI motion video tayyor: {output}")
    return str(output)


def provider_ready(provider: str | None = None) -> tuple[bool, str]:
    """Check local credentials and package availability without an API request."""
    try:
        _load_environment()
        selected = _selected_provider(provider)
        if selected == "gemini":
            if not os.environ.get("GEMINI_API_KEY", "").strip():
                return False, "GEMINI_API_KEY .env faylida yo'q"
            if not shutil.which("ffmpeg"):
                return False, "ffmpeg topilmadi"
            try:
                from google import genai
                _ = genai
            except ImportError:
                return False, "google-genai o'rnatilmagan"
            return True, "Gemini Veo tayyor"
        if selected == "fal":
            if not os.environ.get("FAL_KEY", "").strip():
                return False, "FAL_KEY .env faylida yo'q"
            if not shutil.which("ffmpeg"):
                return False, "ffmpeg topilmadi"
            import fal_client
            _ = fal_client
            return True, "Fal AI tayyor"
        if selected == "replicate":
            if not os.environ.get("REPLICATE_API_TOKEN", "").strip():
                return False, "REPLICATE_API_TOKEN .env faylida yo'q"
            if not os.environ.get("AI_VIDEO_REPLICATE_MODEL", "").strip():
                return False, "AI_VIDEO_REPLICATE_MODEL .env faylida yo'q"
            import replicate
            _ = replicate
            return True, "Replicate tayyor"
        return False, "AI_VIDEO_PROVIDER gemini, fal yoki replicate emas"
    except VideoConfigurationError as exc:
        return False, str(exc)
