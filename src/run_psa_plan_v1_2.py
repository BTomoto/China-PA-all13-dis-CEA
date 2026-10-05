from __future__ import annotations
from model_io import install as _configure_io
_configure_io()
import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / 'src' / 'joint_psa_v1_2.py'
DATA_ROOT = Path(os.environ.get('ALLDIS_DATA_ROOT', str(ROOT))).resolve()
PSA_INPUT = Path(os.environ.get('ALLDIS_PSA_INPUT_ROOT', str(DATA_ROOT / 'input' / 'psa'))).resolve()
PLAN = PSA_INPUT / 'PSA_batch_plan_binary_v2.0.csv'

def run_one(row: pd.Series, output_root: Path, formal: bool, stroke_mapping: str) -> tuple[int, int, str]:
    batch_id = int(row['batch_id'])
    out = output_root / f'batch_{batch_id:02d}'
    cmd = [sys.executable, str(RUNNER), '--draws', str(int(row['draws'])), '--seed', str(int(row['seed'])), '--batch-id', str(batch_id), '--draw-offset', str(int(row['draw_offset'])), '--output-dir', str(out), '--stroke-mapping', stroke_mapping]
    if formal:
        cmd.append('--formal-run')
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return (batch_id, completed.returncode, completed.stdout + completed.stderr)
