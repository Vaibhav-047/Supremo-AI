# Supremo — Desktop Management AI

A small, safe desktop assistant for macOS that you talk to from the terminal or GUI.

## Quick Start

```bash
# GUI mode (JARVIS-style dark window) — default
python3 main.py        # or: python3 jarvis.py

# CLI mode (terminal)
python3 main.py --cli  # or: python3 supremo.py

# Start in voice mode (requires speech packages)
python3 supremo.py --voice
```

For voice mode, install the optional speech packages:

```bash
brew install portaudio
pip3 install SpeechRecognition pyaudio
```

## Commands

| Command | Description |
|---------|-------------|
| `help` | Show all available commands |
| `time` | Tell the current time |
| `date` | Tell today's date |
| `battery` | Show battery status |
| `screenshot` | Save a screenshot to Desktop |
| `open <app/url/path>` | Open an app, website, or file |
| `close <app>` | Quit an app |
| `search <query>` | Search the web |
| `find <name>` | Find files in your home folder |
| `say <text>` | Speak a phrase aloud |
| `notify <message>` | Show a macOS notification |
| `copy <text>` | Copy text to the clipboard |
| `run <command>` | Run a shell command (requires confirmation) |
| `listen` | Give one command by voice |
| `voice mode` | Keep listening until "stop listening" |
| `quit` | Exit |

## Safety

- Dangerous commands (`sudo`, `rm`, `chmod`, `chmod`, `kill`, etc.) are **blocked**.
- `run <command>` always asks for confirmation before executing.
- Voice input cannot run shell commands or nest voice sessions.
- Voice transcripts are sent to Google's Speech Recognition API (requires internet).

## Project Structure

| File | Purpose |
|------|---------|
| `supremo.py` | Core assistant — parser, router, and all desktop actions |
| `jarvis.py` | JARVIS-style GUI frontend (Tkinter, dark theme) |
| `test_supremo.py` | Unit tests for parsing, safety, and command handling |
| `main.py` | Entry point — launches GUI by default, CLI with `--cli` |
| `config.py` | Configuration — tweak app settings without editing code |
| `requirements.txt` | Python dependencies for voice mode |

## License

Open source. See the code for details.
