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

    # --- Antigravity theme ---
    BG = "#0a0f17"
    PANEL = "#161d2a"
    BORDER = "#2d3748"
    TEXT = "#e5e7eb"
    USER_MSG = "#60a5fa"
    AI_MSG = "#34d399"
    INPUT_BG = "#1e293b"
    GLOW = "#34d399"
    GLOW_HOVER = "#22c55e"
    TIMESTAMP = "#64748b"
    WARNING = "#f59e0b"
    ERROR = "#ef4444"
    MIC_ON = "#34d399"
    MIC_OFF = "#64748b"
    GRADIENT_TOP = "#0f172a"
    GRADIENT_BOTTOM = "#0a0f17"

    def __init__(self, root):
        self.root = root
        self.assistant = Supremo()
        self.voice_active = False
        self._voice_error = ""
        self.voice_enabled = self._check_voice_available()
        self._drag_start = {"x": 0, "y": 0}
        self.setup_window_effects()
        self.setup_ui()

        # Auto-start voice mode on launch
        if self.voice_enabled:
            self.add_message("system", "Supremo",
                             "Voice mode auto-started. Say 'stop listening' to disable.")
            self.status_var.set("🔊 Listening...")
            self.voice_btn.configure(fg=self.MIC_ON)
            self.viz.set_listening(True)
            self._animate_logo()
            threading.Thread(target=self._voice_loop, daemon=True).start()
        else:
            self.add_message("system", "Supremo",
                             "Voice mode unavailable.\n"
                             "Install: pip install SpeechRecognition pyaudio\n"
                             f"  ({self._voice_error})")

        self.speak("Supremo online. How can I help you?")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _check_voice_available(self):
        """Check if voice packages are installed and importable."""
        try:
            import speech_recognition  # noqa: F401
            try:
                import pyaudio  # noqa: F401
            except Exception as e:
                self._voice_error = f"pyaudio: {e}"
                return False
            return True
        except ImportError as e:
            self._voice_error = f"speech_recognition: {e}"
            return False
        except Exception as e:
            self._voice_error = f"unexpected: {type(e).__name__}: {e}"
            return False

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

        # Main container
        main_container = tk.Frame(root, bg=self.GRADIENT_BOTTOM)
        main_container.pack(fill="both", expand=True)

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

        name_label = tk.Label(header_left, text="SUPEREMO",
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
            bg=self.PANEL, fg=self.TEXT,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, width=3, height=1,
            command=self.start_voice_once, cursor="hand2")
        listen_icon.pack(side="left", padx=(0, 6))

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
                                fg=self.USER_MSG, bg=self.PANEL)
        skills_title.pack(pady=(14, 8), padx=12, anchor="w")

        self.skills_list = tk.Listbox(
            self.skills_frame, font=_get_font(9), bg=self.PANEL,
            fg=self.TEXT, relief="flat", borderwidth=0, highlightthickness=0,
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
            fg=self.TEXT, insertbackground=self.USER_MSG,
            relief="flat", borderwidth=0, highlightthickness=0, width=1)
        self.input_field.pack(fill="x", padx=12, pady=10)
        self.input_field.bind("<Return>", self.on_enter)
        self.input_field.focus_set()

        # Button row
        btn_row = tk.Frame(input_frame, bg=self.GRADIENT_BOTTOM)
        btn_row.pack(side="right", padx=(8, 0))

        voice_input_btn = tk.Button(
            btn_row, text="🎙️", font=_get_font(12),
            bg=self.PANEL, fg=self.TEXT,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, width=4, height=1,
            command=self.start_voice_once, cursor="hand2")
        voice_input_btn.pack(side="left", padx=(0, 4))

        send_btn = tk.Button(
            btn_row, text="SEND", font=_get_font(12, "bold"),
            bg=self.USER_MSG, fg=self.BG,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, padx=16, pady=6,
            command=self.on_send, cursor="hand2")
        send_btn.pack(side="left")

        send_btn.bind("<Enter>", lambda e: send_btn.configure(bg=self.GLOW_HOVER))
        send_btn.bind("<Leave>", lambda e: send_btn.configure(bg=self.USER_MSG))
        voice_input_btn.bind("<Enter>", lambda e: voice_input_btn.configure(fg=self.GLOW))
        voice_input_btn.bind("<Leave>", lambda e: voice_input_btn.configure(fg=self.TEXT))

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
                         "Type 'help' for the full command list.")

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
                             f"Voice mode unavailable: {self._voice_error}\n"
                             "Install: pip install SpeechRecognition pyaudio")
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

    def _voice_loop(self):
        """Continuous voice listening loop (auto mode)."""
        import time
        while self.voice_active:
            try:
                transcript = self.assistant.listen_once(quiet=True)
                if transcript:
                    self.root.after(0, self._process_voice_transcript, transcript)
                time.sleep(0.3)
            except VoiceUnavailable:
                break
            except Exception as e:
                self.root.after(0, self.add_message, "error", "Voice", str(e))
                break

    def stop_voice(self):
        self.voice_active = False
        self.root.after(0, self._update_voice_ui)
        self.root.after(0, lambda: self.status_var.set("Voice off. Click 🎙️ to listen."))

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
        if self.voice_active:
            self.status_var.set("🔊 Listening...")
        else:
            self.status_var.set("Ready — type or click 🎙️")

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
