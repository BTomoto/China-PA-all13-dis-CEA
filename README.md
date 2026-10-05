# China physical activity policy cost-effectiveness analysis

Analysis code and accompanying results for physical activity promotion policies among Chinese adults aged 20 years or older, covering 13 disease groups.

## Run the analysis

1. Download the repository and extract the complete folder.
2. Use Python 3.12 with Jupyter Notebook or JupyterLab.
3. Open `notebooks/PA_study_analysis.ipynb`.
4. If dependencies are missing, set `INSTALL_DEPENDENCIES = True` in the installation cell and run it. Restart the kernel and reset the option to `False`.
5. Run the notebook from the first cell to the last. The workflow includes deterministic analysis, 10,000-draw joint probabilistic sensitivity analysis, economic analysis, and table and figure export.

Keep the folder structure intact. After changing the Excel workbook, restart the kernel and rerun the notebook from the beginning. Chinese instructions are in [README_使用流程.md](README_使用流程.md).

## Files

| Path | Purpose |
|---|---|
| `notebooks/PA_study_analysis.ipynb` | Single analysis entry point |
| `data/Public_model_inputs.xlsx` | Workbook read at the start of the analysis |
| `data/input_schema.json` | Mapping of 27 workbook tables to computational inputs |
| `src/` | Model, input/output, reporting, and plotting modules |
| `reference/` | Manuscript table records and model diagram |
| `outputs/` | Supplied analysis results and regenerated tables and figures |
| `work/` | Intermediate files created during execution |

The workbook's `身体活动水平` sheet contains manuscript descriptive values. It is loaded into `excel_tables` but is not among the 27 computational input tables. Model calculations use the existing physical activity resources loaded by `src/aggregate_inputs.py`. See [data and licensing notes](DATA_AND_LICENSES.md).

## Version and verification

This repository snapshot corresponds to the uploaded `PA_Integrated_Notebook_20261004(1).zip`, synchronized on 2026-10-05. Analysis code, inputs, random seeds, and supplied outputs are retained from that archive. Syntax and input-loading checks were performed during synchronization; the full model and probability analyses were not rerun. Existing manuscript comparison records remain in `outputs/verification/`.
