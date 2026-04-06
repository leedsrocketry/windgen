"""Entry point for ``python -m windgen`` or ``python .`` from windgen/."""

import sys
from pathlib import Path

# When invoked as ``python .`` from the windgen/ directory, Python runs
# __main__.py directly without setting up the package.  Add the parent
# directory to sys.path so absolute imports work, then bootstrap the package.
_pkg_dir = Path(__file__).resolve().parent
if _pkg_dir.name == "windgen" and str(_pkg_dir.parent) not in sys.path:
    sys.path.insert(0, str(_pkg_dir.parent))

from windgen.cli import main

main()
