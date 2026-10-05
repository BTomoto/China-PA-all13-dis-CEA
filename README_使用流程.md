# 身体活动促进政策分析：Notebook 使用流程

1. 解压 `PA_Integrated_Notebook_20261004.zip`，保留解压后的完整目录结构。
2. 在 Jupyter Notebook 或 JupyterLab 中打开 `PA_Integrated_Analysis/notebooks/PA_study_analysis.ipynb`，选择 Python 3.12 内核。
3. 首次运行如缺少依赖，将安装单元中的 `INSTALL_DEPENDENCIES` 设为 `True`，运行该单元；安装完成后重启内核，再设回 `False`。
4. 从第一个单元开始依次运行整份 Notebook。首次完整运行包含确定性分析、联合概率敏感性分析和经济不确定性分析，耗时可能较长。
5. 结果写入包内的 `outputs/`；运行过程产生的中间文件写入 `work/`。若修改 `data/Public_model_inputs.xlsx`，从头重新运行 Notebook。
