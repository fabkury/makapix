"""Add the parent dir to sys.path so tests can import from generate_report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
