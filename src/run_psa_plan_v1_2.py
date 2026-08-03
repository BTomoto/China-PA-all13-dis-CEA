from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "src" / "joint_psa_v1_2.py"
PLAN = ROOT / "input" / "psa" / "PSA_batch_plan_v1.2.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the locked ALLdis PSA batch plan")
    parser.add_argument("--run-type", choices=["SMOKE", "FORMAL"], required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--confirm-final-lock", action="store_true", help="Required for FORMAL after v1.3 deterministic and smoke-test QC")
    return parser.parse_args()


def run_one(row: pd.Series, output_root: Path, formal: bool) -> tuple[int, int, str]:
    batch_id = int(row["batch_id"])
    out = output_root / f"batch_{batch_id:02d}"
    cmd = [
        sys.executable,
        str(RUNNER),
        "--draws", str(int(row["draws"])),
        "--seed", str(int(row["seed"])),
        "--batch-id", str(batch_id),
        "--draw-offset", str(int(row["draw_offset"])),
        "--output-dir", str(out),
    ]
    if formal:
        cmd.append("--formal-run")
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return batch_id, completed.returncode, completed.stdout + completed.stderr


def main() -> None:
    args = parse_args()
    formal = args.run_type == "FORMAL"
    if formal and not args.confirm_final_lock:
        print("FORMAL requires explicit confirmation that v1.3 deterministic and smoke-test QC passed; use --confirm-final-lock.", file=sys.stderr)
        raise SystemExit(2)
    plan = pd.read_csv(PLAN, encoding="utf-8-sig")
    selected = plan.loc[plan["run_type"].eq(args.run_type)].copy()
    output_root = ROOT / ("psa_formal" if formal else "psa_smoke_recheck")
    output_root.mkdir(parents=True, exist_ok=True)
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as pool:
        futures = [pool.submit(run_one, row, output_root, formal) for _, row in selected.iterrows()]
        for future in as_completed(futures):
            batch_id, code, output = future.result()
            print(f"batch {batch_id}: exit={code}")
            if code != 0:
                failures.append((batch_id, output))
    if failures:
        details = "\n".join(f"batch {batch}:\n{output}" for batch, output in failures)
        raise SystemExit(details)
    print(f"Completed {len(selected)} {args.run_type} batches under {output_root}")


if __name__ == "__main__":
    main()
