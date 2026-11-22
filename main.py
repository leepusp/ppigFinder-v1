#!/usr/bin/env python3
"""Desktop entry point: provide a clear error before importing the legacy GUI."""
import sys
if sys.version_info < (3, 11):
    raise SystemExit(
        f"ppigFinder needs Python 3.11+, but this is {sys.version.split()[0]}. "
        "Activate the project's .venv or install Python 3.11 and run "
        "scripts/install_ppigfinder.sh (Windows: scripts/install_ppigfinder.ps1)."
    )
from ppigfinder.app import main

if __name__ == "__main__":
    raise SystemExit(main())
