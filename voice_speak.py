import sys
import os
import asyncio
import subprocess

# Load .env file automatically
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    try:
        with open(env_file, "r", encoding="utf-8") as f:
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

async def speak_text(text: str, voice: str = "alloy"):
    """
    Speaks text using OpenAI TTS ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer', 'sol', etc.)
    or Uzbek Neural voices ('uz-UZ-SardorNeural', 'uz-UZ-MadinaNeural').
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    output_path = "/tmp/speak_output.mp3"

    if voice.startswith("uz-UZ-"):
        import edge_tts
        print(f"Uzbek Neural TTS ({voice}) orqali ijro etilmoqda...")
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        subprocess.run(["afplay", output_path], check=True)
        print("Uzbek audio ijro etildi!")
        return

    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            print(f"ChatGPT Voice API ('{voice}') orqali ijro etilmoqda...")
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice if voice in ("alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar", "breeze", "cove", "sol", "arbor", "spruce", "vale") else "alloy",
                input=text
            )
            with open(output_path, "wb") as f:
                f.write(response.content)
            subprocess.run(["afplay", output_path], check=True)
            print("ChatGPT audio muvaffaqiyatli eshitildi!")
            return
        except Exception as e:
            print(f"OpenAI API bilan xatolik yuz berdi: {e}")
            print("Zaxira (fallback) sifatida Uzbek Edge-TTS ishlatilmoqda...")

    import edge_tts
    communicate = edge_tts.Communicate(text, "uz-UZ-SardorNeural")
    await communicate.save(output_path)
    subprocess.run(["afplay", output_path], check=True)

if __name__ == "__main__":
    requested_voice = os.environ.get("TTS_VOICE", "alloy")
    if len(sys.argv) > 1:
        input_text = " ".join(sys.argv[1:])
    else:
        input_text = "Salom! Men ChatGPT Voice Mode orqali gapirayapman."
    
    asyncio.run(speak_text(input_text, voice=requested_voice))

