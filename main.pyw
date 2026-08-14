"""PB Dev Helper — PowerBuilder 10/2025 Development Assistant.

A GUI tool for browsing and exporting PowerBuilder PBL files to SR text files,
enabling modern VSCode editing workflows.

Usage:
    python main.py
"""

import sys
import os

# Ensure project root is on path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import PBDevHelperApp


def main():
    app = PBDevHelperApp()
    app.run()


if __name__ == "__main__":
    main()
