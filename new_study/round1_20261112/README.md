# 中国成年人身体活动改善研究：第一轮数据整理

日期：2026-11-12。分支：`codex/data-round1-20261112`。基于远程默认分支 `initial-project-import` 的 `83b6e50b8d5f0321c2d5c3c312d2a58988e55a0b`。`main` 指向另一个旧提交，未改动。交接 bundle 为依赖上述提交的增量包，HEAD `9c588948dba52f332c6ff23c90a418103c5b456b`，仅读取，未直接合入（其目录搬移不符合本轮保留原位要求）。

本目录只保存来源、候选输入和核验。没有健康模型、政策成本、CEA 或正式结果。来源核验不代表研究准入；RR/费用保持 HOLD。Work 负责研究方案和争议参数决策。

## 从哪里接手

1. 先读 [交接报告](reports/HANDOFF.md) 和 [执行缺口](registers/actionable_gaps.csv)。
2. [52行病种×结局表](registers/disease_endpoint_availability.csv) 记录候选是否存在、2018—2023原件核验、定义疑点；`candidate_rows=0` 是行数，绝非疾病数值为零。卒中三亚型见逐行表；高血压患病率候选另存，不能冒称GBD导出。
3. [来源登记](registers/source_registry.csv)、[下载尝试](registers/download_attempts.csv)、[文件SHA256](registers/file_manifest.csv) 与 [原交接包哈希](registers/handoff_packages.csv) 联合追溯。取得日期为本轮接收/下载日期；原下载日期未知则留空，不以 ZIP 时间冒充。
4. `raw/` 是本轮实际下载原件。`handoff/continuation/` 是交接版新研究目录的原样快照，`handoff/supplement/` 是补充包原样快照；其内部历史README和旧检查路径只作证据，不是本轮运行入口。两个相同XLSX保留各自交接位置，默认候选来源为 continuation；补充包新增 RR 来源 JSON 单独引用。见 [重复清单](registers/duplicate_files.csv)。E盘三份原交接文件、bundle及完整旧目录不重复上传。
5. `candidate_inputs/` 是扁平 CSV 接口。`*_legacy.csv` 全部只是旧候选；`pa_2018_published_verified.csv` 是核对原表的18条年龄性别观察；`population_UN_official_china_2024_2050.csv` 是联合国原CSV的中国摘录。原单位与列名保留，缺失不补0，不进行参数准入或正式投影。

## 关键核验

- Gao2018六粗龄组×三性别（含合计）18条，按保存的Table2图逐项核对率/CI。2018→2025细年龄组计算文件未找到，22条2025率仍为旧派生候选。`psa_precision_n`不得当全国样本量。
- 官方联合国2025年20+五岁组总人口为 **1,113,252,964** 人；旧WPP年末平均法为 **1,113,252,959** 人，仅差5人；旧基线为 **1,063,188,925** 人。官方值与旧基线差 **50,064,039** 人。原先50,064,034差额不是年中/年末转换可解释的误差；旧基线的上游来源仍未找回。未替用户选唯一分母。
- 23,580条GBD候选独立与4个原ZIP对照：12,296条数值与上下界匹配；1,216条部分核验（包括70+均值和32条区间方法差异）；10,068条缺少可匹配原件。四个缺失ZIP仍未恢复。`gbd_row_comparison.csv` 区分声明源和实际匹配源。
- Katzmarzyk Table1可定位旧15组件中的14个数值，痴呆1.40与表中1.32不符；14个包含旧卒中亚型复用同一数值的情况，不等于疾病定义相容。新研究没有任何组件因此自动准入。

## 检查与重跑

从仓库根目录运行 `python new_study/round1_20261112/scripts/audit_round1.py`（Python3.11+，只用标准库）。输出 `checks/validation.json`、保留原文件检查、逐行核验、52行表和SHA256清单。脚本只读来源并写审计文件，没有健康模型入口。

下载脚本是独立操作，不在审计时联网重下。`collect_pmc_cloud.py` 需要pypdf；使用PMC官方公开云数据接口（见raw/metadata/PMC_cloud_README.txt）。对下载中转/验证页不执行挑战，不把HTML当PDF。文献全文若仅有HTML或XML，按实际格式交接。保存的是2026-11-12快照，不声称是此后最新版本；原作者、期刊、PMC/NLM、联合国等署名和原许可保留。

本轮不改写交接版31表XLSX，避免CSV与旧簿看似同步。新核验以本目录registers为准，旧簿只作候选历史快照。后续应先核准数据，再经授权生成新的正式输入簿。

原文XML表格的逐格摘录见 `candidate_inputs/published_table_cells.csv`，保留表号、行列及合并格跨度。它是来源文字转存，不是统一单位后的模型参数。PMC原文版次、DOI、许可见各目录JSON；补表未出现在公开目录时保持缺失。
