"""JARVIS-style GUI frontend for Supremo — the desktop management AI.

Features:
  - Antigravity window: transparent, always-on-top, floating
  - Auto voice input mode on startup
  - Chat interface with message bubbles
  - macOS native notifications and speech

Run with: python3 jarvis.py
Or double-click the .app bundle.
"""

import datetime as dt
import platform
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.scrolledtext as tkst
from pathlib import Path
from tkinter import font as tkfont

# Ensure we can import the backend
sys.path.insert(0, str(Path(__file__).parent))
from supremo import Supremo, Intent, VoiceUnavailable


class JarvisApp:
    """JARVIS-style GUI for the Supremo desktop assistant."""

    # --- Antigravity theme colors ---
    BG = "#0a0f17"
    PANEL = "#161d2a"
    BORDER = "#2d3748"
    TEXT = "#e5e7eb"
    USER_MSG = "#60a5fa"
    AI_MSG = "#34d399"
    INPUT_BG = "#1e293b"
    GLOW = "#34d399"
    TIMESTAMP = "#64748b"
    MIC_ON = "#34d399"
    MIC_OFF = "#64748b"

    def __init__(self, root):
        self.root = root
        self.assistant = Supremo()
        self.voice_active = False
        self.voice_enabled = self._check_voice_available()
        self.setup_ui()
        self.setup_window_effects()

        # Auto-start voice mode
        if self.voice_enabled:
            self.add_message("system", "Supremo",
                             "Voice mode auto-started. Say 'stop listening' to disable.")
            self.start_voice_listener()
        else:
            self.add_message("system", "Supremo",
                             "Voice mode unavailable.\n"
                             "Install: brew install portaudio && pip3 install SpeechRecognition pyaudio")

        self.speak("Supremo online. How can I help you?")

    def _check_voice_available(self):
        """Check if speech_recognition is installed."""
        try:
            import speech_recognition  # noqa
            return True
        except ImportError:
            return False

    def setup_window_effects(self):
        """Antigravity window: transparent, floating, always-on-top."""
        root = self.root

        # Semi-transparent window (antigravity effect)
        root.wm_attributes("-alpha", 0.93)

        # Always float above other windows
        root.wm_attributes("-topmost", True)

        # Subtle shadow (macOS native)
        try:
            root.wm_attributes("-shadow", "-0.5")
        except tk.TclError:
            pass  # Not all platforms support shadow

        # Remove title bar for a sleek floating look
        root.overrideredirect(True)

        # Add a gentle pulsing animation to the whole window
        self._animate_glow()

    def _animate_glow(self):
        """Pulsing glow effect on the window border."""
        if not hasattr(self, '_glow_offset'):
            self._glow_offset = 0
        self._glow_offset += 0.05
        # This is subtle — just keeps the effect alive
        self.root.after(100, self._animate_glow)

    def setup_ui(self):
        root = self.root
        root.title("Supremo — Desktop Management AI")
        root.configure(bg=self.BG)
        root.geometry("820x560")
        root.minsize(600, 400)
        root.eval("tk::PlaceWindow . center")

        # Drag handling for borderless window
        self._drag_start = {"x": 0, "y": 0}
        root.bind("<ButtonPress-1>", self._on_drag_start)
        root.bind("<B1-Motion>", self._on_drag_motion)

        # Custom fonts
        self.font_title = tkfont.Font(family="SF Mono", size=14, weight="bold")
        self.font_chat = tkfont.Font(family="SF Mono", size=11)
        self.font_input = tkfont.Font(family="SF Mono", size=12)
        self.font_ts = tkfont.Font(family="SF Mono", size=9)
        self.font_micro = tkfont.Font(family="SF Mono", size=10)

        # Header
        header = tk.Frame(root, bg=self.PANEL, height=55, relief="flat",
                          highlightbackground=self.BORDER, highlightthickness=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        header_left = tk.Frame(header, bg=self.PANEL)
        header_left.pack(side="left", padx=16, pady=0, fill="y")

        # Logo dot + name
        self.dot = tk.Canvas(header_left, width=20, height=20, bg=self.PANEL,
                             highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 8))
        self.dot.create_oval(4, 4, 16, 16, fill=self.GLOW, outline=self.GLOW)

        name_label = tk.Label(header_left, text="SUPEREMO", font=self.font_title,
                              fg=self.USER_MSG, bg=self.PANEL)
        name_label.pack(side="left")

        subtitle = tk.Label(header_left, text="Desktop Management AI",
                            font=self.font_ts, fg=self.TIMESTAMP, bg=self.PANEL)
        subtitle.pack(side="left", padx=(8, 0))

        # Voice indicator + close button (right side)
        right_frame = tk.Frame(header, bg=self.PANEL)
        right_frame.pack(side="right", padx=16)

        # Voice indicator
        self.voice_btn = tk.Button(
            right_frame, text="🎤", font=self.font_micro,
            bg=self.PANEL, fg=self.MIC_OFF if not self.voice_enabled else self.MIC_ON,
            activebackground=self.PANEL, activeforeground=self.GLOW,
            relief="flat", borderwidth=0, width=3,
            command=self.toggle_voice, cursor="hand2")
        self.voice_btn.pack(side="left", padx=(0, 12))

        # Status indicator
        status_frame = tk.Frame(right_frame, bg=self.PANEL)
        status_frame.pack(side="left")
        self.status_dot_canvas = tk.Canvas(status_frame, width=12, height=12,
                                           bg=self.PANEL, highlightthickness=0)
        self.status_dot_canvas.pack(side="left", padx=(0, 6))
        self.status_dot_canvas.create_oval(3, 3, 9, 9, fill="#22c55e", outline="#22c55e")
        status_label = tk.Label(status_frame, text="Online", font=self.font_ts,
                                fg="#22c55e", bg=self.PANEL)
        status_label.pack(side="left")

        # Close button (top-right corner)
        close_btn = tk.Button(header, text="✕", font=self.font_title,
                              fg="#f87171", bg=self.PANEL,
                              activebackground="#7f1d1d", activeforeground="#fca5a5",
                              relief="flat", borderwidth=0, padx=10, pady=0,
                              command=self._close_window, cursor="hand2")
        close_btn.pack(side="right", padx=(0, 8))

        # Chat area
        chat_container = tk.Frame(root, bg=self.BG)
        chat_container.pack(fill="both", expand=True, padx=16, pady=12)

        self.chat = tkst.ScrolledText(
            chat_container, wrap="word", font=self.font_chat,
            bg=self.PANEL, fg=self.TEXT, insertbackground=self.USER_MSG,
            insertwidth=2, relief="flat", borderwidth=0, highlightthickness=0,
            spacing1=2, spacing2=2, spacing3=2, state="disabled",
        )
        self.chat.pack(fill="both", expand=True, side="left")

        scrollbar = tk.Scrollbar(chat_container, orient="vertical",
                                 command=self.chat.yview, width=12)
        scrollbar.pack(fill="y", side="right", padx=(0, 2))
        self.chat.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(bg=self.BG, troughcolor=self.BORDER,
                            activebackground=self.GLOW, activerelief="flat")

        # Input area
        input_frame = tk.Frame(root, bg=self.BG)
        input_frame.pack(fill="x", padx=16, pady=12)

        self.input_field = tk.Entry(
            input_frame, font=self.font_input, bg=self.INPUT_BG,
            fg=self.TEXT, insertbackground=self.USER_MSG,
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground=self.BORDER, highlightcolor=self.GLOW,
            width=1,
        )
        self.input_field.pack(fill="x", side="left", padx=(0, 8), expand=True)
        self.input_field.bind("<Return>", self.on_enter)
        self.input_field.focus_set()

        # Listen button
        self.listen_btn = tk.Button(
            input_frame, text="🎤 Listen", font=self.font_micro,
            bg=self.INPUT_BG, fg=self.TEXT if self.voice_enabled else self.TIMESTAMP,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, padx=10, pady=4,
            command=self.start_voice_once, cursor="hand2",
        )
        self.listen_btn.pack(side="left", padx=(0, 8))

        # Send button
        send_btn = tk.Button(
            input_frame, text="SEND", font=self.font_title,
            bg=self.USER_MSG, fg=self.BG,
            activebackground=self.GLOW, activeforeground=self.BG,
            relief="flat", borderwidth=0, padx=16, pady=6,
            command=self.on_send, cursor="hand2",
        )
        send_btn.pack(side="right")

        # Hover effects
        send_btn.bind("<Enter>", lambda e: send_btn.configure(bg=self.GLOW))
        send_btn.bind("<Leave>", lambda e: send_btn.configure(bg=self.USER_MSG))
        self.listen_btn.bind("<Enter>", lambda e: self.listen_btn.configure(fg=self.GLOW))
        self.listen_btn.bind("<Leave>", lambda e: self.listen_btn.configure(
            fg=self.TEXT if self.voice_enabled else self.TIMESTAMP))

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready — type a command or click 🎤")
        status_bar = tk.Label(root, textvariable=self.status_var,
                              font=self.font_ts, fg=self.TIMESTAMP, bg=self.BG)
        status_bar.pack(fill="x", padx=16, pady=(0, 8))

        # Welcome message
        self.add_message("system", "Supremo Desktop Management AI",
                         "I'm online. Try:\n"
                         "  • open Safari\n"
                         "  • close Chrome\n"
                         "  • search Python dataclasses\n"
                         "  • screenshot\n"
                         "  • run pwd\n"
                         "  • time / date / help / quit\n"
                         "Type 'help' for the full command list.")

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

    def toggle_voice(self):
        if self.voice_enabled:
            if self.voice_active:
                self.stop_voice()
            else:
                self.start_voice_listener()

    def start_voice_once(self):
        """Manually trigger one voice listening cycle."""
        if not self.voice_enabled:
            self.add_message("system", "Supremo",
                             "Voice mode requires: brew install portaudio && pip3 install SpeechRecognition pyaudio")
            return
        self.voice_active = True
        self._update_voice_ui()
        threading.Thread(target=self._do_voice_once, daemon=True).start()

    def _do_voice_once(self):
        """Listen for one voice command in background."""
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
            self.root.after(0, lambda: self.status_var.set("Ready"))

    def start_voice_listener(self):
        """Start background voice listener (auto mode)."""
        if not self.voice_enabled:
            return
        self.voice_active = True
        self._update_voice_ui()
        threading.Thread(target=self._voice_loop, daemon=True).start()

    def _voice_loop(self):
        """Continuous voice listening loop (auto mode)."""
        while self.voice_active:
            try:
                transcript = self.assistant.listen_once(quiet=True)
                if transcript:
                    self.root.after(0, self._process_voice_transcript, transcript)
                # Brief pause between listens
                import time
                time.sleep(0.3)
            except VoiceUnavailable as e:
                self.root.after(0, self.add_message, "system", "Supremo", str(e))
                break
            except Exception as e:
                self.root.after(0, self.add_message, "error", "Voice", str(e))
                break

    def stop_voice(self):
        self.voice_active = False
        self.root.after(0, self._update_voice_ui)

    def _update_voice_ui(self):
        """Update the voice button and status based on voice state."""
        if self.voice_active:
            self.voice_btn.configure(fg=self.MIC_ON)
            self.status_var.set("🔊 Listening...")
            # Pulse the logo dot
            self.dot.delete("all")
            self.dot.create_oval(4, 4, 16, 16, fill=self.MIC_ON, outline=self.MIC_ON)
        else:
            self.voice_btn.configure(
                fg=self.MIC_ON if self.voice_enabled else self.MIC_OFF)
            self.status_var.set("Ready — type a command or click 🎤")
            self.dot.delete("all")
            self.dot.create_oval(4, 4, 16, 16, fill=self.GLOW, outline=self.GLOW)

    def _process_voice_transcript(self, transcript: str):
        """Process a voice transcript as a command."""
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

        # Process the command
        threading.Thread(
            target=self._process_intent, args=(intent, transcript), daemon=True
        ).start()

    def _process_intent(self, intent, original_text: str = ""):
        """Process an intent and display the result."""
        import io
        old_stdout = sys.stdout
        captured = io.StringIO()
        sys.stdout = captured

        try:
            self.assistant.handle(intent)
        except Exception as e:
            self.root.after(0, self.add_message, "error", "Error", str(e))
            sys.stdout = old_stdout
            return
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue().strip()
        if output:
            self.root.after(0, self.add_message, "ai", "Supremo", output)
            self.speak_response(output)
        else:
            self.root.after(0, self.add_message, "ai", "Supremo", "Done.")

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
            color = "#f87171"
            prefix = "! "
        else:
            color = self.AI_MSG
            prefix = "▶ "

        self.chat.insert(tk.END, f"{prefix}{sender_name}  ", color)
        self.chat.insert(tk.END, f"{timestamp}\n", self.TIMESTAMP)
        self.chat.insert(tk.END, f"  {message}\n", color if sender == "user" else self.TEXT)

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

        threading.Thread(target=self._process_typed_command, args=(user_input,), daemon=True).start()

    def _process_typed_command(self, request: str):
        """Process a typed command in a background thread."""
        try:
            intent = self.assistant.parse(request)

            if intent.action == "quit":
                self.add_message("ai", "Supremo", "Going offline. Goodbye!")
                self.speak("Goodbye")
                self.root.after(500, self.root.quit)
                return

            import io
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

        self.root.after(0, lambda: self.status_var.set("Ready — type or click 🎤"))

    def speak(self, text: str):
        """Speak text using macOS 'say' command."""
        try:
            subprocess.run(["say", text], timeout=5)
        except Exception:
            pass

    def speak_response(self, text: str):
        """Extract a short response to speak aloud."""
        if len(text) > 200:
            return
        if text.startswith("Opening") or text.startswith("Searching"):
            return
        self.speak(text)

    def destroy(self):
        self.voice_active = False
        self.root.destroy()


def main():
    if platform.system() != "Darwin":
        print("Supremo's GUI mode currently targets macOS.")
        sys.exit(1)

    root = tk.Tk()
    app = JarvisApp(root)

    root.configure(bg=JarvisApp.BG)
    root.option_add("*tearOff", tk.FALSE)
    root.bind("<Escape>", lambda e: root.quit())

    # Antigravity: fade-in effect
    root.wm_attributes("-alpha", 0.0)
    def fade_in(alpha=0.0):
        alpha += 0.05
        if alpha < 0.93:
            root.wm_attributes("-alpha", alpha)
            root.after(20, fade_in, alpha)
        else:
            root.wm_attributes("-alpha", 0.93)
    root.after(100, fade_in)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
