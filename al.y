"""Supremo configuration.

Tweak these values to customize assistant behavior without editing super.py.
"""

import os

# --- App aliases: maps spoken/typed names to macOS app names ---
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

# --- Commands that are always blocked from execution ---
BLOCKED_COMMANDS = {
    "sudo", "su", "shutdown", "reboot", "halt", "mkfs", "diskutil",
    "launchctl", "kill", "killall", "crontab", "dscl", "rm", "dd",
    "chmod", "chown", "mv", "eval", "exec",
}

# --- Polite prefixes/suffixes to strip before parsing ---
POLITE_PREFIXES = ("please ", "can you ", "could you ", "would you ")
POLITE_SUFFIXES = (" please",)

# --- Voice settings ---
LISTEN_TIMEOUT = 6   # seconds to wait for speech to start
PHRASE_LIMIT = 10    # max seconds for a single spoken command

# --- File search limits ---
MAX_SEARCH_RESULTS = 20
MAX_SCREENSHOTS = 50  # keep at most this many screenshots on Desktop

# --- Paths ---
DESKTOP_DIR = os.path.expanduser("~/Desktop")

print("Configuration loaded. All settings applied.")
