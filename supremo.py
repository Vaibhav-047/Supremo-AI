"""Supremo: a small, safe desktop assistant for macOS.

Run with: python3 supremo.py            (type commands)
          python3 supremo.py --voice    (start in voice mode)

Voice input is optional. To enable it:
    brew install portaudio
    pip3 install SpeechRecognition pyaudio
"""

from __future__ import annotations

import argparse
import datetime as dt
import platform
import re
import shlex
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Intent:
    action: str
    value: str = ""


class VoiceUnavailable(Exception):
    """Raised when voice input can't be used (missing package, no microphone)."""


class Supremo:
    """Command router and desktop action layer for Supremo."""

    APP_ALIASES = {
        "browser": "Safari",
        "safari": "Safari",
        "chrome": "Google Chrome",
        "finder": "Finder",
        "terminal": "Terminal",
        "notes": "Notes",
        "calendar": "Calendar",
        "mail": "Mail",
        "music": "Music",
        "code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "preview": "Preview",
        "settings": "System Settings",
        "calculator": "Calculator",
        "messages": "Messages",
    }
    BLOCKED_COMMANDS = {
        "sudo",
        "su",
        "shutdown",
        "reboot",
        "halt",
        "mkfs",
        "diskutil",
        "launchctl",
        "kill",
        "killall",
        "crontab",
        "dscl",
        "rm",
        "dd",
        "chmod",
        "chown",
        "mv",
        "eval",
        "exec",
    }
    POLITE_PREFIXES = ("please ", "can you ", "could you ", "would you ")
    POLITE_SUFFIXES = (" please",)
    # Speech recognition can mishear, so these are typed-only: a transcript
    # never runs shell commands or nests another voice session.
    VOICE_BLOCKED_ACTIONS = {"run", "listen", "voice_mode"}
    LISTEN_TIMEOUT = 6  # seconds to wait for speech to start
    PHRASE_LIMIT = 10  # max seconds for a single spoken command

    def parse(self, request: str) -> Intent:
        text = self._normalize(request)
        if not text:
            return Intent("empty")
        normalized = text.lower()

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
        for prefix in ("open ", "launch ", "start "):
            if normalized.startswith(prefix):
                return Intent("open", text[len(prefix):])
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
        return Intent("unknown", text)

    def handle(self, intent: Intent, from_voice: bool = False) -> bool:
        actions = {
            "help": self.show_help,
            "time": self.show_time,
            "date": self.show_date,
            "battery": self.show_battery,
            "screenshot": self.take_screenshot,
            "open": self.open_target,
            "search": self.search_web,
            "find": self.find_files,
            "say": self.speak,
            "notify": self.notify,
            "copy": self.copy_to_clipboard,
            "run": self.run_command,
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

    def show_help(self, _value: str = "") -> None:
        print(
            """
Supremo can help with:
  open Safari                Launch an app
  open https://example.com   Open a website
  search Python dataclasses  Search the web
  find budget                Find files in your home folder
  say good morning           Speak a short phrase
  notify stretch             Show a macOS notification
  copy meeting notes         Copy text to the clipboard
  screenshot                 Save a screenshot to the Desktop
  battery                    Show battery status
  run pwd                    Run a command after confirmation
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
        output = self._capture(["pmset", "-g", "batt"])
        if output is None:
            return
        print(output or "Could not read battery status.")

    def take_screenshot(self, _value: str = "") -> None:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path.home() / "Desktop" / f"supremo-screenshot-{stamp}.png"
        if self._run(["screencapture", "-x", str(path)]):
            print(f"Saved screenshot to {path}")

    def open_target(self, target: str) -> None:
        target = target.strip()
        if not target:
            print("Tell me what you want to open.")
            return
        app_name = self.APP_ALIASES.get(target.lower(), target)
        path = Path(target).expanduser()
        if path.exists():
            self._run(["open", str(path)])
            return
        if target.lower() in self.APP_ALIASES or "://" not in target and "." not in target:
            self._run(["open", "-a", app_name])
            return
        url = target if "://" in target else f"https://{target}"
        print(f"Opening {url}")
        webbrowser.open(url)

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
        matches = self._spotlight_matches(name)
        if matches is None:
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
        self._run(["say", text])

    def notify(self, message: str) -> None:
        message = message.strip()
        if not message:
            print("Tell me what the notification should say.")
            return
        script = (
            'display notification "{}" with title "Supremo"'.format(
                message.replace("\\", "\\\\").replace('"', '\\"')
            )
        )
        self._run(["osascript", "-e", script])

    def copy_to_clipboard(self, text: str) -> None:
        text = text.strip()
        if not text:
            print("Tell me what to copy.")
            return
        try:
            subprocess.run(
                ["pbcopy"],
                input=text,
                text=True,
                check=True,
                timeout=10,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            print(f"Could not copy to the clipboard: {error}")
            return
        print("Copied to the clipboard.")

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
            print(
                f"Refusing to run {argv[0]!r}. Supremo only runs low-risk commands.")
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
                argv,
                check=False,
                text=True,
                capture_output=True,
                timeout=30,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            print(f"Could not run command: {error}")
            return
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        print(f"Command finished with exit code {result.returncode}.")

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
            import speech_recognition as sr
        except ImportError:
            raise VoiceUnavailable(
                "Voice input needs extra packages:\n"
                "  brew install portaudio\n"
                "  pip3 install SpeechRecognition pyaudio"
            ) from None

        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.4)
                if not quiet:
                    print("Listening...")
                audio = recognizer.listen(
                    source,
                    timeout=self.LISTEN_TIMEOUT,
                    phrase_time_limit=self.PHRASE_LIMIT,
                )
        except sr.WaitTimeoutError:
            if not quiet:
                print(
                    "I didn't hear anything. If this keeps happening, allow "
                    "microphone access for your terminal in System Settings > "
                    "Privacy & Security > Microphone."
                )
            return None
        except AttributeError:
            # SpeechRecognition raises this when PyAudio is missing.
            raise VoiceUnavailable(
                "PyAudio is missing. Install it with:\n"
                "  brew install portaudio\n"
                "  pip3 install pyaudio"
            ) from None
        except OSError as error:
            raise VoiceUnavailable(
                f"Could not open the microphone: {error}"
            ) from None

        try:
            return recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            if not quiet:
                print("Sorry, I couldn't understand that.")
        except sr.RequestError as error:
            raise VoiceUnavailable(
                f"Speech recognition service unavailable: {error}"
            ) from None
        return None

    def _process_transcript(self, transcript: str) -> Intent:
        transcript = self._clean_transcript(transcript)
        print(f"Heard: {transcript}")
        return self.parse(transcript)

    def explain_unknown(self, request: str) -> None:
        print(
            f"I do not know how to handle {request!r} yet. Type 'help' for commands.")

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
            # "open github dot com" -> "open github.com"
            text = re.sub(r"\s+dot\s+", ".", text, flags=re.IGNORECASE)
        return text

    def _spotlight_matches(self, name: str) -> list[Path] | None:
        if platform.system() != "Darwin":
            return None
        query = "kMDItemDisplayName == {}c".format(
            self._spotlight_glob(name)
        )
        output = self._capture(
            ["mdfind", "-onlyin", str(Path.home()), query],
            timeout=15,
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
                command,
                check=False,
                text=True,
                capture_output=True,
                timeout=timeout,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Supremo desktop assistant")
    parser.add_argument(
        "--voice", action="store_true", help="start in voice mode"
    )
    args = parser.parse_args()

    if platform.system() != "Darwin":
        print("Supremo currently targets macOS desktop actions.")
    assistant = Supremo()
    print("Supremo online. Type 'help' for commands, or 'quit' to exit.")
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
