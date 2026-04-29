"""Compatibility launcher for the packaged H-1B wage dashboard."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wage_dashboard.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
