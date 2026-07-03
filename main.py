"""Root ASGI entrypoint for local uvicorn runs.

Allows:
    uvicorn main:app --reload
from the repository root.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "medivend_source" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from medivend_source.backend.main import app

