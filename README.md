# Supremo — Desktop Management AI

A small, safe desktop assistant for macOS and Windows. Talk to it from a JARVIS-style GUI or the terminal.

![Version](https://img.shields.io/badge/version-3.0-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-orange)

## Quick Start

```bash
# GUI mode (JARVIS-style dark window with antigravity effects) — default
python3 main.py        # or: python3 jarvis.py

# CLI mode (terminal)
python3 main.py --cli  # or: python3 supremo.py

# Start in voice mode (requires speech packages)
python3 supremo.py --voice
```

### Dependencies

```bash
# Core: Python 3.8+ with tkinter (usually included)

# Voice mode (optional):
#   macOS:   pip3 install sounddevice SpeechRecognition numpy
#   Windows: pip install sounddevice SpeechRecognition numpy
```

## Commands

| Command | Description |
|---------|-------------|
| `help` | Show all available commands |
| `time` | Tell the current time |
| `date` | Tell today's date |
| `battery` | Show battery/power status |
| `screenshot` | Save a screenshot to Desktop |
| `open <app/url/path>` | Open an app, website, or file |
| `close <app>` | Quit an app |
| `search <query>` | Search the web |
| `find <name>` | Find files in your home folder |
| `say <text>` | Speak a phrase aloud |
| `notify <message>` | Show a system notification |
| `copy <text>` | Copy text to the clipboard |
| `run <command>` | Run a shell command (requires confirmation) |
| `skills` | List all available skills |
| `skill <name> <args>`        | Run a custom skill |
| `chatgpt <query>`            | Ask ChatGPT (needs `OPENAI_API_KEY`) |
| `listen` | Give one command by voice |
| `voice mode` | Keep listening until "stop listening" |
| `quit` | Exit |

## Skills System

Supremo supports a **skills system** — custom commands that extend the assistant. Two example skills ship built-in:

| Skill | Usage | Description |
|-------|-------|-------------|
| `calculate` | `skill calculate 2 + 2` | Safely evaluate math expressions |
| `note` | `skill note buy groceries` | Save notes to your Desktop |
| `remind` | `skill remind <task>` | Set a reminder |
| `chatgpt` | `skill chatgpt <question>` | Ask ChatGPT (needs `OPENAI_API_KEY`) |

To add your own skill, use `register_skill()`:

```python
from supremo import Supremo

assistant = Supremo()
assistant.register_skill("weather", "Get weather for a city",
    lambda city: f"Weather for {city}: 72°F and sunny")
```

## GUI Features (JARVIS Mode)

- **Antigravity window**: Transparent, always-on-top, borderless, fade-in animation
- **Auto voice mode**: Starts listening on launch
- **Voice visualization**: Animated bars in the header
- **Skills sidebar**: Shows all registered skills in a collapsible panel
- **Chat interface**: Message bubbles with avatars, timestamps, and colors
- **Hover effects**: Buttons pulse and change color on hover
- **Drag-to-move**: Click+drag anywhere on the header to move the window

## Cross-Platform Support

| Feature | macOS | Windows |
|---------|-------|---------|
| App launcher | `open -a` | `os.startfile()` |
| Close app | `osascript` | `taskkill` |
| TTS | `say` | PowerShell SpeechSynthesis |
| Screenshot | `screencapture` | PowerShell Graphics |
| Notifications | `osascript` | WScript.Shell |
| Clipboard | `pbcopy` | `clip` |
| File search | `mdfind` | `pathlib.rglob()` |

## Safety

- Dangerous commands (`sudo`, `rm`, `chmod`, `kill`, `eval`, etc.) are **blocked**.
- `run <command>` always asks for confirmation before executing.
- Voice input cannot run shell commands or nest voice sessions.
- Voice transcripts are sent to Google's Speech Recognition API (requires internet).

## Project Structure

| File | Purpose |
|------|---------|
| `supremo.py` | Core assistant — parser, router, desktop actions, skills |
| `jarvis.py` | JARVIS-style GUI frontend (Tkinter, dark theme, animations) |
| `test_supremo.py` | Unit tests for parsing, safety, and command handling |
| `main.py` | Entry point — launches GUI by default, CLI with `--cli` |
| `config.py` | Configuration — tweak app settings without editing code |
| `launcher.sh` | .app bundle launcher shell script |
| `requirements.txt` | Python dependencies for voice mode |

## Testing

```bash
python3 test_supremo.py -v
```

## License

Open source. See the code for details.