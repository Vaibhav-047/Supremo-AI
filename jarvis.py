"""JARVIS-style GUI frontend for Supremo — the desktop management AI.

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
from supremo import Supremo, Intent


class JarvisApp:
    """JARVIS-style GUI for the Supremo desktop assistant."""

    # --- Theme colors ---
    BG = "#0a0f17"
    PANEL = "#161d2a"
    BORDER = "#2d3748"
    TEXT = "#e5e7eb"
    USER_MSG = "#60a5fa"
    AI_MSG = "#34d399"
    INPUT_BG = "#1e293b"
    GLOW = "#34d399"
    TIMESTAMP = "#64748b"

    def __init__(self, root):
        self.root = root
        self.assistant = Supremo()
        self.setup_ui()
        self.speak("Supremo online. How can I help you?")

    def setup_ui(self):
        root = self.root
        root.title("Supremo — Desktop Management AI")
        root.configure(bg=self.BG)

        # Make it a nice window
        root.geometry("820x560")
        root.minsize(600, 400)
        root.eval("tk::PlaceWindow . center")

        # Custom fonts
        self.font_title = tkfont.Font(family="SF Mono", size=14, weight="bold")
        self.font_chat = tkfont.Font(family="SF Mono", size=11)
        self.font_input = tkfont.Font(family="SF Mono", size=12)
        self.font_ts = tkfont.Font(family="SF Mono", size=9)

        # Header
        header = tk.Frame(root, bg=self.PANEL, height=50, relief="flat",
                          highlightbackground=self.BORDER, highlightthickness=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        header_left = tk.Frame(header, bg=self.PANEL)
        header_left.pack(side="left", padx=16, pady=0, fill="y")

        # Logo dot + name
        dot = tk.Canvas(header_left, width=20, height=20, bg=self.PANEL,
                        highlightthickness=0)
        dot.pack(side="left", padx=(0, 8))
        dot.create_oval(4, 4, 16, 16, fill=self.GLOW, outline=self.GLOW)

        name_label = tk.Label(header_left, text="SUPEREMO", font=self.font_title,
                              fg=self.USER_MSG, bg=self.PANEL)
        name_label.pack(side="left")

        subtitle = tk.Label(header_left, text="Desktop Management AI",
                            font=self.font_ts, fg=self.TIMESTAMP, bg=self.PANEL)
        subtitle.pack(side="left", padx=(8, 0))

        # Status indicator
        status_frame = tk.Frame(header, bg=self.PANEL)
        status_frame.pack(side="right", padx=16)
        self.status_dot = tk.Canvas(status_frame, width=12, height=12,
                                     bg=self.PANEL, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_dot.create_oval(3, 3, 9, 9, fill="#22c55e", outline="#22c55e")
        status_label = tk.Label(status_frame, text="Online", font=self.font_ts,
                                fg="#22c55e", bg=self.PANEL)
        status_label.pack(side="left")

        # Chat area
        chat_container = tk.Frame(root, bg=self.BG)
        chat_container.pack(fill="both", expand=True, padx=16, pady=12)

        self.chat = tkst.ScrolledText(
            chat_container,
            wrap="word",
            font=self.font_chat,
            bg=self.PANEL,
            fg=self.TEXT,
            insertbackground=self.USER_MSG,
            insertwidth=2,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            spacing1=2,
            spacing2=2,
            spacing3=2,
            state="disabled",
        )
        self.chat.pack(fill="both", expand=True, side="left")

        # Custom scrollbar
        scrollbar = tk.Scrollbar(chat_container, orient="vertical",
                                  command=self.chat.yview, width=12)
        scrollbar.pack(fill="y", side="right", padx=(0, 2))
        self.chat.configure(yscrollcommand=scrollbar.set)
        # Style scrollbar
        scrollbar.configure(bg=self.BG, troughcolor=self.BORDER,
                            activebackground=self.GLOW,
                            activerelief="flat")

        # Input area
        input_frame = tk.Frame(root, bg=self.BG)
        input_frame.pack(fill="x", padx=16, pady=12)

        self.input_field = tk.Entry(
            input_frame,
            font=self.font_input,
            bg=self.INPUT_BG,
            fg=self.TEXT,
            insertbackground=self.USER_MSG,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.GLOW,
            width=1,
        )
        self.input_field.pack(fill="x", side="left", padx=(0, 8), expand=True)
        self.input_field.bind("<Return>", self.on_enter)
        self.input_field.focus_set()

        send_btn = tk.Button(
            input_frame,
            text="SEND",
            font=self.font_title,
            bg=self.USER_MSG,
            fg=self.BG,
            activebackground=self.GLOW,
            activeforeground=self.BG,
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=6,
            command=self.on_send,
            cursor="hand2",
        )
        send_btn.pack(side="right")

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready — type a command and press Enter")
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

    def add_message(self, sender, sender_name, message, is_error=False):
        """Add a message to the chat display."""
        current = self.chat.get("1.0", tk.END).strip()
        if current:
            self.chat.configure(state="normal")
            self.chat.insert(tk.END, "\n\n")
            self.chat.configure(state="disabled")

        timestamp = dt.datetime.now().strftime("%H:%M")

        self.chat.configure(state="normal")

        # Message bubble styling
        if sender == "user":
            color = self.USER_MSG
            prefix = "> "
        elif sender == "system":
            color = self.TEXT
            prefix = "· "
        elif sender == "error":
            color = "#f87171"
            prefix = "! "
        else:  # ai
            color = self.AI_MSG
            prefix = "▶ "

        # Sender label
        self.chat.insert(tk.END, f"{prefix}{sender_name}  ", color)
        self.chat.insert(tk.END, f"{timestamp}\n", self.TIMESTAMP)

        # Message content
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

        # Run in background thread
        threading.Thread(target=self.process_command, args=(user_input,), daemon=True).start()

    def process_command(self, request: str):
        """Process a command and display the result."""
        try:
            intent = self.assistant.parse(request)

            # Handle quit specially
            if intent.action == "quit":
                self.add_message("ai", "Supremo", "Going offline. Goodbye!")
                self.speak("Goodbye")
                self.root.after(500, self.root.quit)
                return

            # Capture output by redirecting stdout
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
                self.add_message("ai", "Supremo", output)
                self.speak_response(output)
            else:
                self.add_message("ai", "Supremo", "Done.")

        except Exception as e:
            self.add_message("error", "Error", str(e))

        self.root.after(0, lambda: self.status_var.set("Ready"))

    def speak(self, text: str):
        """Speak text using macOS 'say' command (non-blocking)."""
        try:
            subprocess.run(["say", text], timeout=5)
        except Exception:
            pass

    def speak_response(self, text: str):
        """Extract a short response to speak aloud."""
        # Don't speak long outputs or error messages
        if len(text) > 200:
            return
        if text.startswith("Opening") or text.startswith("Searching"):
            return
        self.speak(text)

    def destroy(self):
        self.root.destroy()


def main():
    if platform.system() != "Darwin":
        print("Supremo's GUI mode currently targets macOS.")
        sys.exit(1)

    root = tk.Tk()
    app = JarvisApp(root)

    # Set window transparency and border
    root.configure(bg=JarvisApp.BG)
    root.option_add("*tearOff", tk.FALSE)

    # Keyboard shortcuts
    root.bind("<Escape>", lambda e: root.quit())

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
