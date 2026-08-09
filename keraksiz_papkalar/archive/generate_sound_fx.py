import wave
import math
import struct
import os

DIR = "/Users/muhasibpro/Desktop/Geminisdk/audio"
os.makedirs(DIR, exist_ok=True)

def create_sine_wave(filename, freq, duration, sample_rate=44100, fade=True):
    num_samples = int(duration * sample_rate)
    with wave.open(filename, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(num_samples):
            t = i / sample_rate
            val = math.sin(2 * math.pi * freq * t)
            if fade:
                env = math.exp(-4 * t / duration)
                val *= env
            sample = int(val * 32767 * 0.5)
            wav.writeframesraw(struct.pack('<h', max(-32768, min(32767, sample))))

# 1. Bell chime
create_sine_wave(os.path.join(DIR, "bell.wav"), 1046.5, 1.2) # High C bell

# 2. Scanner Beep
create_sine_wave(os.path.join(DIR, "beep.wav"), 2400.0, 0.2, fade=False)

# 3. Cash register click
create_sine_wave(os.path.join(DIR, "cash.wav"), 440.0, 0.4)

# 4. Shock sound
create_sine_wave(os.path.join(DIR, "shock.wav"), 650.0, 0.6)

print("Generated sound FX in audio/")
