from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
PSA = ROOT / "input" / "psa"
MERGED = ROOT / "psa_smoke_recheck" / "merged"
OUT = ROOT / "workbook_data_v1.3.json"
OLD_ROOT = ROOT.parent / "ALLdis_正式PSA前参数与试运行_v1.2"


def payload(df: pd.DataFrame) -> dict[str, object]:
    clean = df.copy().astype(object)
    clean = clean.where(pd.notna(clean), None)
    return {"headers": clean.columns.tolist(), "rows": clean.values.tolist()}


def scenario_label(case_id: str) -> str:
    labels = {
        "PRIMARY": "2010—2023趋势衰减（主分析）",
        "D3_RECENT_2018_2023": "2018—2023近期趋势衰减",
        "D3_FIXED_2023_RATE": "2023年率保持不变",
        "D3_CONTINUED": "2010—2023趋势持续外推",
    }
    return labels.get(case_id, case_id)


methods = pd.DataFrame([
    ["D1", "A", "疾病组特异滞后；即时/延后2年结构情景", "READY_STRUCTURAL", "滞后不在PSA内随机化"],
    ["D2", "B", "S0低身体活动趋势三角分布，2034后衰减", "READY", "0.0042/0.0084/0.0126"],
    ["D3", "A", "2010—2023年龄—性别—疾病率趋势；2035—2040逐步衰减", "READY_FINAL_HISTORY", "2018—2023近期趋势、2023率固定、趋势持续为结构敏感性"],
    ["D4", "A", "新发/首次事件×首年直接医疗费用", "PARTIAL", "9个结局有中国证据或显式代理；4个保持缺失"],
    ["D5", "A", "公共支付方净成本", "INTERIM_BRIDGE", "NHSA 2024全国加权支付比例；非病种特异"],
    ["D6", "A", "劳动参与与就业拆分", "INTERFACE_ONLY", "不阻断主PSA"],
    ["D7", "A", "疾病相关生产率损失", "INTERFACE_ONLY", "不使用代理值伪造结果"],
    ["D8", "A", "工资/GDP宏观连接", "INTERFACE_ONLY", "作为卫星分析"],
    ["D9", "A", "完全维持主路径；75%和2034后停止敏感性", "READY_5Y_10Y; INTERIM_26Y", "2035—2050资本更新未完全封库"],
    ["D10", "A", "高血压避免患者年；痴呆长期照护卫星", "PARTIAL_READY", "不与D4首年事件费用混同"],
], columns=["decision", "choice", "locked_method", "current_status", "reporting_boundary"])

d4 = pd.read_csv(PSA / "D4_first_year_cost_parameters_v1.2.csv", encoding="utf-8-sig")
d5 = pd.read_csv(PSA / "D5_public_payer_share_v1.2.csv", encoding="utf-8-sig")
d9 = pd.read_csv(PSA / "D9_horizon_and_renewal_rules_v1.2.csv", encoding="utf-8-sig")
registry = pd.read_csv(PSA / "PSA_parameter_registry_v1.2.csv", encoding="utf-8-sig")
policy = pd.read_csv(PSA / "policy_effect_parameters_v1.2.csv", encoding="utf-8-sig")
rr = pd.read_csv(PSA / "rr_component_parameters_v1.2.csv", encoding="utf-8-sig")
cost = pd.read_csv(PSA / "programme_cost_parameters_v1.2.csv", encoding="utf-8-sig")
summary = pd.read_csv(MERGED / "02_PSA_summary.csv", encoding="utf-8-sig")
ceac = pd.read_csv(MERGED / "03_CEAC.csv", encoding="utf-8-sig")
ceaf = pd.read_csv(MERGED / "04_CEAF.csv", encoding="utf-8-sig")
stability = pd.read_csv(MERGED / "05_batch_stability.csv", encoding="utf-8-sig")
recon = pd.read_csv(MERGED / "06_deterministic_reconciliation.csv", encoding="utf-8-sig")
convergence = pd.read_csv(MERGED / "07_convergence_smoke.csv", encoding="utf-8-sig")
qc = pd.read_csv(MERGED / "00_QC.csv", encoding="utf-8-sig")
manifest = json.loads((MERGED / "MERGED_MANIFEST.json").read_text(encoding="utf-8"))

gbd_qc = pd.read_csv(ROOT / "audit_gbd_update" / "00_GBD更新QC.csv", encoding="utf-8-sig")
det_qc = pd.read_csv(ROOT / "results" / "00_QC.csv", encoding="utf-8-sig")
det_qc.insert(2, "status", det_qc["passed"].map({True: "PASS", False: "FAIL"}))
det_qc = det_qc.rename(columns={"severity": "failure_severity"})
gbd_update = json.loads((ROOT / "audit_gbd_update" / "GBD_UPDATE_SUMMARY.json").read_text(encoding="utf-8"))
gbd_summary = pd.DataFrame([[k, v] for k, v in gbd_update.items()], columns=["item", "value"])

structural = pd.read_csv(ROOT / "results" / "09_S6_structural_sensitivity.csv", encoding="utf-8-sig")
structural = structural.loc[structural["case_id"].isin([
    "PRIMARY", "D3_RECENT_2018_2023", "D3_FIXED_2023_RATE", "D3_CONTINUED"
])].copy()
structural.insert(1, "scenario_label", structural["case_id"].map(scenario_label))

primary = pd.read_csv(ROOT / "results" / "05_primary_horizon_summary.csv", encoding="utf-8-sig")
primary = primary.loc[primary["scenario_id"].eq("S6")].copy()

comparison_rows = []
if OLD_ROOT.exists():
    old = pd.read_csv(OLD_ROOT / "results" / "05_primary_horizon_summary.csv", encoding="utf-8-sig")
    old = old.loc[old["scenario_id"].eq("S6")].copy()
    metrics = [
        ("discounted_dalys_averted", "贴现DALY"),
        ("cumulative_avoided_daly_undiscounted", "未贴现DALY"),
        ("cumulative_avoided_deaths_undiscounted", "避免死亡"),
        ("cumulative_avoided_incidence", "避免新发"),
        ("icer_vs_s0_programme_only_cny_per_daly", "桥接ICER"),
    ]
    for h in [5, 10, 26]:
        nrow = primary.loc[primary["horizon_years"].eq(h)].iloc[0]
        orow = old.loc[old["horizon_years"].eq(h)].iloc[0]
        for field, label in metrics:
            nv, ov = float(nrow[field]), float(orow[field])
            comparison_rows.append([h, label, nv, ov, (nv / ov - 1.0) if ov else None])
comparison = pd.DataFrame(comparison_rows, columns=["horizon_years", "metric", "v1.3_2010_2023", "v1.2_2018_2023", "relative_change"])

smoke_summary = summary.loc[
    summary["scenario_id"].eq("S6")
    & summary["metric"].isin([
        "discounted_dalys_averted",
        "undiscounted_incidence_averted",
        "discounted_programme_cost_2025_cny",
        "discounted_partial_direct_medical_savings_2025_cny",
        "discounted_partial_public_payer_net_cost_2025_cny",
        "programme_only_icer_cny_per_daly",
        "partial_payer_icer_cny_per_daly",
    ])
].copy()

sources = pd.DataFrame([
    ["GBD-2010-2017", "IHME GBD 2023 Results Tool原始ZIP", "2010—2017疾病负担与病例历史补充", "用户提供的3个原始ZIP"],
    ["WPP-2024", "United Nations World Population Prospects 2024", "2010—2023中国年龄—性别人口分母", "https://population.un.org/wpp/"],
    ["D4-IHD", "He et al. Direct Medical Costs of Incident Complications in Newly Diagnosed T2D", "心肌梗死即时增量直接医疗费用；IHD保守下界代理", "https://pmc.ncbi.nlm.nih.gov/articles/PMC7843809/"],
    ["D4-stroke", "CNSR-III one-year direct and indirect costs of ischaemic stroke", "首次缺血性卒中一年直接医疗费用", "https://www.ispor.org/docs/default-source/euro2022/poster-stroke-burden1020clean-pdf.pdf"],
    ["D4-breast", "Liao et al. multicentre breast cancer expenditure", "13省新诊断病程医疗费用", "https://pubmed.ncbi.nlm.nih.gov/28670694/"],
    ["D4-CRC", "China multicentre colorectal cancer expenditure", "新诊断病程直接医疗费用", "https://pmc.ncbi.nlm.nih.gov/articles/PMC5410077/"],
    ["D4-gastric", "Zhang et al. stomach cancer multicentre study", "37家医院新诊断病程；医疗费用占91.2%", "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2020.00310/full"],
    ["D4-oesophageal", "Expenditure and financial burden for common cancers in China", "新诊断病程总直接费用，医疗份额依共同研究推导", "https://www.sciencedirect.com/science/article/abs/pii/S0140673616319377"],
    ["D5", "2024年全国医疗保障事业发展统计公报", "职工/居民住院目录内基金支付比例与参保人数", "https://www.nhsa.gov.cn/art/2025/7/14/art_7_17248.html"],
], columns=["source_id", "citation", "parameter_use", "url"])

data = {
    "metadata": {
        "title": "ALLdis GBD 2010—2023更新与正式PSA候选审计",
        "version": "v1.3",
        "formal_psa_run": False,
        "formal_psa_ready": True,
        "smoke_draws": manifest["draws"],
        "smoke_batches": manifest["batches"],
        "smoke_qc_pass": manifest["qc_pass"],
        "smoke_qc_total": manifest["qc_total"],
        "det_qc_pass": int(det_qc["passed"].sum()),
        "det_qc_total": int(len(det_qc)),
        "gbd_qc_pass": int(gbd_qc["passed"].sum()),
        "gbd_qc_total": int(len(gbd_qc)),
        "gbd_new_rows": int(gbd_update["gbd_new_rows_raw"]),
        "d4_available": int(d4["mean_2025_cny"].notna().sum()),
        "d4_total": int(len(d4)),
        "d5_mean": float(d5.iloc[0]["mean"]),
        "d5_low": float(d5.iloc[0]["approx_95_lower"]),
        "d5_high": float(d5.iloc[0]["approx_95_upper"]),
    },
    "methods": payload(methods),
    "registry": payload(registry),
    "d4": payload(d4),
    "d5": payload(d5),
    "d9": payload(d9),
    "policy": payload(policy),
    "rr": payload(rr),
    "cost": payload(cost),
    "smoke_summary": payload(smoke_summary),
    "ceac": payload(ceac),
    "ceaf": payload(ceaf),
    "stability": payload(stability),
    "recon": payload(recon),
    "convergence": payload(convergence),
    "qc": payload(qc),
    "gbd_qc": payload(gbd_qc),
    "gbd_summary": payload(gbd_summary),
    "det_qc": payload(det_qc),
    "d3_structural": payload(structural),
    "comparison": payload(comparison),
    "sources": payload(sources),
}
OUT.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")
print(OUT)
