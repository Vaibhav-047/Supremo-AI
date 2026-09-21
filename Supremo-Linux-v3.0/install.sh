#!/bin/bash
echo "Installing Supremo dependencies..."
pip3 install -r requirements.txt
echo "Done! Run with:"
echo "  python3 main.py        # GUI mode"
echo "  python3 main.py --cli  # CLI mode"
