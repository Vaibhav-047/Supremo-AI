#!/usr/bin/env python3
"""Diagnostic script for voice input issues."""
import sys, os

print("=== Supremo Voice Input Diagnostic ===\n")

# 1. Check Python
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}\n")

# 2. Check package availability
print("=== Package Check ===")
for pkg in ["sounddevice", "numpy", "speech_recognition"]:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "unknown")
        print(f"  ✓ {pkg} {ver}")
    except ImportError as e:
        print(f"  ✗ {pkg}: NOT INSTALLED ({e})")

# 3. Check sounddevice devices
print("\n=== Audio Devices ===")
try:
    import sounddevice as sd
    devices = sd.query_devices()
    input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
    if input_devices:
        for d in input_devices:
            print(f"  ✓ Input: {d['name']} (channels={d['max_input_channels']})")
    else:
        print("  ✗ No input devices found")

    # 4. Try opening InputStream
    print("\n=== Microphone Permission Test ===")
    try:
        with sd.InputStream(samplerate=16000, channels=1, dtype="int16") as s:
            print("  ✓ InputStream opens — microphone access granted")
    except Exception as e:
        print(f"  ✗ InputStream failed: {e}")
        print(f"  → Go to System Settings > Privacy & Security > Microphone")
        print(f"  → Add Supremo (or Terminal/python3) to the allowed list")

    # 5. Test actual recording
    print("\n=== Quick Recording Test (3s) ===")
    import numpy as np
    audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="int16")
    sd.wait()
    rms = np.sqrt(np.mean(audio**2))
    print(f"  Audio RMS: {rms:.2f} (should be >0 if talking, ~0 if silent)")
    if rms > 100:
        print("  ✓ Audio detected — mic is working!")
    else:
        print("  ⚠ No audio detected — check if mic is selected as default input")
        print(f"  Default input device: {sd.query_devices(sd.default.device[0])['name']}")

except Exception as e:
    print(f"  ✗ sounddevice error: {e}")

# 6. Check speech_recognition
print("\n=== Speech Recognition Test ===")
try:
    import speech_recognition as sr
    print(f"  ✓ speech_recognition {sr.__version__}")
    print("  (Google Web API is used for transcription — requires internet)")
except Exception as e:
    print(f"  ✗ speech_recognition error: {e}")

print("\n=== Summary ===")
print("If InputStream opens and audio is detected, the app's voice input")
print("should work. Make sure to:")
print("  1. Click on the Supremo window to focus it")
print("  2. Press and hold SPACE (don't type in the input field)")
print("  3. Speak clearly, then release SPACE")
