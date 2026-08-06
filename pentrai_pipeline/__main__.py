"""Entry point so the pipeline can be run as `python -m pentrai_pipeline ...`."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
