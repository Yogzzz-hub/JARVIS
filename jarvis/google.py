"""Entrypoint for python -m jarvis.google CLI commands."""
from __future__ import annotations

import sys
from jarvis.integrations.google.cli import main

if __name__ == "__main__":
    sys.exit(main())
