"""Build round-four inputs, run the software fixture, and audit output gates."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from src.dynamic_model import (R4, R3, RAW_ZIP, RAW_SHA, InputBlocked, incidence_input,
                               read_csv, write_csv, run_cohorts, summarize,
                               synthetic_fixture, missing_parameter, verify_rate_number_pairs)


def write_utf8(path, content):
    Path(path).write_bytes(content.encode('utf-8'))


def parameter_tables():
    fields = ["disease","parameter_id","parameter_name","age","sex","duration_since_incidence","point","lower","upper","source","source_year","source_population","parameter_role","admission_status","uncertainty_distribution","notes"]
    rows = []
    source = [r for r in incidence_input() if r['year']=='2025']
    for base in source:
        disease,age,sex=base['disease'],base['age_group'],base['sex']
        rows.append(dict(disease=disease,parameter_id='incidence',parameter_name='incidence_rate_per_100k',age=age,sex=sex,duration_since_incidence=0,point=base['baseline_rate_per_100k'],lower=base['baseline_rate_lower'],upper=base['baseline_rate_upper'],source='GBD 2023 verified incidence ZIP',source_year=2023,source_population='China; All Population',parameter_role='DIRECT_INPUT',admission_status='DIRECT_INPUT',uncertainty_distribution='',notes='95+ GBD rate aligns with WPP 95-99 plus 100+ population'))
        for parameter, role, evidence, note in (
            ("prevalence", "CALIBRATION_TARGET", "GBD 2023 requested", "Raw 2023 export unavailable"),
            ("disease_specific_mortality", "CALIBRATION_TARGET", "GBD 2023 requested", "Not a transition probability"),
            ("all_cause_mortality", "BLOCKED", "WPP/China life table requested", "Competing risk by age-sex-year"),
            ("remission", "BLOCKED", "Longitudinal cohort required", "Disease-specific definition and duration required"),
            ("recurrence", "BLOCKED", "Longitudinal cohort required", "Disease-specific definition and duration required"),
            ("disease_survival", "BLOCKED", "Registry/cohort required", "Time since incidence required"),
            ("excess_mortality", "BLOCKED", "Registry/cohort required", "Separate from all-cause competing risk"),
            ("case_fatality", "BLOCKED", "Registry/cohort required", "Acute interval and denominator required"),
            ("disability_weight_or_yld", "CALIBRATION_TARGET", "GBD 2023 YLD requested", "YLD/prevalence is descriptive only"),
            ("standard_remaining_life_expectancy", "BLOCKED", "GBD standard life table requested", "Not interchangeable with China life table"),
        ):
            rows.append(dict(disease=disease,parameter_id=parameter,parameter_name=parameter,age=age,sex=sex,duration_since_incidence='ALL',point='',lower='',upper='',source=evidence,source_year=2023 if 'GBD' in evidence else '',source_population='China' if 'GBD' in evidence else '',parameter_role=role,admission_status='BLOCKED',uncertainty_distribution='',notes=note))
    write_csv(R4/"inputs"/"transition_parameters.csv",rows,fields)
    calibration = []
    for disease in ("IHD","IS"):
        for ratio in ("Prevalence/Incidence","Deaths/Prevalence","YLD/Prevalence","YLL/Deaths"):
            calibration.append(dict(disease=disease,ratio=ratio,point="",lower="",upper="",status="BLOCKED_SOURCE_MISSING",interpretation="Descriptive calibration target, not an annual transition probability"))
    write_csv(R4/"inputs"/"calibration_targets.csv",calibration,list(calibration[0]))


def rr_table():
    rows=[]
    for disease,rr,lo,hi in (("IHD",1.19474313,1.128668172,1.264222503),("IS",1.18623962,1.089324619,1.283697047)):
        rows.append(dict(disease=disease,source="Kyu 2016",comparison="<600 vs 600-3999 MET-min/week",rr=rr,lower=lo,upper=hi,model_denominator="all >=600 treated as risk 1",model_type="low-active-reference binary approximation",category_rr_complete="NO",age_sex_category_proportions="MISSING",result_status="PILOT_CONDITIONAL_RR_DENOMINATOR"))
    write_csv(R4/"inputs"/"rr_exposure_interface.csv",rows,list(rows[0]))
    category=[]
    for disease,risks in (("IHD",[(1.0,"",""),(.837,.791,.886),(.769,.698,.838),(.754,.704,.809)]),("IS",[(1.0,"",""),(.843,.779,.918),(.810,.690,.937),(.736,.659,.811)])):
        for label,(point,lower,upper) in zip(("<600","600-3999","4000-7999",">=8000"),risks):
            category.append(dict(disease=disease,category_MET_min_week=label,rr_vs_inactive=point,lower=lower,upper=upper,source="Kyu 2016 original Table 1",source_path="new_study/round1_20261112/raw/rr/Kyu2016.html",exposure_share_status="MISSING_AGE_SEX_CATEGORY_SHARES",use_status="EVIDENCE_EXTRACTED_NOT_MODEL_READY"))
    write_csv(R4/"inputs"/"kyu_category_rr.csv",category,list(category[0]))


def notebooks():
    topics = [
        ("01_rr_exposure_interface","RR and exposure interface","The Kyu contrast is <600 versus 600–3999 MET-min/week. The binary calculation assigns risk 1 to everyone ≥600, so its denominator is an explicit structural approximation.","from src.dynamic_model import pif\nprint('Equal exposure PIF:', pif(.2,.2,1.19474313))"),
        ("02_dynamic_input_validation","GBD and incidence input validation","Only the SHA-matched GBD 2023 incidence ZIP is admitted. Prevalence, Deaths, YLD and YLL exports are absent; no legacy candidate is loaded.","from src.dynamic_model import incidence_input, verify_rate_number_pairs\nrows=incidence_input()\nprint('Frozen rows:', len(rows), 'Rate/Number pairs:',len(verify_rate_number_pairs()))"),
        ("03_transition_calibration","Transition calibration gate","GBD burden ratios are descriptive calibration targets. Their cells remain blank until original 2023 exports are obtained. No ratio is interpreted as a transition probability.","from src.dynamic_model import read_csv,R4\nprint('Blocked targets:',len(read_csv(R4/'inputs'/'calibration_targets.csv')))"),
        ("04_multistate_lifetable_model","Annual cohort engine","Avoided incidence is the sole intervention entry. Competing disease death, other death, remission, recurrence and aging are modelled. Synthetic values exercise code only.","from src.dynamic_model import run_cohorts, synthetic_fixture, incidence_input\nfixture,_=run_cohorts(incidence_input()[:2],synthetic_fixture,allow_provisional=True)\nprint('Synthetic rows:',len(fixture),'status:',fixture[0]['result_status'])"),
        ("05_dynamic_results_reconciliation","Results and gate reconciliation","Frozen IHD/IS incidence is preserved. Actual dynamic endpoints remain blocked. Synthetic output must never be presented as scientific results.","from src.dynamic_model import read_csv,R4\nrows=read_csv(R4/'results'/'incidence_results_age_sex_year.csv')\nexpected={'IHD':547363.017,'IS':598423.448}\nfor disease,target in expected.items():\n    actual=sum(float(r['incident_cases_averted']) for r in rows if r['disease']==disease)\n    assert abs(actual-target)<.001\n    print(disease,'frozen 2025-2050:',round(actual,3))\nassert all(r['DALY_averted']=='' and r['result_status']=='BLOCKED_DYNAMIC_PARAMETERS' for r in read_csv(R4/'results'/'dynamic_results_summary.csv'))\nprint('Dynamic endpoints: BLOCKED_DYNAMIC_PARAMETERS')")]
    for name,title,explanation,code in topics:
        doc={"cells":[
            {"cell_type":"markdown","metadata":{},"source":["# "+title+"\n",explanation+"\n"]},
            {"cell_type":"markdown","metadata":{},"source":["## Source and method\n","Verified input: round 3 incidence derived from the SHA-matched original GBD 2023 ZIP, WPP population and CCDRFS exposure. Kyu Table 1 supplies IHD and ischemic-stroke exposure contrasts. The callable code below uses `src.dynamic_model`; no independent notebook formula is introduced.\n"]},
            {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":[code+"\n"]},
            {"cell_type":"markdown","metadata":{},"source":["## Interpretation and limit\n","The incidence result remains `PILOT_CONDITIONAL_RR_DENOMINATOR`. Empirical dynamic death, patient-years, YLD, YLL and DALY remain `BLOCKED_DYNAMIC_PARAMETERS`. Any synthetic fixture output is a software test only.\n"]}],"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python"}},"nbformat":4,"nbformat_minor":5}
        write_utf8(R4/"notebooks"/(name+".ipynb"),json.dumps(doc,ensure_ascii=False,indent=2)+"\n")


def build():
    start=time.time()
    for folder in ("inputs","raw","config","results","figures","tests","logs","reports","notebooks"):
        (R4/folder).mkdir(parents=True,exist_ok=True)
    original=incidence_input()
    fields=list(original[0])+["parameter_status","result_status"]
    preserved=[dict(r,parameter_status="GBD_2023_INC_RATE_VERIFIED",result_status="PILOT_CONDITIONAL_RR_DENOMINATOR") for r in original]
    write_csv(R4/"results"/"incidence_results_age_sex_year.csv",preserved,fields)
    parameter_tables();rr_table();notebooks()
    config="""model: avoided_incidence_cohort\nperiod: 2025-2050\nincidence_source: verified_GBD_2023_rate\nrr_exposure_status: PILOT_CONDITIONAL_RR_DENOMINATOR\ndynamic_science_status: BLOCKED_DYNAMIC_PARAMETERS\nannual_timing: incident_entry_then_competing_exits\nsynthetic_fixture: software_test_only\n"""
    write_utf8(R4/"config"/"model_config.yaml",config)
    write_utf8(R4/"raw"/"SOURCE_POINTER.md",f"GBD incidence original: `{RAW_ZIP.relative_to(R4.parents[1])}`\nSHA256: `{RAW_SHA}`\nNo duplicate ZIP is stored here. 2023 Prevalence/Deaths/YLD/YLL raw export not found.\n")
    implied=verify_rate_number_pairs()
    diagnostics=[dict(disease=k[0],sex=k[1],age=k[2],measure=k[3],implied_population=v,status="RATE_NUMBER_PAIR_PRESENT; WPP comparison is descriptive") for k,v in sorted(implied.items())]
    write_csv(R4/"results"/"calibration_diagnostics.csv",diagnostics,list(diagnostics[0]))
    blocked=[dict(year="",disease=d,sex="",age_group="",scenario="difference_vs_control",incident_cases_averted="",prevalent_patient_years_averted="",disease_deaths_averted="",YLD_averted="",YLL_averted="",DALY_averted="",parameter_status="MISSING",result_status="BLOCKED_DYNAMIC_PARAMETERS") for d in ("IHD","IS")]
    write_csv(R4/"results"/"dynamic_results_age_sex_year.csv",blocked,list(blocked[0]))
    write_csv(R4/"results"/"dynamic_results_summary.csv",blocked,list(blocked[0]))
    fixture,ff=run_cohorts(original,synthetic_fixture,allow_provisional=True)
    write_csv(R4/"tests"/"synthetic_software_fixture.csv",fixture,ff)
    fixture_summary=summarize(fixture)
    write_csv(R4/"tests"/"synthetic_software_fixture_summary.csv",fixture_summary,list(fixture_summary[0]))
    # Formal run must fail closed; the fixture is only a software test.
    try:
        run_cohorts(original[:1],missing_parameter)
    except InputBlocked as error:
        gate=str(error)
    else:
        raise AssertionError("dynamic gate failed open")
    report={"status":"BLOCKED_DYNAMIC_PARAMETERS","incidence_status":"PILOT_CONDITIONAL_RR_DENOMINATOR","incidence_rows":len(original),"rate_number_pairs":len(implied),"synthetic_test_rows":len(fixture),"formal_gate":gate,"gbd_incidence_sha256":RAW_SHA,"python":sys.version,"platform":platform.platform(),"started_utc_epoch":start,"ended_utc_epoch":time.time()}
    write_utf8(R4/"results"/"model_validation_report.json",json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    return report


if __name__=="__main__":
    print(json.dumps(build(),ensure_ascii=False,indent=2))
