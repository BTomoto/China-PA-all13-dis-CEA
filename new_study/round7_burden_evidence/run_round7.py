"""Offline, reproducible Round 7 evidence and partially identified CRA analysis."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from src.pipeline import build,execute_notebooks,finalize
if __name__=='__main__':
    build()
    if '--execute-notebooks' in sys.argv:execute_notebooks()
    finalize()
