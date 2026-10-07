"""
8D Audio — Real-Time Spatial Sound Processor
Main Application Entrypoint.
"""

import os
import sys

# Ensure repository root is on Python sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gui.main_window import run_gui


def main():
    run_gui()


if __name__ == "__main__":
    main()
