# Supremo — Running Logs & Debug Reference

This file serves as a living log of all error states, diagnostic commands, and
verification steps used during Supremo v3.0 development. Keep it alongside the code.

---

## Voice Input Debugging Commands

```bash
# 1. Check which Python the app uses at runtime
ps aux | grep -i "main.py" | grep -v grep

# 2. Verify all required packages are installed
/usr/local/bin/python3 -c "import sounddevice, speech_recognition, numpy; print('All OK')"

# 3. Test sounddevice callback directly
/usr/local/bin/python3 -c "
import sounddevice as sd
import numpy as np

chunks = []
recording = [True]

def callback(indata, frames, time, status):  # NOTE: 4 params, not 3
    if not recording[0]:
        return sd.CallbackStop
    chunks.append(indata.tobytes())

with sd.InputStream(samplerate=16000, channels=1, dtype='int16', callback=callback) as s:
    sd.sleep(2000)  # Hold for 2 seconds

print(f'Chunks captured: {len(chunks)}')
print(f'Total bytes: {sum(len(c) for c in chunks)}')
if chunks:
    audio = b''.join(chunks)
    rms = np.sqrt(np.mean(np.frombuffer(audio, dtype=np.int16)**2))
    print(f'RMS level: {rms:.2f}')
"

# 4. Test full listen_once flow
/usr/local/bin/python3 -c "
import sys
sys.path.insert(0, '.')
from supremo import Supremo, VoiceUnavailable
a = Supremo()
try:
    t = a.listen_once(quiet=False)
    print(f'Transcript: {repr(t)}')
except VoiceUnavailable as e:
    print(f'VoiceUnavailable: {e}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
"

# 5. Check microphone permissions
/usr/local/bin/python3 -c "
import sounddevice as sd
devices = sd.query_devices()
for d in devices:
    if d.get('max_input_channels', 0) > 0:
        print(f'Input device: {d[\"name\"]} (channels={d[\"max_input_channels\"]})')
try:
    with sd.InputStream(samplerate=16000, channels=1, dtype='int16'):
        print('InputStream opens: OK — mic access granted')
except Exception as e:
    print(f'InputStream error: {e}')
    print('→ Grant microphone access in System Settings > Privacy & Security > Microphone')
"

# 6. Run the diagnostic script
python3 diagnose_voice.py
```

---

## Error Log

### Error 1: sounddevice Callback TypeError
```
Exception ignored from cffi callback <function _StreamBase.__init__.<locals>.callback_ptr at 0x...>:
Traceback (most recent call last):
  File ".../sounddevice.py", line 863, in callback_ptr
    return _wrap_callback(c
TypeError: callback() takes 3 positional arguments but 4 were given
```
**Cause**: Callback signature was `callback(indata, frames, status)` — missing `time` parameter.
**Fix**: `callback(indata, frames, time, status)`
**Diagnosis command**: Tested callback in isolation with `/usr/local/bin/python3 -c "..."`

---

### Error 2: macOS 26 Python Crash
```
python3: Task stopped due to signal: 11
macOS 26 (2603) or later required, have instead 16 (1603)
```
**Cause**: System Python 3.9 used in the DMG launcher instead of `/usr/local/bin/python3` (3.14).
**Fix**: Updated `launcher.sh` to prefer `/usr/local/bin/python3` (3.14).

---

### Error 3: App "just runs then closes"
```
# App launches and immediately exits
# No error message, exit code 0
```
**Cause**: The `Contents/MacOS/Supremo` launcher script was using the wrong Python interpreter
or the launcher.sh inside the DMG bundle still referenced pyaudio checks.
**Fix**: Updated launcher to check `sounddevice, numpy, speech_recognition` instead of `pyaudio, speech_recognition`.
**Also fixed**: Copied updated `launcher.sh` to both `Contents/MacOS/Supremo` and `Contents/Resources/launcher.sh`.

---

### Error 4: PTT Not Triggering (Input Field Focus)
```
Debug log:
PTT_PRESS: focused=Entry, voice_enabled=True, ptt_active=False
PTT_PRESS: skipped (input field focused)
```
**Cause**: `self.input_field.focus_set()` at line 387 gave keyboard focus to the Entry widget
at startup. Space key went to typing a space character instead of triggering PTT.
**Fix**: Removed `focus_set()`, added `root.focus_set()` in `main()`, added click-to-focus
on window background.

---

### Error 5: 10-Second Delay After PTT Release
```
# User releases Space → no response for 10 seconds
# Then transcription happens all at once
```
**Cause**: `sd.sleep(int(self.assistant.PHRASE_LIMIT * 1000))` blocked the recording thread
for the full 10 seconds. `CallbackStop` from the callback does NOT interrupt `sd.sleep()`.
**Fix**: Polling loop: `while self.ptt_active and (time.time() - start_time) < PHRASE_LIMIT: sd.sleep(100)`

---

### Error 6: Patch Indentation Error (development only, not released)
```
SyntaxError: expected 'except' or 'finally' block (line 581, column 9)
```
**Cause**: During patching, the `while` loop ended up outside the `with` block due to
incorrect indentation in the patch replacement text.
**Fix**: Ensured `while` loop is inside the `with sd.InputStream(...) as stream:` context.

---

### Error 7: Unbound Variable in Clipboard (Linux, development only)
```
ERROR: "cb_cmd" is possibly unbound
ERROR: No overloads for "run" match the provided arguments
```
**Cause**: When adding Linux clipboard support, the `cb_cmd = None` path fell through to
`subprocess.run(cb_cmd, ...)` with `cb_cmd = None`.
**Fix**: Restructured to return early after successful clipboard write on Linux.

---

### Error 8: Duplicate Lines in Callback (development only)
```
IndentationError: unexpected indent (line 581, column 16)
```
**Cause**: When removing debug logging from the callback, the patch created duplicate
lines for the callback body.
**Fix**: Manually removed duplicate lines 581-585.

---

## Git Commands Reference

```bash
# Push a new tag
git tag -a v3.0 -m "Supremo v3.0 — Cross-platform desktop management AI"
git push origin v3.0

# Delete a remote branch
git push origin --delete branch_name

# Delete and recreate a release asset
gh release upload v3.0-windows ./Supremo-Windows.zip --clobber --repo Vaibhav-047/Supremo-AI

# List release assets
gh release view v3.0-windows --json assets --repo Vaibhav-047/Supremo-AI

# Delete a release asset by ID
gh api --method DELETE "/repos/Vaibhav-047/Supremo-AI/releases/assets/{asset_id}"
```

---

## macOS TCC (Permissions) Debugging

```bash
# Check microphone permissions (requires Full Disk Access)
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  "SELECT client, service, auth_value FROM access WHERE service='kTCCServiceMicrophone' ORDER BY client;"

# Reset microphone permissions for an app
tccutil reset Microphone com.supremo.desktop

# Reset all permissions
tccutil reset All

# Check app Info.plist for usage descriptions
plutil -p /path/to/Supremo.app/Contents/Info.plist
```

---

## Process Management

```bash
# Check if app is running
pgrep -f "main.py" 

# Kill app
pkill -f Supremo

# Check process details
ps -p $(pgrep -f "main.py") -o pid,command

# Build DMG
hdiutil create -volname "Supremo" -srcfolder /path/to/Supremo.app -ov -format UDZO ~/Downloads/Supremo.dmg

# Build Windows ZIP
zip -r -X Supremo-Windows.zip *.py *.bat

# Build Linux package
./build_linux.sh
```
