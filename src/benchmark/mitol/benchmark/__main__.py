"""Allow ``python -m mitol.benchmark``, which is how backends invoke a step."""

import sys

from mitol.benchmark.cli import main

sys.exit(main())
