"""Entry point for Supremo — the desktop management AI.

GUI mode (default):  python3 main.py
CLI mode:            python3 main.py --cli
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from supremo import main as cli_main
from jarvis import main as gui_main


if __name__ == "__main__":
    if "--cli" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--cli"]
        cli_main()
    else:
        gui_main()
