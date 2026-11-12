"""Create pilot outputs, notebooks, succinct requirements, tests and hashes."""
from __future__ import annotations
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import health_pilot as hp
from dynamic_outcomes import DiseaseTransitions, TransitionParametersMissing, cohort_outcomes

HERE = Path(__file__).resolve().parent


def notebook(title, source):
    cells = [{"cell_type":"markdown","metadata":{},"source":[f"# {title}\n"]}]
    for text in source:
        cells.append({"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":[line+"\n" for line in text.splitlines()]})
    return {"cells":cells,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"}},"nbformat":4,"nbformat_minor":5}


def write_notebooks():
    specs = [
        ("01_scenario_population.ipynb","Scenario and WPP population",["from health_pilot import scenario_rows, write_csv, HERE\nrows = scenario_rows()\nwrite_csv(HERE/'inputs'/'scenario_age_sex_2025_2050.csv', rows)\nprint(len(rows), sum(x['population'] for x in rows if x['year']==2025))"]),
        ("02_gbd_input_validation.ipynb","GBD 2023 source validation",["from health_pilot import copy_and_describe_raw, validated_rates\nraw = copy_and_describe_raw()\nrates, numbers, selected = validated_rates(raw)\nprint(len(raw),len(selected),len(rates),len(numbers))"]),
        ("03_incidence_pif_pilot.ipynb","IHD and ischemic stroke incidence PIF",["from health_pilot import main, read_csv, HERE\ndetail = main()\nsummary = read_csv(HERE/'results'/'incidence_summary.csv')\nprint(len(detail))\nprint([r for r in summary if r['period_type']=='cumulative_2025_2050'])"]),
        ("04_dynamic_outcome_model_scaffold.ipynb","Dynamic outcomes: blocked parameters",["from dynamic_outcomes import DiseaseTransitions, TransitionParametersMissing, cohort_outcomes\ntry:\n    cohort_outcomes(1.0, DiseaseTransitions())\nexcept TransitionParametersMissing as exc:\n    print(exc)"]),
        ("05_results_reconciliation.ipynb","Reconciliation tests",["import subprocess, sys\np = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],check=True)\nprint('Tests passed')"]),
    ]
    for name,title,codes in specs:
        (HERE/name).write_text(json.dumps(notebook(title,codes),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def write_documents():
    hp.write_csv(HERE/"transition_parameters_required.csv",[
        dict(parameter="incidence_rate",potential_GBD_calibration="2023 age-sex Incidence Rate; AVAILABLE",external_evidence="",status="PILOT_INPUT",use="Entry only"),
        dict(parameter="baseline_prevalence",potential_GBD_calibration="2023 age-sex Prevalence Number/Rate; source absent",external_evidence="",status="BLOCKED",use="Calibration constraint, not transition probability"),
        dict(parameter="disease_survival_by_duration",potential_GBD_calibration="Incidence/Prevalence/Deaths jointly constrain",external_evidence="Survival cohort or registry evidence",status="BLOCKED",use="Avoided prevalent patient-years"),
        dict(parameter="remission_and_recurrence",potential_GBD_calibration="Incidence/Prevalence can constrain",external_evidence="Disease natural history and recurrence literature",status="BLOCKED",use="Disease state transitions"),
        dict(parameter="excess_mortality_by_age_duration",potential_GBD_calibration="Deaths/Prevalence is a descriptive candidate ratio",external_evidence="Cause-specific survival and competing-risk literature",status="BLOCKED",use="Avoided disease deaths"),
        dict(parameter="YLD_per_disease_state",potential_GBD_calibration="YLD/Prevalence is a descriptive candidate ratio",external_evidence="Severity distribution and disability-weight evidence",status="BLOCKED",use="Avoided YLD"),
        dict(parameter="life_years_lost_by_death_age",potential_GBD_calibration="YLL/Deaths is a descriptive candidate ratio",external_evidence="GBD standard life table and death-age mapping",status="BLOCKED",use="Avoided YLL"),
    ])
    causes=[
        ("IHD","PILOT_READY","2023 verified incidence Rate; dynamic endpoints blocked","Survival and duration parameters for dynamic outcomes"),
        ("ischemic stroke","PILOT_READY","2023 verified incidence Rate; dynamic endpoints blocked","Survival and duration parameters for dynamic outcomes"),
        ("T2D","NEXT_PRIORITY","Type 2 definition and compatible RR interface","Verify definition and obtain 2023 age-sex rate"),
        ("breast cancer","NEXT_PRIORITY","Female-specific 2023 rate and exposure match","Obtain female 2023 source rate"),
        ("colon cancer","DEFINITION_OR_SOURCE_BLOCKED","Colon-only cause needed","Obtain colon-only burden"),
        ("hypertension","DEFINITION_OR_SOURCE_BLOCKED","Leisure activity RR differs from total activity","Work-approved interface and incidence source"),
        ("depression","DEFINITION_OR_SOURCE_BLOCKED","Adult OR versus RR and comparison unresolved","Specify effect conversion and source"),
        ("bladder cancer","DEFINITION_OR_SOURCE_BLOCKED","Leisure proxy exposure","Work-approved exposure mapping"),
        ("endometrial cancer","DEFINITION_OR_SOURCE_BLOCKED","Leisure proxy and female cause","Female-specific source and mapping"),
        ("kidney cancer","DEFINITION_OR_SOURCE_BLOCKED","Leisure proxy exposure","Work-approved mapping and source"),
        ("oesophageal cancer","DEFINITION_OR_SOURCE_BLOCKED","Adenocarcinoma subtype","Subtype burden"),
        ("gastric cardia cancer","DEFINITION_OR_SOURCE_BLOCKED","Cardia subtype","Subtype burden"),
        ("dementia","DEFINITION_OR_SOURCE_BLOCKED","RR source mismatch; excluded","New evidence and Work decision"),
        ("ICH","DEFINITION_OR_SOURCE_BLOCKED","Ischemic RR inapplicable","ICH-specific RR and Work decision"),
        ("SAH","DEFINITION_OR_SOURCE_BLOCKED","Ischemic RR inapplicable","SAH-specific RR and Work decision"),
    ]
    hp.write_csv(HERE/"disease_expansion_status.csv",[dict(disease=x,tier=t,main_blocker=b,release_condition=c) for x,t,b,c in causes])
    hp.write_csv(HERE/"results"/"dynamic_outcome_status.csv",[
        dict(disease=d,incident_cases_averted="SEE_INCIDENCE_DETAIL",prevalent_patient_years_averted="",disease_deaths_averted="",YLD_averted="",YLL_averted="",DALY_averted="",status="BLOCKED_DYNAMIC_PARAMETERS") for d in hp.RR])
    (HERE/"METHODS.md").write_text("""# Health pilot methods\n\nPopulation: China age 20+, WPP 2024 Medium July 1 populations, 2025–2050. The 2025 exposure structure comes from 2018 CCDRFS observations, so it is a modelled 2025 starting point. The scenario multiplies each sex-age stratum's baseline prevalence by 1.00, .97, .94, .91, .88 and .85 in 2025–2030, then retains .85. The fixed 2025-population target is 18.6711438%; yearly crude prevalence can change with population composition. This is a WHO-target-magnitude-aligned Chinese health scenario, not a declaration of WHO formal target attainment. WHO monitoring uses a separate age-standardized 18+ series.\n\nKyu 2016 compares <600 with 600–3999 MET-min/week. This binary pilot maps newly meeting recommendations to the low-active category. It does not assume an exact 600 MET-min/week point effect or identical risk among all adults already meeting recommendations. RR is used only for IHD and ischemic-stroke incidence. For each cell, PIF=(p0-p1)*(RR-1)/(1+p0*(RR-1)); avoided incidence = WPP population × 2023 GBD incidence Rate/100,000 × PIF. The age-sex rate is held constant; no disease trend is projected.\n\nThe original GBD 2023 export offers 95+ and an additional 70+ aggregate. We ignore the overlapping 70+ aggregate and combine WPP 95–99 with 100+ to match its 95+ rate. The original download date and UI screenshot were not recovered; exact row-domain query conditions, citation, checksum and 2026-11-12 recovery date are recorded. Rate lower/upper are retained as inputs, not propagated into an invented formal uncertainty interval.\n\nDynamic outcomes can start only from avoided incidence cohorts. Prevalence/incidence, deaths/prevalence, YLD/prevalence and YLL/death would be descriptive calibration candidates if 2023 source exports were available, not approved transition probabilities. The current dynamic outputs are BLOCKED_DYNAMIC_PARAMETERS.\n""",encoding="utf-8")


def main():
    detail=hp.main()
    write_documents()
    write_notebooks()
    run=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],cwd=HERE,text=True,capture_output=True)
    report={"status":"PASS" if run.returncode==0 else "FAIL","command":"python -m unittest discover -s tests -v","stdout":run.stdout,"stderr":run.stderr,"test_count":10}
    (HERE/"tests"/"test_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if run.returncode: raise RuntimeError(run.stderr)
    summary=hp.read_csv(HERE/"results"/"incidence_summary.csv")
    cumulative=[r for r in summary if r["period_type"].startswith("cumulative")]
    (HERE/"HANDOFF_HEALTH_MODEL_PILOT.md").write_text("# Health model pilot handoff\n\nBranch: `codex/health-model-pilot-round3-20261112`\n\nBase remote commit: `204f3e3c3bdf719d189c0a761760f072d77cc5c6`\n\nStatus: `INCIDENCE_PILOT_COMPLETE`; dynamic outcomes `BLOCKED_DYNAMIC_PARAMETERS`.\n\nThe verified GBD 2023 ZIP contains 2023 IHD and ischemic-stroke incidence Rate/Number with point/lower/upper for Male and Female. GBD 95+ matches combined WPP 95–99 and 100+. Original download date and UI screenshot remain unknown; provenance reconstructs exact conditions from the raw rows.\n\nResults (expected cases, unrounded):\n\n"+"\n".join(f"- {r['period']} {r['disease']}: avoided {float(r['incident_cases_averted']):,.2f}; baseline {float(r['baseline_expected_incidence']):,.2f}" for r in cumulative)+"\n\nThe 2025 baseline is 21.9660515204% and fixed-weight 2030 intervention is 18.6711437924%, agreeing with Work's rounded figures. The 2018 exposure rates are retained by sex and age in the control.\n\nRun `python build_deliverables.py` from this directory to rebuild data, reports and tests. The five notebooks call the same public functions. No fee model, CEA, PSA or formal dynamic endpoint numbers were run. Next steps require 2023 Prevalence, Deaths, YLD, YLL and disease survival/duration evidence plus Work method approval.\n",encoding="utf-8")
    (HERE/"README.md").write_text("# IHD and ischemic-stroke health pilot\n\nFrom repository root, run `python new_study/round3_health_model_pilot_20261112/build_deliverables.py`. It copies and checksum-verifies the GBD 2023 source ZIP, rebuilds the WPP/exposure scenario and incidence results, runs 10 tests, and refreshes the SHA256 manifest. Use the five numbered notebooks in order for interactive reproduction.\n\nRead `METHODS.md` for definitions and `HANDOFF_HEALTH_MODEL_PILOT.md` for results and open dynamic parameters. Outputs are unrounded expected case counts; reporting may round them.\n",encoding="utf-8")
    for p in HERE.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".json", ".ipynb"}:
            p.write_bytes(p.read_bytes().replace(b"\r\n",b"\n"))
    files=[]
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and p.name!="sha256_manifest.csv" and "__pycache__" not in p.parts:
            files.append(dict(path=p.relative_to(HERE).as_posix(),bytes=p.stat().st_size,sha256=hp.sha256(p)))
    hp.write_csv(HERE/"sha256_manifest.csv",files)
    print(json.dumps({"detail_rows":len(detail),"tests":report["status"],"manifest_rows":len(files)}))

if __name__=="__main__": main()
