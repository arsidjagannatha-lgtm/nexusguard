"""
conftest.py — root test configuration for the NexusGuard backend.

Placed at backend/ (one level above tests/) so it is loaded by pytest
before any test module is imported. This guarantees that backend/ is
always on sys.path regardless of which directory pytest is invoked from.

  pytest from backend/     ← standard, works via pytest.ini pythonpath
  pytest from tests/       ← works via this conftest sys.path insert
  pytest from project root ← works via this conftest sys.path insert
"""
import sys
import os

# Ensure backend/ is the first entry on sys.path.
# __file__ is <backend>/conftest.py, so dirname(__file__) is backend/.
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
