"""JARVIS-style GUI frontend for Supremo — the desktop management AI.

Features:
  - Antigravity window: transparent, always-on-top, floating, borderless
  - Fade-in animation on launch
  - Voice auto-mode: starts listening on launch
  - Voice visualization: animated bars when listening
  - Skills sidebar: shows all registered skills
  - Chat interface with avatars and timestamps
  - Smooth hover animations and neon accents
  - Cross-platform (macOS + Windows)

Run with: python3 jarvis.py
Or double-click the .app bundle.
"""

import datetime as dt
import io
import math
import platform
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.scrolledtext as tkst
from pathlib import Path
from tkinter import font as tkfont

IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"

# Font priority — try the best available monospace font per platform
if IS_MAC:
    FONT_FAMILY = ("SF Mono", "Monaco", "Menlo", "Courier New")
elif IS_WINDOWS:
    FONT_FAMILY = ("Cascadia Code", "Consolas", "Courier New", "Monospace")
else:
    FONT_FAMILY = ("DejaVu Sans Mono", "Liberation Mono", "Courier New", "Monospace")


def _get_font(size=11, weight="normal"):
    """Create a font with the best available monospace family."""
    for family in FONT_FAMILY:
        try:
            return tkfont.Font(family=family, size=size, weight=weight)
        except tk.TclError:
            continue
    return tkfont.Font(family="Courier", size=size, weight=weight)


# Ensure we can import the backend
sys.path.insert(0, str(Path(__file__).parent))
from supremo import Supremo, Intent, VoiceUnavailable


class VoiceVisualizer(tk.Canvas):
    """Animated sound-level visualizer shown in the header during voice mode."""

    def __init__(self, parent, width=120, height=26, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=JarvisApp.PANEL, highlightthickness=0, **kwargs)
        self.n_bars = 10
        self.bar_w = width / self.n_bars
        self.bars = []
        self.listening = False
        self.phase = 0
        for i in range(self.n_bars):
            bar = self.create_rectangle(
                i * self.bar_w, height,
                (i + 1) * self.bar_w - 1, height,
                fill=JarvisApp.MIC_OFF, width=0,
            )
            self.bars.append(bar)

    def set_listening(self, listening: bool):
        self.listening = listening
        for b in self.bars:
            self.itemconfig(b, fill=JarvisApp.GLOW if listening else JarvisApp.MIC_OFF)
        if listening:
            self._animate()

    def _animate(self):
        if not self.listening:
            # Reset bars to baseline
            for i, bar in enumerate(self.bars):
                self.coords(bar, i * self.bar_w, 26,
                            (i + 1) * self.bar_w - 1, 26)
            return
        self.phase += 1
        for i, bar in enumerate(self.bars):
            h = abs(math.sin(self.phase / 5 + i) * 12 + 3)
            self.coords(bar, i * self.bar_w, 26 - h,
                        (i + 1) * self.bar_w - 1, 26)
        self.after(40, self._animate)


class JarvisApp:
    """JARVIS-style GUI for the Supremo desktop assistant."""

    # --- Dark-mode design system (inspired by Linear, VoltAgent) ---
    BG = "#0a0f17"                    # canvas — near-black
    PANEL = "#161d2a"                # surface — one step lighter
    BORDER = "#2d3748"               # whisper border
    BORDER_HOVER = "#4a5568"         # hover border
    TEXT = "#f7f8f8"                 # snow white (not pure #fff)
    TEXT_SECONDARY = "#8b949e"       # steel slate
    TEXT_MUTED = "#62666d"           # quaternary
    USER_MSG = "#60a5fa"             # blue (user messages)
    AI_MSG = "#34d399"               # emerald (AI responses)
    INPUT_BG = "#1e293b"             # input surface
    GLOW = "#34d399"                 # emerald glow
    GLOW_HOVER = "#22c55e"           # emerald hover
    TIMESTAMP = "#62666d"
    WARNING = "#f59e0b"
    ERROR = "#ef4444"
    MIC_ON = "#34d399"
    MIC_OFF = "#62666d"
    GRADIENT_TOP = "#0f172a"
    GRADIENT_BOTTOM = "#0a0f17"

    def __init__(self, root):
        self.root = root
        self.assistant = Supremo()
        self.voice_active = False
        self.ptt_active = False
        self._voice_error = ""
        self.voice_enabled = self._check_voice_available()
        self._drag_start = {"x": 0, "y": 0}
        self.setup_window_effects()
        self.setup_ui()

        # Don't auto-start voice mode — let user initiate via:
        #   Space key (push-to-talk) or 🎙️ button (continuous mode)
        if self.voice_enabled:
            self.add_message("system", "Supremo",
                             "Ready! Hold SPACE to speak, or click 🎙️ for continuous mode.\n"
                             "Type commands for voice response anytime.")
            self._reset_status()
            self.voice_btn.configure(fg=self.MIC_ON)
        else:
            self.add_message("system", "Supremo",
                             "Voice mode unavailable.\n"
                             "Install: pip install sounddevice SpeechRecognition numpy\n"
                             f"  ({self._voice_error})\n"
                             "Typing mode active — type a command, I'll respond by voice.")

        self.speak("Supremo online. How can I help you?")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _check_voice_available(self):
        """Check if voice packages are installed and importable.

        Detects architecture mismatches (arm64/x86_64) on macOS and
        automatically re-executes the app with the correct architecture
        if possible.
        """
        import platform as _pf
        import subprocess as _sp
        import sys as _sys
        import os as _os

        try:
            import speech_recognition  # noqa: F401
            import sounddevice  # noqa: F401
            import numpy  # noqa: F401
            return True
        except Exception as e:
            err = str(e)
            if ("incompatible architecture" in err or "mach-o" in err) and _pf.system() == "Darwin":
                # On Apple Silicon, Python may run as x86_64 (Rosetta) while
                # packages are arm64. Try the opposite architecture.
                current_arch = _pf.machine()
                target_arch = "arm64" if current_arch == "x86_64" else "x86_64"
                try:
                    result = _sp.run(
                        ["arch", f"-{target_arch}", _sys.executable, "-c",
                         "import sounddevice, numpy, speech_recognition"],
                        capture_output=True, timeout=15
                    )
                    if result.returncode == 0:
                        # Packages work in target arch — re-exec app
                        _os.execvp("arch", [
                            "arch", f"-{target_arch}", _sys.executable,
                            _os.path.abspath(_sys.argv[0])
                        ] + _sys.argv[1:])
                except Exception:
                    pass
                self._voice_error = self._arch_mismatch_msg(e)
                return False
            self._voice_error = f"Import failed: {e}"
            return False

        # Packages imported successfully — on macOS, also verify mic access
        if IS_MAC:
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                has_input = any(
                    d.get("max_input_channels", 0) > 0 for d in devices
                )
                if has_input:
                    # Open stream to verify mic permission — if it raises,
                    # the OS denied access
                    with sd.InputStream(samplerate=16000, channels=1,
                                        dtype="int16"):
                        pass  # Just verify it opens, don't read audio
                if not has_input:
                    self._voice_error = (
                        "No microphone input device found.\n"
                        "Grant microphone access in System Settings > "
                        "Privacy & Security > Microphone."
                    )
                    return False
            except Exception as e:
                self._voice_error = f"Microphone error: {e}"
                return False

        return True

    def _arch_mismatch_msg(self, error):
        """Build a helpful message for architecture mismatch errors."""
        import platform
        py_arch = platform.machine()
        fix_cmd = f"arch -{py_arch} /usr/local/bin/python3 -m pip install sounddevice SpeechRecognition numpy"
        return (
            f"Architecture mismatch (Python={py_arch}, "
            f"library built for different arch).\n"
            f"Fix: Run app without Rosetta, or reinstall:\n"
            f"  {fix_cmd}"
        )

    def setup_window_effects(self):
        """Antigravity window: transparent, floating, always-on-top, borderless."""
        root = self.root
        # Semi-transparent window (antigravity effect)
        root.wm_attributes("-alpha", 0.0)  # start invisible for fade-in
        # Always float above other windows
        root.wm_attributes("-topmost", True)
        # Remove title bar for sleek floating look
        root.overrideredirect(True)

    def setup_ui(self):
        root = self.root
        root.title("Supremo — Desktop Management AI")
        root.geometry("1000x660")
        root.minsize(800, 520)
        root.eval("tk::PlaceWindow . center")
        root.configure(bg=self.GRADIENT_BOTTOM)

        # Main container — click to focus root (enables Space PTT)
        main_container = tk.Frame(root, bg=self.GRADIENT_BOTTOM)
        main_container.pack(fill="both", expand=True)
        main_container.bind("<Button-1>", lambda e: root.focus_set())

        # ── Header (drag area + controls) ──
        header = tk.Frame(main_container, bg=self.PANEL, height=60,
                          highlightbackground=self.BORDER, highlightthickness=1)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        header.bind("<ButtonPress-1>", self._on_drag_start)
        header.bind("<B1-Motion>", self._on_drag_motion)

        # Left: logo + name
        header_left = tk.Frame(header, bg=self.PANEL)
        header_left.pack(side="left", padx=16, pady=0, fill="y")

        self.dot = tk.Canvas(header_left, width=24, height=24,
                             bg=self.PANEL, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 10))
        self._draw_logo()

        name_label = tk.Label(header_left, text="SUPREMO",
                              font=_get_font(15, "bold"),
                              fg=self.USER_MSG, bg=self.PANEL)
        name_label.pack(side="left")

        subtitle = tk.Label(header_left, text="Desktop Management AI · v3.0",
                            font=_get_font(9), fg=self.TIMESTAMP, bg=self.PANEL)
        subtitle.pack(side="left", padx=(8, 0))

        # Center: voice visualizer
        self.viz = VoiceVisualizer(header, width=120, height=26)
        self.viz.pack(side="left", padx=(24, 0))

        # Right: controls + close
        right_frame = tk.Frame(header, bg=self.PANEL)
        right_frame.pack(side="right", padx=(0, 8))

        self.voice_btn = tk.Button(
            right_frame, text="🎙️", font=_get_font(14),
            bg=self.PANEL,
            fg=self.MIC_ON if self.voice_enabled else self.MIC_OFF,
            activebackground=self.PANEL, activeforeground=self.GLOW,
            relief="flat", borderwidth=0, width=3, height=1,
            command=self.toggle_voice, cursor="hand2")
        self.voice_btn.pack(side="left", padx=(0, 6))

        listen_icon = tk.Button(
            right_frame, text="🔊", font=_get_font(12),
            bg=self.PANEL, fg=self.TEXT_SECONDARY,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, width=3, height=1,
            command=self.start_voice_once, cursor="hand2")
        listen_icon.pack(side="left", padx=(0, 6))

        # Fix Voice button (shows when voice is unavailable)
        self.fix_btn = tk.Button(
            right_frame, text="🔧", font=_get_font(12),
            bg=self.PANEL, fg=self.TEXT_SECONDARY,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, width=3, height=1,
            command=self._fix_voice, cursor="hand2")
        self.fix_btn.pack(side="left", padx=(0, 6))
        if self.voice_enabled:
            self.fix_btn.pack_forget()

        close_btn = tk.Button(
            header, text="✕", font=_get_font(14, "bold"),
            fg="#f87171", bg=self.PANEL,
            activebackground="#7f1d1d", activeforeground="#fca5a5",
            relief="flat", borderwidth=0, padx=10, pady=0,
            command=self._close_window, cursor="hand2")
        close_btn.pack(side="right", padx=(0, 4))

        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg="#fca5a5"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg="#f87171"))

        # ── Content area (chat + skills sidebar) ──
        content = tk.Frame(main_container, bg=self.GRADIENT_BOTTOM)
        content.pack(fill="both", expand=True, padx=16, pady=12)

        # Chat area
        chat_container = tk.Frame(content, bg=self.BG,
                                  highlightbackground=self.BORDER,
                                  highlightthickness=1)
        chat_container.pack(fill="both", expand=True, side="left", padx=(0, 12))

        self.chat = tkst.ScrolledText(
            chat_container, wrap="word", font=_get_font(11),
            bg=self.PANEL, fg=self.TEXT, insertbackground=self.USER_MSG,
            insertwidth=2, relief="flat", borderwidth=0, highlightthickness=0,
            spacing1=4, spacing2=3, spacing3=4, state="disabled",
            selectbackground="#33415b", selectforeground=self.TEXT,
        )
        self.chat.pack(fill="both", expand=True, side="left", padx=1, pady=1)

        scrollbar = tk.Scrollbar(chat_container, orient="vertical",
                                 command=self.chat.yview, width=10)
        scrollbar.pack(fill="y", side="right", padx=(0, 1))
        self.chat.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(bg=self.BG, troughcolor=self.BORDER,
                            activebackground=self.GLOW, activerelief="flat")

        # ── Skills sidebar ──
        self.skills_frame = tk.Frame(content, bg=self.PANEL, width=190,
                                     highlightbackground=self.BORDER,
                                     highlightthickness=1)
        self.skills_frame.pack(side="right", fill="y", padx=(12, 0))
        self.skills_frame.pack_propagate(False)

        skills_title = tk.Label(self.skills_frame, text="SKILLS",
                                font=_get_font(9, "bold"),
                                fg=self.AI_MSG, bg=self.PANEL)
        skills_title.pack(pady=(14, 8), padx=12, anchor="w")

        self.skills_list = tk.Listbox(
            self.skills_frame, font=_get_font(9), bg=self.PANEL,
            fg=self.TEXT_SECONDARY, relief="flat", borderwidth=0, highlightthickness=0,
            activestyle="none", selectbackground="#33415b",
            selectforeground=self.TEXT, height=20)
        self.skills_list.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        self._refresh_skills_list()

        # ── Input area ──
        input_frame = tk.Frame(main_container, bg=self.GRADIENT_BOTTOM)
        input_frame.pack(fill="x", padx=16, pady=(0, 16))

        input_container = tk.Frame(input_frame, bg=self.INPUT_BG,
                                   highlightbackground=self.BORDER,
                                   highlightthickness=1)
        input_container.pack(fill="x", expand=True)

        self.input_field = tk.Entry(
            input_container, font=_get_font(12), bg=self.INPUT_BG,
            fg=self.TEXT, insertbackground=self.AI_MSG,
            relief="flat", borderwidth=0, highlightthickness=0, width=1,
            disabledbackground=self.INPUT_BG, disabledforeground=self.TEXT_MUTED)
        self.input_field.pack(fill="x", padx=12, pady=10)
        self.input_field.bind("<Return>", self.on_enter)
        # Don't auto-focus the input field — let Space key trigger PTT when
        # the user clicks window background. Click input field to type.

        # Button row — ghost buttons with subtle hover
        btn_row = tk.Frame(input_frame, bg=self.GRADIENT_BOTTOM)
        btn_row.pack(side="right", padx=(8, 0))

        voice_input_btn = tk.Button(
            btn_row, text="🎙️", font=_get_font(12),
            bg=self.PANEL, fg=self.MIC_ON if self.voice_enabled else self.MIC_OFF,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, width=4, height=1,
            command=self.start_voice_once, cursor="hand2")
        voice_input_btn.pack(side="left", padx=(0, 4))

        send_btn = tk.Button(
            btn_row, text="SEND", font=_get_font(12, "bold"),
            bg=self.AI_MSG, fg=self.BG,
            activebackground=self.GLOW_HOVER, activeforeground=self.BG,
            relief="flat", borderwidth=0, padx=16, pady=6,
            command=self.on_send, cursor="hand2")
        send_btn.pack(side="left")

        # Hover states — subtle opacity shifts
        send_btn.bind("<Enter>", lambda e: send_btn.configure(bg=self.GLOW_HOVER, fg=self.BG))
        send_btn.bind("<Leave>", lambda e: send_btn.configure(bg=self.AI_MSG, fg=self.BG))
        voice_input_btn.bind("<Enter>", lambda e: voice_input_btn.configure(fg=self.GLOW))
        voice_input_btn.bind("<Leave>", lambda e: voice_input_btn.configure(
            fg=self.MIC_ON if self.voice_enabled else self.MIC_OFF))

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready — type a command or click 🎙️")
        status_bar = tk.Label(main_container, textvariable=self.status_var,
                              font=_get_font(9), fg=self.TIMESTAMP,
                              bg=self.GRADIENT_BOTTOM)
        status_bar.pack(fill="x", padx=16, pady=(0, 8))

        # Welcome message
        self.add_message("system", "Supremo Desktop Management AI",
                         "I'm online. Try:\n"
                         "  • open Safari / close Chrome\n"
                         "  • search Python dataclasses\n"
                         "  • screenshot\n"
                         "  • battery / time / date\n"
                         "  • chatgpt what is artificial intelligence\n"
                         "  • skills (list available skills)\n"
                         "  • skill calculate 2 + 2\n"
                         "  • skill note buy groceries\n"
                         "Type 'help' for the full command list.\n"
                         "\n"
                         "🎙️ Voice input" if self.voice_enabled
                         else "⌨️ Typing works — type a command, I'll respond by voice"
                         + (" (click 🔧 to fix voice input)" if not self.voice_enabled else ""))

    def _draw_logo(self, pulse=False):
        """Draw the Supremo logo dot with glow effect."""
        self.dot.delete("all")
        # Glow rings
        for r in range(4, 0, -1):
            self.dot.create_oval(4 + r, 4 + r, 20 - r, 20 - r,
                                 outline=self.GLOW, width=1)
        # Core
        fill_color = self.GLOW_HOVER if pulse else self.GLOW
        self.dot.create_oval(7, 7, 17, 17, fill=fill_color, outline=fill_color)

    def _animate_logo(self):
        """Pulse the logo dot during voice listening."""
        if not self.voice_active:
            self._draw_logo(pulse=False)
            return
        self._draw_logo(pulse=True)
        self.root.after(600, self._animate_logo)
        self.root.after(300, lambda: self._draw_logo(pulse=False) if self.voice_active else None)

    def _refresh_skills_list(self):
        """Update the skills sidebar with current skills."""
        self.skills_list.delete(0, tk.END)
        skills = self.assistant.list_skills()
        for name, desc in sorted(skills):
            self.skills_list.insert(tk.END, f"  {name}")

        # Add separator and built-in command hints
        self.skills_list.insert(tk.END, "")
        self.skills_list.insert(tk.END, "Built-in commands")
        for cmd in ["open", "close", "search", "find", "say", "notify",
                     "copy", "run", "time", "date", "battery", "screenshot"]:
            self.skills_list.insert(tk.END, f"  {cmd}")

    # ------------------------------------------------------------------
    # Drag handling for borderless window
    # ------------------------------------------------------------------
    def _on_drag_start(self, event):
        self._drag_start["x"] = event.x
        self._drag_start["y"] = event.y

    def _on_drag_motion(self, event):
        dx = event.x - self._drag_start["x"]
        dy = event.y - self._drag_start["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def _close_window(self):
        self.speak("Going offline.")
        self.root.quit()

    # ------------------------------------------------------------------
    # Voice mode
    # ------------------------------------------------------------------
    def toggle_voice(self):
        if not self.voice_enabled:
            return
        if self.voice_active:
            self.stop_voice()
        else:
            self.start_voice_listener()

    def start_voice_once(self):
        """Manually trigger one voice listening cycle."""
        if not self.voice_enabled:
            self.add_message("system", "Supremo",
                             f"Voice mode unavailable: {self._voice_error}\\n"
                             "Install: pip install sounddevice SpeechRecognition numpy")
            return
        self.voice_active = True
        self._update_voice_ui()
        threading.Thread(target=self._do_voice_once, daemon=True).start()

    def _do_voice_once(self):
        try:
            transcript = self.assistant.listen_once()
            if transcript:
                self.root.after(0, self._process_voice_transcript, transcript)
            else:
                self.root.after(0, self.add_message, "system", "Supremo",
                                "No speech detected. Try again.")
        except VoiceUnavailable as e:
            self.root.after(0, self.add_message, "system", "Supremo", str(e))
        finally:
            self.voice_active = False
            self.root.after(0, self._update_voice_ui)
            self.root.after(0, lambda: self.status_var.set(
                "Ready — type or click 🎙️") if not self.voice_enabled
                else "Voice off. Click 🎙️ to listen.")

    def start_voice_listener(self):
        """Start background voice listener (auto mode)."""
        if not self.voice_enabled or self.voice_active:
            return
        self.voice_active = True
        self._update_voice_ui()
        threading.Thread(target=self._voice_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # Push-to-Talk (hold Space key to listen)
    # ------------------------------------------------------------------
    def _on_ptt_press(self, event):
        # Don't trigger PTT when typing in the input field
        focused = self.root.focus_get()
        if isinstance(focused, tk.Entry):
            return
        if not self.voice_enabled or self.ptt_active:
            return
        self.ptt_active = True
        self.voice_active = True
        self._update_voice_ui()
        threading.Thread(target=self._ptt_listen, daemon=True).start()

    def _on_ptt_release(self, event):
        if self.ptt_active:
            self.ptt_active = False

    def _ptt_listen(self):
        """Record audio via sounddevice while PTT key is held, then transcribe."""
        import sounddevice as sd
        import numpy as np
        import speech_recognition as sr

        sample_rate = 16000
        audio_chunks = []

        def callback(indata, frames, time, status):
            if status:
                import sys as _sys
                print(f"Audio: {status}", file=_sys.stderr)
            if not self.ptt_active:
                return sd.CallbackStop
            audio_chunks.append(indata.tobytes())

        try:
            with sd.InputStream(
                samplerate=sample_rate, channels=1,
                dtype="int16", callback=callback
            ) as stream:
                # Block until PTT released or phrase limit reached
                import time
                start_time = time.time()
                while self.ptt_active and (time.time() - start_time) < self.assistant.PHRASE_LIMIT:
                    sd.sleep(100)
        except Exception as e:
            self.root.after(0, self.add_message, "error", "Error",
                            f"Voice input error: {e}")
            self.ptt_active = False
            self.voice_active = False
            self.root.after(0, self._update_voice_ui)
            self.root.after(0, self._reset_status)
            return

        # Stop recording state
        self.ptt_active = False
        self.voice_active = False
        self.root.after(0, self._update_voice_ui)

        # Transcribe captured audio
        if audio_chunks:
            audio_data = sr.AudioData(
                b"".join(audio_chunks), sample_rate, 2
            )
            recognizer = sr.Recognizer()
            try:
                transcript = recognizer.recognize_google(audio_data)
                if transcript:
                    self.root.after(0, self._process_voice_transcript, transcript)
                else:
                    self.root.after(0, self.add_message, "system", "Supremo",
                                    "No speech detected.")
            except sr.UnknownValueError:
                self.root.after(0, self.add_message, "system", "Supremo",
                                "Couldn't understand that.")
            except Exception as e:
                self.root.after(0, self.add_message, "error", "Error", str(e))

        self.root.after(0, self._reset_status)

    def _update_voice_ui(self):
        if self.voice_active:
            self.voice_btn.configure(fg=self.MIC_ON)
            if self.ptt_active:
                self.status_var.set("🔴 Push-to-talk — holding SPACE")
                self.viz.set_listening(True)
                self._animate_logo()
            else:
                self.status_var.set("🔊 Listening...")
                self.viz.set_listening(True)
                self._animate_logo()
        else:
            self.voice_btn.configure(
                fg=self.MIC_ON if self.voice_enabled else self.MIC_OFF)
            self.viz.set_listening(False)
            self._draw_logo(pulse=False)
            if self.voice_enabled:
                self.status_var.set("Voice off. Hold SPACE or click 🎙️")
            else:
                self.status_var.set("Type a command (🔧 to fix voice)")
    # ------------------------------------------------------------------
    def _fix_voice(self):
        """Auto-detect Python architecture and install packages correctly."""
        self.status_var.set("Fixing voice input...")
        threading.Thread(target=self._do_fix_voice, daemon=True).start()

    def _do_fix_voice(self):
        """Run the fix command in the correct architecture."""
        import platform, subprocess, sys

        is_mac = platform.system() == "Darwin"
        python = sys.executable
        current_arch = platform.machine()
        messages = []

        if is_mac:
            for target in ["arm64", "x86_64"]:
                try:
                    cmd = ["arch", f"-{target}", python, "-m", "pip", "install",
                           "sounddevice", "SpeechRecognition", "numpy"]
                    result = subprocess.run(cmd, capture_output=True,
                                            text=True, timeout=60)
                    ok = result.returncode == 0
                    messages.append(f"arch -{target}: {'OK' if ok else 'FAILED'}")
                except Exception as e:
                    messages.append(f"arch -{target}: {e}")

            for target in ["arm64", "x86_64"]:
                try:
                    result = subprocess.run(
                        ["arch", f"-{target}", python, "-c",
                         "import sounddevice, numpy, speech_recognition; print('OK')"],
                        capture_output=True, text=True, timeout=15)
                    if result.returncode == 0 and "OK" in result.stdout:
                        self.root.after(0, self.add_message, "system", "Supremo",
                                        f"Voice fix succeeded (arch -{target})!"
                                        + "\n".join(messages))
                        self.root.after(2000, self._reopen_in_arch, target)
                        return
                except Exception as e:
                    messages.append(f"arch -{target}: {e}")

            self.root.after(0, self.add_message, "system", "Supremo",
                            "Voice fix attempted. If still broken, run manually:\n"
                            "  arch -arm64 python3 -m pip install sounddevice SpeechRecognition numpy\n"
                            "  arch -x86_64 python3 -m pip install sounddevice SpeechRecognition numpy\n"
                            + "\n".join(messages))
        else:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install",
                     "sounddevice", "SpeechRecognition", "numpy"],
                    capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    self.root.after(0, self.add_message, "system", "Supremo",
                                    "Packages installed. Restart Supremo.")
                else:
                    self.root.after(0, self.add_message, "system", "Supremo",
                                    "Install failed. Run: pip install sounddevice SpeechRecognition numpy")
            except Exception as e:
                self.root.after(0, self.add_message, "system", "Supremo",
                                f"Install error: {e}")

        self.root.after(0, self._reset_status)

    def _reopen_in_arch(self, target_arch):
        """Re-launch the app using the specified architecture."""
        import os, subprocess, sys
        python = sys.executable
        app_path = os.path.abspath(sys.argv[0])
        subprocess.Popen(
            ["arch", f"-{target_arch}", python, app_path] + sys.argv[1:],
            cwd=os.path.dirname(app_path) or ".",
        )
        self.root.quit()

    def _voice_loop(self):
        """Continuous voice listening loop (auto mode)."""
        import time
        silent_count = 0
        while self.voice_active:
            try:
                transcript = self.assistant.listen_once(quiet=True)
                if transcript:
                    silent_count = 0
                    self.root.after(0, self._process_voice_transcript, transcript)
                else:
                    silent_count += 1
                    if silent_count == 3:
                        self.root.after(0, self.add_message, "system", "Supremo",
                                        "Still listening — speak into the microphone.")
                    elif silent_count == 10:
                        self.root.after(0, self.add_message, "system", "Supremo",
                                        "No audio detected. Check microphone "
                                        "permissions in System Settings > "
                                        "Privacy & Security > Microphone.")
                        silent_count = 0
                time.sleep(0.3)
            except VoiceUnavailable as e:
                self.root.after(0, self.add_message, "system", "Supremo", str(e))
                self.root.after(0, self._safe_stop_voice)
                break
            except Exception as e:
                self.root.after(0, self.add_message, "error", "Voice", str(e))
                self.root.after(0, self._safe_stop_voice)
                break

    def _safe_stop_voice(self):
        """Stop voice mode from a background thread (thread-safe)."""
        self.voice_active = False
        self._update_voice_ui()

    def stop_voice(self):
        self.voice_active = False
        self.ptt_active = False
        self.root.after(0, self._update_voice_ui)
        self.root.after(0, self._reset_status)

    def _update_voice_ui(self):
        if self.voice_active:
            self.voice_btn.configure(fg=self.MIC_ON)
            self.status_var.set("🔊 Listening...")
            self.viz.set_listening(True)
            self._animate_logo()
        else:
            self.voice_btn.configure(
                fg=self.MIC_ON if self.voice_enabled else self.MIC_OFF)
            self.viz.set_listening(False)
            self._draw_logo(pulse=False)
            if self.voice_enabled:
                self.status_var.set("Voice off. Click 🎙️ to listen.")
            else:
                self.status_var.set("Ready — type or click 🎙️")

    def _process_voice_transcript(self, transcript: str):
        self.add_message("system", "🎤 Heard", transcript)
        intent = self.assistant.parse(transcript)

        if intent.action == "stop_listening":
            self.stop_voice()
            self.add_message("ai", "Supremo", "Voice mode off.")
            return

        if intent.action == "quit":
            self.add_message("ai", "Supremo", "Going offline. Goodbye!")
            self.speak("Goodbye")
            self.root.after(500, self.root.quit)
            return

        threading.Thread(
            target=self._process_intent, args=(intent,), daemon=True
        ).start()

    def _process_intent(self, intent: Intent):
        """Process an intent and display the result in the chat."""
        old_stdout = sys.stdout
        captured = io.StringIO()
        sys.stdout = captured

        try:
            self.assistant.handle(intent)
        except Exception as e:
            sys.stdout = old_stdout
            self.root.after(0, self.add_message, "error", "Error", str(e))
            return
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue().strip()
        if output:
            self.root.after(0, self.add_message, "ai", "Supremo", output)
            self.speak_response(output)
        else:
            self.root.after(0, self.add_message, "ai", "Supremo", "Done.")

    # ------------------------------------------------------------------
    # Chat / messaging
    # ------------------------------------------------------------------
    def add_message(self, sender, sender_name, message, is_error=False):
        """Add a message to the chat display."""
        current = self.chat.get("1.0", tk.END).strip()
        if current:
            self.chat.configure(state="normal")
            self.chat.insert(tk.END, "\n\n")
            self.chat.configure(state="disabled")

        timestamp = dt.datetime.now().strftime("%H:%M")
        self.chat.configure(state="normal")

        if sender == "user":
            color = self.USER_MSG
            prefix = "> "
        elif sender == "system":
            color = self.TEXT
            prefix = "· "
        elif sender == "error":
            color = self.ERROR
            prefix = "! "
        else:
            color = self.AI_MSG
            prefix = "▶ "

        self.chat.insert(tk.END, f"{prefix}{sender_name}  ", color)
        self.chat.insert(tk.END, f"{timestamp}\n", self.TIMESTAMP)
        self.chat.insert(tk.END, f"  {message}\n",
                         color if sender == "user" else self.TEXT)

        self.chat.configure(state="disabled")
        self.chat.see(tk.END)

    def on_enter(self, event):
        self.on_send()

    def on_send(self):
        user_input = self.input_field.get().strip()
        if not user_input:
            return
        self.add_message("user", "You", user_input)
        self.input_field.delete(0, tk.END)
        self.status_var.set("Processing...")
        threading.Thread(
            target=self._process_typed_command, args=(user_input,), daemon=True
        ).start()

    def _process_typed_command(self, request: str):
        try:
            intent = self.assistant.parse(request)

            if intent.action == "quit":
                self.add_message("ai", "Supremo", "Going offline. Goodbye!")
                self.speak("Goodbye")
                self.root.after(500, self.root.quit)
                return

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                self.assistant.handle(intent)
            finally:
                sys.stdout = old_stdout

            output = captured.getvalue().strip()
            if output:
                self.root.after(0, self.add_message, "ai", "Supremo", output)
                self.speak_response(output)
            else:
                self.root.after(0, self.add_message, "ai", "Supremo", "Done.")
        except Exception as e:
            self.root.after(0, self.add_message, "error", "Error", str(e))

        self.root.after(0, self._reset_status)

    def _reset_status(self):
        if self.voice_active and self.ptt_active:
            self.status_var.set("🔴 Push-to-talk — holding SPACE")
        elif self.voice_active:
            self.status_var.set("🔊 Listening...")
        elif self.voice_enabled:
            self.status_var.set("Ready — hold SPACE or type")
        else:
            self.status_var.set("Voice unavailable — type to chat (🔧 to fix)")

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------
    def speak(self, text: str):
        """Speak text using platform TTS."""
        try:
            if IS_MAC:
                subprocess.run(["say", text], timeout=5)
            elif IS_WINDOWS:
                ps = (
                    "Add-Type -AssemblyName System.Speech;"
                    f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;'
                    f'$s.Speak("{text}")'
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=5)
            else:
                subprocess.run(["espeak", text], timeout=5)
        except Exception:
            pass

    def speak_response(self, text: str):
        """Speak a short response aloud."""
        if len(text) > 200:
            return
        if text.startswith(("Opening", "Searching")):
            return
        if text.startswith(("·", "!")):
            return
        self.speak(text)

    def destroy(self):
        self.voice_active = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = JarvisApp(root)
    root.configure(bg=JarvisApp.GRADIENT_BOTTOM)
    root.option_add("*tearOff", tk.FALSE)
    root.bind("<Escape>", lambda e: root.quit())
    root.bind_all("<space>", app._on_ptt_press)
    root.bind_all("<KeyRelease-space>", app._on_ptt_release)
    root.focus_set()  # Give root focus so Space triggers PTT (not typing)

    # Antigravity: fade-in animation
    root.wm_attributes("-alpha", 0.0)

    def fade_in(alpha=0.0):
        alpha += 0.03
        if alpha < 0.93:
            root.wm_attributes("-alpha", alpha)
            root.after(15, fade_in, alpha)
        else:
            root.wm_attributes("-alpha", 0.93)

    root.after(50, fade_in)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
