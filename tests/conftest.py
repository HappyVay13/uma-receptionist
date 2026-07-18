from __future__ import annotations

import os
import sys
from pathlib import Path

# The production application intentionally fails closed when DATABASE_URL is absent.
# Unit tests replace the imported engine with isolated temporary databases, so provide
# a harmless in-memory default only for test collection. A caller-supplied URL wins.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("PULSE_RECEPTIONIST_WORKER_ENABLED", "false")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
