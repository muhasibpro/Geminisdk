#!/usr/bin/python3
import asyncio
import os
import edge_tts

DIR = "/Users/muhasibpro/Desktop/Geminisdk"

lines = [
    {
        "text": "Quvnoq bola do'konga kiradi, javondan yaxshilab energetik ichimlik tanlab oladi va kassa taraqqat boradi.",
        "voice": "uz-UZ-MadinaNeural",
        "file": os.path.join(DIR, "real_s1.mp3")
    },
    {
        "text": "Uka, energetik ichimligingiz hammasi bo'lib 25,000 so'm bo'ldi.",
        "voice": "uz-UZ-MadinaNeural",
        "file": os.path.join(DIR, "real_s2.mp3")
    },
    {
        "text": "Vay! Nega sizlarda Muhasib dasturi yo'q?! Muhasib bo'lsa tezroq va qulayroq bo'lardi-ku!",
        "voice": "uz-UZ-SardorNeural",
        "file": os.path.join(DIR, "real_s3.mp3")
    },
    {
        "text": "Muhasib dasturi o'rnatildi! Endi 1 soniyada skanerlash, aniq hisob-kitob va zamonaviy POS kassa!",
        "voice": "uz-UZ-SardorNeural",
        "file": os.path.join(DIR, "real_s4.mp3")
    }
]

async def main():
    for item in lines:
        print(f"Synthesizing [{item['voice']}]: {item['text']}")
        communicate = edge_tts.Communicate(item["text"], item["voice"])
        await communicate.save(item["file"])
        print(f"Saved: {item['file']}")

if __name__ == "__main__":
    asyncio.run(main())
