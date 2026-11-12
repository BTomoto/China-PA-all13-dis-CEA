# 第二轮：Work v1 口径与候选输入接口

分支 `codex/data-round2-20261112`；基于第一轮提交 `94e893ab90bfab75866eeff19d501afdf76739b4`。本目录独立保存第二轮生成物，第一轮及旧研究原文件不改动。本轮只生成可审计的数据和准入接口，没有运行正式健康、费用或 PSA 模型。

## 接手顺序

1. 阅读 [`reports/HANDOFF_ROUND2.md`](reports/HANDOFF_ROUND2.md) 和 [`reports/WORK_DECISIONS_IMPLEMENTATION.md`](reports/WORK_DECISIONS_IMPLEMENTATION.md)。
2. 人口主输入为 `registers/population_input_whitelist_v1.csv`（2025—2050，男/女×20—24至100+，人，7月1日）；2018年龄衔接为 `pa_age_crosswalk_v1.csv`；2025模型起点为 `pa_2025_model_baseline_v1.csv`。该起点是 `modelled_2025_baseline_using_2018_observed_rates`，不是2025年实测率。
3. `rr_admission_work_v1.csv` 记录风险证据准入；`disease_endpoint_admission_work_v1.csv` 记录六结局应用口径；`gbd_input_whitelist_v1.csv` 只列第一轮与原ZIP逐值相符的12,296条 **Number 候选**，但每条的 `model_admission` 仍为 `HOLD_RATE_AND_ENDPOINT_GATE`。来源核验不等于模型准入。`gbd_endpoint_source_gate_v1.csv` 记录各病种结局的近年来源门槛。
4. GBD四组缺失原件的精确查询条件在 `gbd_download_requirements_v2.csv`；具体可执行缺口在 `round2_actionable_gaps.csv`。需用户自行通过正常IHME账号下载时，保留原文件、查询截图/条件、citation、取得时点与SHA256，然后逐行复核。本轮没有恢复这些原件，也没有绕过登录。
5. 费用接口是证据要求和量纲/重复费用规则，所有既有费用候选仍是 `NOT_ESTIMATED`，不可直接相乘或求和。

## 重建与检查

从仓库根目录执行 `python new_study/round2_20261112/scripts/build_round2.py`。脚本仅读取第一轮候选与证据，写本目录登记表和 `checks/validation_round2.json`，不访问网络、不运行健康模型。每次重建后执行 `python new_study/round2_20261112/scripts/finalize_round2.py` 更新SHA256清单与检查报告。`checks/validation_round2.json` 记录数据断言；Git保留检查另在交接报告中列出。

原始来源、版本/下载日期、适用人群和SHA256继续见第一轮 `registers/source_registry.csv`、`registers/file_manifest.csv`；第二轮生成文件的哈希见本目录 `registers/file_manifest_sha256_v2.csv`。本轮无新增外部原件。
