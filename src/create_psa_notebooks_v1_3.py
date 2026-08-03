from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS = ROOT / "notebooks"
SMOKE = ROOT / "psa_smoke_recheck" / "merged"


def lines(text: str) -> list[str]:
    return text.splitlines(keepends=True) or [""]


def markdown(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": lines(text)}


def code(source: str, execution_count: int | None = None, outputs: list[dict] | None = None) -> dict:
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "metadata": {},
        "outputs": outputs or [],
        "source": lines(source),
    }


def stream(text: str) -> dict:
    return {"name": "stdout", "output_type": "stream", "text": lines(text)}


def display(df: pd.DataFrame) -> dict:
    return {
        "output_type": "display_data",
        "metadata": {},
        "data": {
            "text/plain": lines(df.to_string(index=False)),
            "text/html": lines(df.to_html(index=False, border=0)),
        },
    }


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_smoke_notebook() -> None:
    manifest = json.loads((SMOKE / "MERGED_MANIFEST.json").read_text(encoding="utf-8"))
    qc = pd.read_csv(SMOKE / "00_QC.csv", encoding="utf-8-sig")
    recon = pd.read_csv(SMOKE / "06_deterministic_reconciliation.csv", encoding="utf-8-sig")
    summary = pd.read_csv(SMOKE / "02_PSA_summary.csv", encoding="utf-8-sig")
    metrics = [
        "discounted_dalys_averted",
        "discounted_programme_cost_2025_cny",
        "discounted_partial_public_payer_net_cost_2025_cny",
    ]
    s6 = summary.loc[
        summary["scenario_id"].eq("S6") & summary["metric"].isin(metrics),
        ["horizon_years", "metric", "mean", "p2_5", "median", "p97_5", "result_status"],
    ]
    cells = [
        markdown(
            "# ALLdis GBD 2010—2023更新后联合PSA烟雾测试审计 v1.3\n\n"
            "本Notebook记录2批×100次技术烟雾测试。所有区间仅用于验证引擎，不能作为论文正式概率性结果。"
        ),
        code(
            "from pathlib import Path\nimport json\nimport pandas as pd\n\n"
            "HERE = Path.cwd().resolve()\nROOT = HERE if (HERE / 'input' / 'psa').exists() else HERE.parent\n"
            "MERGED = ROOT / 'psa_smoke_recheck' / 'merged'\nprint('Bundle root:', ROOT)",
            1,
            [stream(f"Bundle root: {ROOT}\n")],
        ),
        markdown("## 1. 自动质量控制"),
        code(
            "manifest = json.loads((MERGED / 'MERGED_MANIFEST.json').read_text(encoding='utf-8'))\n"
            "qc = pd.read_csv(MERGED / '00_QC.csv')\nprint(manifest)\ndisplay(qc)\n"
            "assert manifest['formal_psa_run'] is False\nassert (qc['status'] == 'PASS').all()",
            2,
            [stream(json.dumps(manifest, ensure_ascii=False) + "\n"), display(qc)],
        ),
        markdown("## 2. 与确定性结果衔接"),
        code(
            "recon = pd.read_csv(MERGED / '06_deterministic_reconciliation.csv')\n"
            "display(recon)\nassert (recon['qc_status'] == 'PASS').all()",
            3,
            [display(recon)],
        ),
        markdown("## 3. S6技术性区间"),
        code(
            "summary = pd.read_csv(MERGED / '02_PSA_summary.csv')\n"
            "metrics = ['discounted_dalys_averted','discounted_programme_cost_2025_cny','discounted_partial_public_payer_net_cost_2025_cny']\n"
            "s6 = summary[(summary.scenario_id == 'S6') & summary.metric.isin(metrics)]\n"
            "display(s6[['horizon_years','metric','mean','p2_5','median','p97_5','result_status']])",
            4,
            [display(s6)],
        ),
        markdown(
            "## 4. 结论\n\n"
            "GBD趋势、政策效果、成本、RR、身体活动基线、D4费用和D5支付比例均已进入抽样；"
            "20/20项烟雾测试QC通过后，可使用独立的正式运行Notebook执行10,000次PSA。"
        ),
    ]
    path = NOTEBOOKS / "02_联合PSA烟雾测试审计_v1.3.ipynb"
    path.write_text(json.dumps(notebook(cells), ensure_ascii=False, indent=1), encoding="utf-8")


def build_formal_notebook() -> None:
    cells = [
        markdown(
            "# ALLdis正式10,000次联合PSA运行 v1.3\n\n"
            "本Notebook是正式运行入口。执行“全部运行”将先检查GBD接入、确定性模型和2×100次烟雾测试，"
            "随后运行20批×500次PSA，并自动合并和审计结果。不要同时打开多个正式运行进程。"
        ),
        code(
            "from pathlib import Path\nimport json\nimport subprocess\nimport sys\nimport pandas as pd\n\n"
            "HERE = Path.cwd().resolve()\nROOT = HERE if (HERE / 'input' / 'psa').exists() else HERE.parent\n"
            "print('Bundle root:', ROOT)",
        ),
        markdown("## 1. 正式运行前自动检查"),
        code(
            "gbd_qc = pd.read_csv(ROOT / 'audit_gbd_update' / '00_GBD更新QC.csv')\n"
            "det_qc = pd.read_csv(ROOT / 'results' / '00_QC.csv')\n"
            "smoke_qc = pd.read_csv(ROOT / 'psa_smoke_recheck' / 'merged' / '00_QC.csv')\n"
            "smoke_manifest = json.loads((ROOT / 'psa_smoke_recheck' / 'merged' / 'MERGED_MANIFEST.json').read_text(encoding='utf-8'))\n"
            "psa_manifest = json.loads((ROOT / 'input' / 'psa' / 'PSA_INPUT_MANIFEST_v1.2.json').read_text(encoding='utf-8'))\n\n"
            "assert (gbd_qc['status'] == 'PASS').all(), 'GBD update QC failed'\n"
            "assert det_qc['passed'].all(), 'Deterministic QC failed'\n"
            "assert (smoke_qc['status'] == 'PASS').all(), 'Smoke-test QC failed'\n"
            "assert smoke_manifest['draws'] == 200 and not smoke_manifest['formal_psa_run']\n"
            "assert psa_manifest['gbd_status'] == 'GBD_2010_2023_FINAL_HISTORY_LOCKED'\n"
            "print(f\"Preflight passed: GBD {len(gbd_qc)}/{len(gbd_qc)}, deterministic {len(det_qc)}/{len(det_qc)}, smoke {len(smoke_qc)}/{len(smoke_qc)}\")",
        ),
        markdown("## 2. 运行20批×500次PSA"),
        code(
            "RUN_FORMAL = True\nWORKERS = 2\n\n"
            "if not RUN_FORMAL:\n"
            "    raise RuntimeError('RUN_FORMAL must remain True in the dedicated formal-run notebook.')\n"
            "run_cmd = [sys.executable, str(ROOT / 'src' / 'run_psa_plan_v1_2.py'), '--run-type', 'FORMAL', '--workers', str(WORKERS), '--confirm-final-lock']\n"
            "subprocess.run(run_cmd, cwd=ROOT, check=True)\n"
            "print('All 20 formal batches completed.')",
        ),
        markdown("## 3. 合并正式结果并运行自动QC"),
        code(
            "merge_cmd = [sys.executable, str(ROOT / 'src' / 'merge_and_qc_psa_v1_2.py'), '--input-root', str(ROOT / 'psa_formal'), '--output-dir', str(ROOT / 'psa_formal' / 'merged'), '--formal']\n"
            "subprocess.run(merge_cmd, cwd=ROOT, check=True)\n"
            "formal_manifest = json.loads((ROOT / 'psa_formal' / 'merged' / 'MERGED_MANIFEST.json').read_text(encoding='utf-8'))\n"
            "formal_qc = pd.read_csv(ROOT / 'psa_formal' / 'merged' / '00_QC.csv')\n"
            "display(formal_qc)\nprint(formal_manifest)\n"
            "assert formal_manifest['formal_psa_run'] is True\n"
            "assert formal_manifest['draws'] == 10000\n"
            "assert (formal_qc['status'] == 'PASS').all()",
        ),
        markdown(
            "## 4. 上传内容\n\n"
            "运行结束后，将整个`psa_formal`文件夹压缩为ZIP并上传。"
            "不要只上传图片；正式审计需要`merged`和20个批次目录。"
        ),
    ]
    path = NOTEBOOKS / "03_正式10000次PSA运行_v1.3.ipynb"
    path.write_text(json.dumps(notebook(cells), ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    build_smoke_notebook()
    build_formal_notebook()
    print(NOTEBOOKS)


if __name__ == "__main__":
    main()
