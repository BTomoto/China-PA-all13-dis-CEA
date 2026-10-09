"""Plain input/output with the original CSV float parsing retained."""
from pathlib import Path
import os
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_read_csv = pd.read_csv
_installed = False


def plain_bytes(path):
    return Path(path).read_bytes()


def read_text(path):
    return Path(path).read_text(encoding='utf-8-sig')


def _read(path, *args, **kwargs):
    if isinstance(path, (str, os.PathLike)):
        try:
            rel = Path(path).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            rel = ''
        if rel.startswith(('input/', 'config/')) and not rel.startswith('input/psa/'):
            kwargs.setdefault('float_precision', 'round_trip')
    return _read_csv(path, *args, **kwargs)


def install():
    global _installed
    if not _installed:
        pd.read_csv = _read
        _installed = True
