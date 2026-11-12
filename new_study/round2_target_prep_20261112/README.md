# 第二轮审计修订与WHO目标情景数据准备

基于 `67addc23590666461ea065294c382da5a72e7287`，独立分支 `codex/data-round2-target-prep-20261112`。第一轮和第二轮文件原位保留。此处只保存证据、候选接口、审计门槛和下载要求。

主情景配置是**WHO全球“2030年较2010年身体活动不足率相对下降15%”目标在中国的应用**，公式 `p_target_2030 = 0.85 × p_reference_2010`。中国《健康中国2030》与《全民健身计划（2026—2030年）》仅提供政策背景；其“经常参加体育锻炼”指标不同于WHO不足率，不能称其设定了相同的15%数值目标。

先读 [交接报告](reports/HANDOFF_TARGET_PREP.md)、[审计修订说明](reports/AUDIT_REVISION.md) 和 [证据提取记录](reports/EVIDENCE_EXTRACTION.md)。数据接口在 `registers/`；`checks/validation_target_prep.json` 的 `FAIL` 表示证据或方法门槛不通过，并不表示文件检查失败。当前2010与2025口径不可比，故目标数值与达标差额保持空白。

沿用第二轮人口、暴露和GBD候选，不重新录入12,296条GBD。`exposure_crosswalk_ci_v2.csv` 加入原调查CI及共享参数ID；`population_provenance_v2.csv` 指明官方人口原列。`rr_admission_audit_v2.csv` 和 `endpoint_admission_audit_v2.csv` 分开风险证据、暴露接口、结局方法、GBD来源及最终准备状态，撤销同一PIF六结局自动准入。

只有一份新增外部原件：`raw/Jia2018_fulltext.pdf`。本轮RAND报告网页可读但直下返回403，未声称已归档。来源链接、取得日期、SHA256和失败尝试见 `registers/evidence_acquisition_log.csv` 和 `registers/file_manifest_sha256.csv`。IHME下载需用户正常登录；本轮未尝试绕过。

从仓库根目录运行 `python new_study/round2_target_prep_20261112/scripts/build_target_prep.py`，然后 `python new_study/round2_target_prep_20261112/scripts/finalize_target_prep.py`。脚本不运行正式健康模型、费用汇总或PSA。
