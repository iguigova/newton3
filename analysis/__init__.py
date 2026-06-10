"""Audits and benchmarks over the product (`src/newton`).

These run like the tests do — against real data or baselines. Importing the
package puts `src/` on the path, so audits `import newton` whether run via
`python -m analysis.<module>` or under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
