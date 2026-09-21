# Supremo — Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [v3.0] — 2026-09-21

### Voice Input Fixes

- **Fix: sounddevice callback signature** — The callback function was `callback(indata, frames, status)` but sounddevice passes 4 arguments: `(indata, frames, time, status)`. The missing `time` parameter caused a `TypeError` inside the CFFI callback wrapper, which silently dropped all audio (0 chunks captured). **Fix**: Added the `time` parameter.

- **Fix: 10-second delay after PTT release** — `sd.sleep(10000)` (from `PHRASE_LIMIT`) blocked the recording thread for the full 10 seconds even after the Space key was released. The callback returned `CallbackStop`, but `sd.sleep()` doesn't check for that — it sleeps the full duration. **Fix**: Replaced with a polling loop that checks `ptt_active` every 100ms and exits immediately on release.

- **Fix: PTT blocked by input field focus** — `self.input_field.focus_set()` at line 387 gave keyboard focus to the Entry widget at startup. When the user pressed Space, it was captured by the Entry widget (inserting a space character). The PTT handler detected `isinstance(focused, tk.Entry)` and returned early, so PTT never started. **Fix**: Removed auto-focus from input field, added `root.focus_set()` in `main()`, and added a click handler on window background to restore root focus. Clicking the input field still gives it focus for typing.

### Cross-Platform Support

- **Added Linux support**: `IS_LINUX` constant and platform detection in `supremo.py`
  - Battery: `upower -i /org/freedesktop/UPower/devices/battery_BAT0`
  - Screenshot: `scrot -u` → `gnome-screenshot` fallback
  - Open app: `xdg-open`
  - Close app: `pkill -f`
  - Notifications: `notify-send`
  - Clipboard: `xclip` → `wl-copy` (Wayland) fallback

- **Linux packaging**: Added `build_linux.sh` script that creates a `.tar.gz` with `install.sh`, `run.sh`, and `Supremo.desktop` entry

### GUI Design Improvements

- **Color system**: Refined dark-mode palette inspired by Linear.app and VoltAgent design systems
  - Text: `#f7f8f8` (snow white, not pure `#ffffff`)
  - Accent: emerald (`#34d399`) — single accent color only
  - Borders: `#2d3748` whisper border (replacing harsh grays)
  - Added `TEXT_SECONDARY`, `TEXT_MUTED`, `BORDER_HOVER` constants

- **Typography**: Better hierarchy — headings, body, captions with proper sizing and weight gradations

- **Component styling**: Ghost button pattern with subtle hover states, proper accent colors for CTAs

- **Bug fix**: "SUPEREMO" → "SUPREMO" typo in header label

- **Cleanup**: Removed debug file logging from PTT methods (was added for troubleshooting, confirmed working)

- **Bug fix**: Removed duplicate status update block in `_update_voice_ui`

### New Files

- `diagnose_voice.py` — Diagnostic script for voice input issues (checks packages, mic permissions, audio capture)
- `build_linux.sh` — Linux packaging script
- `CHANGELOG.md` — This file

### GitHub Cleanup

- Deleted stale branches `branch1` and `branch2`
- Created tag `v3.0` on main branch
- Created 3 separate platform releases:
  - `v3.0-mac` — Supremo.dmg
  - `v3.0-linux` — Supremo-Linux-v3.0.tar.gz
  - `v3.0-windows` — Supremo-Windows.zip
- Added build artifacts to `.gitignore`

### Test Results
- 35/35 unit tests passing
- All platform-specific methods verified (macOS: 8 features, Windows: 8 features, Linux: 8 features)

---

## [v2.0] — Previous Release

- Initial JARVIS-style GUI with antigravity window effects
- Cross-platform desktop management (macOS + Windows)
- Skills system (calculate, note, remind)
- Voice mode with pyaudio (had architecture issues on macOS 26)

---

## Known Issues & Work In Progress

- macOS microphone permission must be granted in System Settings > Privacy & Security > Microphone
- Linux requires `libasound2-dev` and `portaudio19-dev` for voice mode
- Voice transcription uses Google Web API (requires internet connection)
- Space key requires app window focus — click window background (not input field) before pressing
