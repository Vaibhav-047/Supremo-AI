"""Supremo: a small, safe desktop assistant for macOS and Windows.

Run with:
    python3 supremo.py              (CLI mode, type commands)
    python3 supremo.py --voice      (CLI mode, start in voice mode)
    python3 main.py                 (GUI mode, JARVIS-style)

Voice input is optional. To enable it:
    macOS:   pip3 install sounddevice SpeechRecognition
    Windows: pip install sounddevice SpeechRecognition

Skills:
    register_skill("name", "description", handler)  # add a custom skill
    skill <name> <args>                               # invoke it
    Type 'skills' to list all registered skills.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import operator
import os
import platform
import re
import shlex
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus


IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"


@dataclass(frozen=True)
class Intent:
    action: str
    value: str = ""


@dataclass
class Skill:
    """A plugin skill that extends Supremo with custom commands."""
    name: str
    description: str
    handler: callable  # (value: str) -> str | None


class VoiceUnavailable(Exception):
    """Raised when voice input can't be used (missing package, no microphone)."""


def _safe_math(args: str) -> str:
    """Evaluate a math expression safely (no eval)."""
    _ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return _ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            return _ops[type(node.op)](_eval(node.operand))
        raise ValueError(f"Unsupported expression element: {node}")

    try:
        tree = ast.parse(args, mode="eval")
        return f"Result: {_eval(tree.body)}"
    except Exception as exc:
        return f"Error: {exc}"


class Supremo:
    """Command router and desktop action layer for Supremo."""

    APP_ALIASES = {
        "browser": "Safari",
        "safari": "Safari",
        "chrome": "Google Chrome",
        "edge": "Microsoft Edge",
        "firefox": "Firefox",
        "finder": "Finder",
        "explorer": "explorer",
        "terminal": "Terminal",
        "cmd": "cmd",
        "powershell": "PowerShell",
        "notes": "Notes",
        "notepad": "Notepad",
        "calendar": "Calendar",
        "mail": "Mail",
        "music": "Music",
        "code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "preview": "Preview",
        "settings": "System Settings",
        "control": "System Settings",
        "calc": "Calculator",
        "calculator": "Calculator",
        "messages": "Messages",
    }
    BLOCKED_COMMANDS = {
        "sudo", "su", "shutdown", "reboot", "halt", "mkfs", "diskutil",
        "launchctl", "kill", "killall", "crontab", "dscl", "rm", "dd",
        "chmod", "chown", "mv", "eval", "exec",
    }
    POLITE_PREFIXES = ("please ", "can you ", "could you ", "would you ")
    POLITE_SUFFIXES = (" please",)
    VOICE_BLOCKED_ACTIONS = {"run", "listen", "voice_mode"}
    LISTEN_TIMEOUT = 6
    PHRASE_LIMIT = 10

    # ------------------------------------------------------------------
    # Skill system
    # ------------------------------------------------------------------
    def __init__(self):
        self.skills: dict[str, Skill] = {}
        self._register_default_skills()

    def _register_default_skills(self):
        """Register a few useful built-in skills as examples."""
        self.register_skill(
            "calculate", "Evaluate a math expression",
            lambda value: _safe_math(value) if value else "Usage: skill calculate <expression>",
        )

        def _note(value: str) -> str:
            if not value:
                return "Usage: skill note <text>"
            path = Path.home() / "Desktop" / "supremo-notes.txt"
            with open(path, "a") as fh:
                fh.write(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {value}\n")
            return f"Saved note to {path}"

        self.register_skill("note", "Save a note to your Desktop", _note)

        def _remind(value: str) -> str:
            if not value:
                return "Usage: skill remind <task> in <N> minutes"
            return f"Reminder set: '{value}'. (Desktop integration coming soon.)"

        self.register_skill("remind", "Set a reminder", _remind)

        def _chatgpt(value: str) -> str:
            if not value:
                return "Usage: chatgpt <question>"
            return Supremo._chatgpt_request(value)

        self.register_skill("chatgpt", "Ask ChatGPT a question (needs OPENAI_API_KEY)", _chatgpt)

    def register_skill(self, name: str, description: str, handler: callable) -> None:
        """Register a custom skill.

        Example::
            assistant.register_skill("weather", "Get weather for a city",
                                      lambda city: fetch_weather(city))
        """
        self.skills[name.lower()] = Skill(name.lower(), description, handler)

    def unregister_skill(self, name: str) -> None:
        """Remove a previously registered skill."""
        self.skills.pop(name.lower(), None)

    def list_skills(self) -> list[tuple[str, str]]:
        """Return a list of (name, description) for all registered skills."""
        return [(s.name, s.description) for s in self.skills.values()]

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse(self, request: str) -> Intent:
        text = self._normalize(request)
        if not text:
            return Intent("empty")
        normalized = text.lower()

        # --- Built-in commands ---
        if normalized in {"help", "?", "commands"}:
            return Intent("help")
        if normalized in {"quit", "exit", "bye"}:
            return Intent("quit")
        if normalized in {"time", "what time is it", "what's the time", "current time"}:
            return Intent("time")
        if normalized in {"date", "today", "what is the date", "what's the date"}:
            return Intent("date")
        if normalized in {"battery", "battery status", "power"}:
            return Intent("battery")
        if normalized in {"screenshot", "take a screenshot", "capture screen"}:
            return Intent("screenshot")
        if normalized in {"listen", "voice", "voice command", "listen to me"}:
            return Intent("listen")
        if normalized in {"voice mode", "voice on", "start listening"}:
            return Intent("voice_mode")
        if normalized in {"stop listening", "voice off"}:
            return Intent("stop_listening")
        if normalized in {"close", "terminate"}:
            return Intent("close")
        if normalized in {"skills", "list skills", "show skills"}:
            return Intent("skills")
        for prefix in ("open ", "launch ", "start "):
            if normalized.startswith(prefix):
                return Intent("open", text[len(prefix):])
        for prefix in ("close ", "terminate "):
            if normalized.startswith(prefix):
                return Intent("close", text[len(prefix):])
        # ChatGPT queries — must come before "search" handler to avoid collision
        if normalized.startswith("chatgpt "):
            return Intent("chatgpt", text[8:])
        if normalized.startswith("ask chatgpt about "):
            return Intent("chatgpt", text[18:])
        if normalized.startswith("ask chatgpt "):
            return Intent("chatgpt", text[12:])
        for prefix in ("search ", "google ", "look up "):
            if normalized.startswith(prefix) and normalized.endswith(" on chatgpt"):
                return Intent("chatgpt", text[len(prefix):-11])
        if normalized.startswith("search chatgpt for "):
            return Intent("chatgpt", text[19:])
        for prefix in ("search ", "google ", "look up "):
            if normalized.startswith(prefix):
                return Intent("search", text[len(prefix):])
        for prefix in ("find ", "locate "):
            if normalized.startswith(prefix):
                return Intent("find", text[len(prefix):])
        for prefix in ("say ", "speak "):
            if normalized.startswith(prefix):
                return Intent("say", text[len(prefix):])
        for prefix in ("notify ", "remind me "):
            if normalized.startswith(prefix):
                return Intent("notify", text[len(prefix):])
        for prefix in ("copy ", "clipboard "):
            if normalized.startswith(prefix):
                return Intent("copy", text[len(prefix):])
        if normalized.startswith("run "):
            return Intent("run", text[4:])
        if normalized.startswith("skill "):
            return Intent("skill", text[6:])
        return Intent("unknown", text)

    def handle(self, intent: Intent, from_voice: bool = False) -> bool:
        actions = {
            "help": self.show_help,
            "time": self.show_time,
            "date": self.show_date,
            "battery": self.show_battery,
            "screenshot": self.take_screenshot,
            "open": self.open_target,
            "close": self.close_target,
            "search": self.search_web,
            "find": self.find_files,
            "say": self.speak,
            "notify": self.notify,
            "copy": self.copy_to_clipboard,
            "run": self.run_command,
            "chatgpt": self._handle_chatgpt,
            "skill": self.execute_skill,
            "skills": self.list_skills_handler,
            "unknown": self.explain_unknown,
            "stop_listening": lambda _value: print("Voice mode isn't on."),
            "empty": lambda _value: None,
        }
        if intent.action == "quit":
            return False
        if from_voice and intent.action in self.VOICE_BLOCKED_ACTIONS:
            print("For safety, that command is only available by typing.")
            return True
        if intent.action == "listen":
            return self.voice_once()
        if intent.action == "voice_mode":
            return self.voice_loop()
        action = actions.get(intent.action, self.explain_unknown)
        action(intent.value)
        return True

    # ------------------------------------------------------------------
    # Skill handlers
    # ------------------------------------------------------------------
    def list_skills_handler(self, _value: str = "") -> None:
        if not self.skills:
            print("No custom skills registered.")
            return
        print("Available skills:")
        for name, desc in self.list_skills():
            print(f"  skill {name} — {desc}")
        print("\nUse: skill <name> <args>")

    def execute_skill(self, value: str = "") -> None:
        parts = value.split(None, 1)
        name = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        if not name:
            print("Usage: skill <name> <args>")
            return
        skill = self.skills.get(name)
        if skill is None:
            print(f"No skill registered as {name!r}. Type 'skills' to list available skills.")
            return
        try:
            result = skill.handler(args)
            if result:
                print(result)
        except Exception as exc:
            print(f"Skill {name!r} failed: {exc}")

    # ------------------------------------------------------------------
    # Built-in action methods
    # ------------------------------------------------------------------
    def show_help(self, _value: str = "") -> None:
        print(
            """
Supremo can help with:
  open Safari                Launch an app
  open https://example.com   Open a website
  close Safari               Quit an app
  search Python dataclasses  Search the web
  find budget                Find files
  say good morning           Speak a short phrase
  notify stretch             Show a notification
  copy meeting notes         Copy text to the clipboard
  screenshot                 Save a screenshot to the Desktop
  battery                    Show battery/power status
  run pwd                    Run a command after confirmation
  skills                     List available skills
  skill <name> <args>        Run a custom skill
  chatgpt <query>            Ask ChatGPT (needs OPENAI_API_KEY)
  search <X> on chatgpt      Search ChatGPT for X
  listen                     Give one command by voice
  voice mode                 Keep listening (say "stop listening" to end)
  time / date / help / quit
"""
        )

    def show_time(self, _value: str = "") -> None:
        print(f"It is {dt.datetime.now().strftime('%I:%M %p').lstrip('0')}.")

    def show_date(self, _value: str = "") -> None:
        print(dt.date.today().strftime("Today is %A, %B %d, %Y."))

    def show_battery(self, _value: str = "") -> None:
        if IS_MAC:
            output = self._capture(["pmset", "-g", "batt"])
        elif IS_WINDOWS:
            output = self._capture([
                "powershell", "-NoProfile", "-Command",
                "(Get-WmiObject -Class Win32_Battery | "
                "Select-Object -ExpandProperty EstimatedChargeRemaining)",
            ])
        else:
            output = None
        if output is None:
            print("Could not read battery status on this platform.")
            return
        print(output.strip() or "Could not read battery status.")

    def take_screenshot(self, _value: str = "") -> None:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path.home() / "Desktop" / f"supremo-screenshot-{stamp}.png"
        if IS_MAC:
            success = self._run(["screencapture", "-x", str(path)])
        elif IS_WINDOWS:
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                "$s=[System.Windows.Forms.Screen]::AllScreens[0];"
                "$b=New-Object System.Drawing.Bitmap($s.Bounds.Width,$s.Bounds.Height);"
                "$g=[System.Drawing.Graphics]::FromImage($b);"
                "$g.CopyFromScreen($s.Bounds.X,$s.Bounds.Y,0,0,$s.Bounds.Size);"
                f'$b.Save("{path}",[System.Drawing.Imaging.ImageFormat]::Png)'
            )
            success = self._run(["powershell", "-NoProfile", "-Command", ps])
        else:
            print("Screenshots are not supported on this platform.")
            return
        if success:
            print(f"Saved screenshot to {path}")

    def open_target(self, target: str) -> None:
        target = target.strip()
        if not target:
            print("Tell me what you want to open.")
            return
        app_name = self.APP_ALIASES.get(target.lower(), target)
        path = Path(target).expanduser()
        if path.exists():
            if IS_MAC:
                self._run(["open", str(path)])
            elif IS_WINDOWS:
                try:
                    os.startfile(str(path))
                except OSError as exc:
                    print(f"Could not open {path}: {exc}")
            else:
                webbrowser.open(str(path))
            return
        if target.lower() in self.APP_ALIASES or ("://" not in target and "." not in target):
            if IS_MAC:
                self._run(["open", "-a", app_name])
            elif IS_WINDOWS:
                try:
                    os.startfile(app_name)
                except OSError as exc:
                    print(f"Could not open {app_name}: {exc}")
            else:
                print(f"Cannot launch {app_name} on this platform.")
            return
        url = target if "://" in target else f"https://{target}"
        print(f"Opening {url}")
        webbrowser.open(url)

    def close_target(self, app_name: str) -> None:
        app_name = app_name.strip()
        if not app_name:
            print("Tell me which app to close.")
            return
        name = self.APP_ALIASES.get(app_name.lower(), app_name)
        print(f"Closing {name}...")
        if IS_MAC:
            self._run(["osascript", "-e", f'tell application "{name}" to quit'])
        elif IS_WINDOWS:
            display = name if name.lower().endswith(".exe") else f"{name}.exe"
            self._run(["taskkill", "/f", "/im", display])
        else:
            print(f"Cannot close {name} on this platform.")

    def search_web(self, query: str) -> None:
        query = query.strip()
        if not query:
            print("Tell me what you want to search for.")
            return
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        print(f"Searching for: {query}")
        webbrowser.open(url)

    def find_files(self, name: str) -> None:
        name = name.strip()
        if not name:
            print("Tell me what filename or pattern to find.")
            return
        if IS_MAC:
            matches = self._spotlight_matches(name)
            if matches is None:
                matches = self._walk_home(name)
        else:
            matches = self._walk_home(name)
        if not matches:
            print(f"No files matching {name!r} found in your home folder.")
            return
        print("\n".join(str(path) for path in matches))

    def speak(self, text: str) -> None:
        text = text.strip()
        if not text:
            print("Tell me what to say.")
            return
        if IS_MAC:
            self._run(["say", text])
        elif IS_WINDOWS:
            ps = (
                "Add-Type -AssemblyName System.Speech;"
                f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;'
                f'$s.Speak("{text}")'
            )
            self._run(["powershell", "-NoProfile", "-Command", ps])
        else:
            try:
                subprocess.run(["espeak", text], check=False, timeout=10)
            except OSError:
                print(f"(text-to-speech not available: {text})")

    def notify(self, message: str) -> None:
        message = message.strip()
        if not message:
            print("Tell me what the notification should say.")
            return
        escaped = message.replace("\\", "\\\\").replace('"', '\\"')
        if IS_MAC:
            script = f'display notification "{escaped}" with title "Supremo"'
            self._run(["osascript", "-e", script])
        elif IS_WINDOWS:
            ps = (
                "$s = New-Object -ComObject WScript.Shell;"
                f'$s.Popup("{escaped}", 5, "Supremo", 0x0)'
            )
            self._run(["powershell", "-NoProfile", "-Command", ps])
        else:
            print(f"[Supremo notification]: {message}")

    def copy_to_clipboard(self, text: str) -> None:
        text = text.strip()
        if not text:
            print("Tell me what to copy.")
            return
        try:
            if IS_MAC:
                cb_cmd = ["pbcopy"]
            elif IS_WINDOWS:
                cb_cmd = ["clip"]
            else:
                cb_cmd = ["xclip", "-selection", "c"]
            subprocess.run(cb_cmd, input=text, text=True, check=True, timeout=10)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError) as error:
            print(f"Could not copy to the clipboard: {error}")
            return
        print("Copied to the clipboard.")

    @staticmethod
    def _chatgpt_request(query: str) -> str:
        """Send a query to the ChatGPT API and return the response.

        Requires OPENAI_API_KEY environment variable or a key file at
        ~/.config/supremo/openai.key
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        key_path = Path.home() / ".config" / "supremo" / "openai.key"
        if not api_key and key_path.exists():
            api_key = key_path.read_text().strip()

        if not api_key:
            return ("OPENAI_API_KEY not set. Get one at https://platform.openai.com/api-keys\n"
                    f"Save to {key_path} or set as environment variable.")

        try:
            import json
            import urllib.request
            import urllib.error

            data = json.dumps({
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 500,
                "temperature": 0.7,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            return f"ChatGPT API error: {e.code} {e.reason}"
        except urllib.error.URLError as e:
            return f"Network error: {e.reason}"
        except Exception as e:
            return f"ChatGPT request failed: {e}"

    def _handle_chatgpt(self, query: str) -> None:
        """Handle a 'chatgpt <query>' command (direct, not via skill)."""
        query = query.strip() if query else ""
        if not query:
            print("Tell me what to ask ChatGPT.")
            return
        print(f"Asking ChatGPT: {query}")
        response = self._chatgpt_request(query)
        print(response)

    def run_command(self, command: str) -> None:
        command = command.strip()
        if not command:
            print("Tell me which command to run.")
            return
        try:
            argv = shlex.split(command)
        except ValueError as error:
            print(f"Could not parse command: {error}")
            return
        if not argv:
            print("Tell me which command to run.")
            return
        if Path(argv[0]).name in self.BLOCKED_COMMANDS:
            print(f"Refusing to run {argv[0]!r}. Supremo only runs low-risk commands.")
            return
        print(f"Supremo is ready to run: {command}")
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            print("\nCancelled.")
            return
        if answer != "y":
            print("Cancelled.")
            return
        try:
            result = subprocess.run(
                argv, check=False, text=True,
                capture_output=True, timeout=30,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            print(f"Could not run command: {error}")
            return
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        print(f"Command finished with exit code {result.returncode}.")

    # ------------------------------------------------------------------
    # Voice
    # ------------------------------------------------------------------
    def voice_once(self) -> bool:
        """Listen for one spoken command. Returns False if it was 'quit'."""
        try:
            transcript = self.listen_once()
        except VoiceUnavailable as error:
            print(error)
            return True
        except KeyboardInterrupt:
            print("\nCancelled.")
            return True
        if transcript is None:
            return True
        return self.handle(self._process_transcript(transcript), from_voice=True)

    def voice_loop(self) -> bool:
        """Keep listening until 'stop listening' or Ctrl+C. Returns False on 'quit'."""
        print(
            "Voice mode on. Say 'stop listening' to go back to typing, "
            "or 'quit' to exit. Ctrl+C also stops."
        )
        while True:
            try:
                transcript = self.listen_once(quiet=True)
                if transcript is None:
                    continue
                intent = self._process_transcript(transcript)
                if intent.action == "stop_listening":
                    print("Voice mode off.")
                    return True
                if not self.handle(intent, from_voice=True):
                    return False
            except VoiceUnavailable as error:
                print(error)
                return True
            except KeyboardInterrupt:
                print("\nVoice mode off.")
                return True

    def listen_once(self, quiet: bool = False) -> str | None:
        """Record one utterance and return its transcript.

        Returns None if nothing was heard or it couldn't be understood.
        Raises VoiceUnavailable if voice input isn't set up.

        Privacy note: the audio is sent to Google's free web speech API to be
        transcribed, so it needs an internet connection.
        """
        try:
            import sounddevice as sd
            import numpy as np
            import speech_recognition as sr
        except ImportError:
            raise VoiceUnavailable(
                "Voice input needs pip packages. Install with:\n"
                "  pip install sounddevice SpeechRecognition numpy"
            ) from None

        sample_rate = 16000
        chunk_duration = 0.3  # seconds per chunk
        chunk_size = int(sample_rate * chunk_duration)
        # VAD threshold: mean absolute amplitude above this = speech
        speech_threshold = 300

        recognizer = sr.Recognizer()

        try:
            if not quiet:
                print("Listening...")

            audio_chunks: list[bytes] = []
            speech_started = False
            silence_streak = 0
            max_chunks = int(self.PHRASE_LIMIT / chunk_duration)

            with sd.InputStream(
                samplerate=sample_rate, channels=1, dtype="int16"
            ) as stream:
                # Phase 1 — wait for speech (with timeout)
                for i in range(int(self.LISTEN_TIMEOUT / chunk_duration)):
                    chunk, _ = stream.read(chunk_size)
                    audio_level = float(np.abs(chunk).mean())
                    if audio_level > speech_threshold:
                        speech_started = True
                        audio_chunks.append(chunk.tobytes())
                        break

                if not speech_started:
                    if not quiet:
                        print(
                            "I didn't hear anything. If this keeps happening, check "
                            "microphone permissions in System Settings."
                            if IS_MAC
                            else "I didn't hear anything. Check your microphone."
                        )
                    return None

                # Phase 2 — record until silence or phrase limit
                for _ in range(max_chunks - len(audio_chunks)):
                    chunk, _ = stream.read(chunk_size)
                    audio_chunks.append(chunk.tobytes())
                    audio_level = float(np.abs(chunk).mean())
                    if audio_level < speech_threshold:
                        silence_streak += 1
                        if silence_streak > 3:
                            break
                    else:
                        silence_streak = 0

        except sd.PortAudioError as error:
            raise VoiceUnavailable(f"Could not open the microphone: {error}") from None
        except OSError as error:
            raise VoiceUnavailable(f"Could not open the microphone: {error}") from None

        try:
            audio_data = sr.AudioData(
                b"".join(audio_chunks), sample_rate, 2
            )
            return recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            if not quiet:
                print("Sorry, I couldn't understand that.")
        except sr.RequestError as error:
            raise VoiceUnavailable(
                f"Speech recognition service unavailable: {error}"
            ) from None
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _process_transcript(self, transcript: str) -> Intent:
        transcript = self._clean_transcript(transcript)
        print(f"Heard: {transcript}")
        return self.parse(transcript)

    def explain_unknown(self, request: str) -> None:
        print(
            f"I do not know how to handle {request!r} yet. Type 'help' for commands."
        )

    def _normalize(self, request: str) -> str:
        text = " ".join(request.strip().split())
        text = text.rstrip("?!.,")
        lowered = text.lower()
        changed = True
        while changed:
            changed = False
            for prefix in self.POLITE_PREFIXES:
                if lowered.startswith(prefix):
                    text = text[len(prefix):].lstrip()
                    lowered = text.lower()
                    changed = True
            for suffix in self.POLITE_SUFFIXES:
                if lowered.endswith(suffix):
                    text = text[: -len(suffix)].rstrip()
                    lowered = text.lower()
                    changed = True
        return text

    @staticmethod
    def _clean_transcript(text: str) -> str:
        """Tidy speech-recognizer output so it parses like typed input."""
        text = " ".join(text.split())
        if text.lower().startswith(("open ", "launch ", "start ")):
            text = re.sub(r"\s+dot\s+", ".", text, flags=re.IGNORECASE)
        return text

    def _spotlight_matches(self, name: str) -> list[Path] | None:
        if platform.system() != "Darwin":
            return None
        query = "kMDItemDisplayName == {}c".format(self._spotlight_glob(name))
        output = self._capture(
            ["mdfind", "-onlyin", str(Path.home()), query], timeout=15,
        )
        if output is None:
            return None
        matches = []
        for line in output.splitlines():
            if line:
                matches.append(Path(line))
            if len(matches) == 20:
                break
        return matches

    @staticmethod
    def _spotlight_glob(name: str) -> str:
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'"*{escaped}*"'

    def _walk_home(self, name: str) -> list[Path]:
        matches = []
        try:
            for path in Path.home().rglob(f"*{name}*"):
                matches.append(path)
                if len(matches) == 20:
                    break
        except OSError as error:
            print(f"Could not search your home folder: {error}")
            return []
        return matches

    def _capture(self, command: list[str], timeout: int = 10) -> str | None:
        try:
            result = subprocess.run(
                command, check=False, text=True,
                capture_output=True, timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"Could not complete that action: {error}")
            return None
        if result.returncode != 0 and not result.stdout:
            print(result.stderr.rstrip() or "Could not complete that action.")
            return None
        return result.stdout.strip()

    @staticmethod
    def _run(command: list[str]) -> bool:
        try:
            subprocess.run(command, check=True, timeout=30)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            print(f"Could not complete that action: {error}")
            return False
        return True


# ------------------------------------------------------------------ #
#  Built-in skills — registered by default                           #
# ------------------------------------------------------------------ #


def _make_default_skills(assistant: Supremo) -> None:
    """Register example skills that ship with Supremo."""
    # calculate and note are registered in _register_default_skills
    # This function can be extended by users.
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Supremo desktop assistant")
    parser.add_argument("--voice", action="store_true", help="start in voice mode")
    parser.add_argument("--cli", action="store_true", help="force CLI mode (default: auto-detect)")
    args = parser.parse_args()

    if not IS_MAC and not IS_WINDOWS and platform.system() != "Linux":
        print("Supremo currently targets macOS, Windows, and Linux desktop actions.")

    assistant = Supremo()
    print("Supremo online. Type 'help' for commands, or 'quit' to exit.")
    print("Type 'skills' to see available skills.")
    if args.voice and not assistant.voice_loop():
        print("Supremo offline.")
        return
    while True:
        try:
            request = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nSupremo offline.")
            break
        try:
            if not assistant.handle(assistant.parse(request)):
                print("Supremo offline.")
                break
        except (EOFError, KeyboardInterrupt):
            print("\nSupremo offline.")
            break


if __name__ == "__main__":
    main()
