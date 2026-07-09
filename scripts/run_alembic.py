"""Run Alembic through its Python CLI entrypoint.

This keeps Docker commands independent from console-script PATH setup.
"""

from __future__ import annotations

import sys

from alembic.config import main


if __name__ == "__main__":
    main(sys.argv[1:])
