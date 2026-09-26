"""Compatibility entry point for downloading and laying out dependencies."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT / 'tools/bootstrap.py'), 'dependencies'], check=True)
subprocess.run([sys.executable, str(ROOT / 'tools/bootstrap.py'), 'materialize'], check=True)
