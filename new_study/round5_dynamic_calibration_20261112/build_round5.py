"""Reproducible E-worktree calibration build. No changes to previous rounds."""
import json
import math
import sys
from pathlib import Path
import numpy as np
from src.common import R5,ROOT,AGES,InputBlocked,config,frozen_incidence,write_csv,write_json
from src.population_reconciliation import load_sources,reconcile
from src.hazard_conversion import prepare as hazards
from src.outcome_mapping import prepare as mappings
from src.transition_calibration import calibrate
from src.dynamic_cohort_model import advance_age,run,aggregate,blocked_results

def age_checks():
    stock=np.zeros(16);stock[0]=100
    rows=[]
    for year in range(6):
        rows.append(dict(year=year,total=stock.sum(),initial_group_remaining=stock[0],outside_initial_group=stock[1:].sum(),minimum=stock.min(),status='PASS' if math.isclose(stock.sum(),100) and stock.min()>=0 else 'FAIL'))
        stock=advance_age(stock)
    return rows

def build_notebooks():
    topics=[
        ('01_source_and_population_reconciliation',"from src.population_reconciliation import load_sources,reconcile\ndata,audit=load_sources()\nrows=reconcile(data)\nassert all(r['status']=='PASS' for r in rows)\nprint('Verified raw ZIPs:',len(audit),'sex-age cells:',len(rows))\nprint('Maximum cross-export relative difference:',max(r['relative_difference'] for r in rows))"),
        ('02_rate_to_hazard_and_competing_risk',"from src.population_reconciliation import load_sources\nfrom src.hazard_conversion import prepare\ndata,_=load_sources()\nconversions,others=prepare(data)\nassert all(r['other_cause_hazard']>=0 for r in others)\nprint('Mortality rate conversions:',len(conversions),'single-disease decompositions:',len(others))\nprint('Hazard=Rate/100000; annual probability=1-exp(-hazard)')"),
        ('03_case_fatality_calibration',"from src.population_reconciliation import load_sources\nfrom src.transition_calibration import calibrate\ndata,_=load_sources()\nparameters,diagnostics,summary=calibrate(data)\nprint('Calibration status:',summary['status'])\nfor group in summary['groups']:\n    print(group['disease'],group['sex'],'max relative error',group['maximum_relative_error'],'RMS',group['rms_relative_error'],'incompatible age intervals',len(group['structurally_incompatible_age_intervals']))"),
        ('04_dynamic_cohort_model',"from src.common import R5,read_csv,InputBlocked\nfrom src.dynamic_cohort_model import run\nfrom src.common import frozen_incidence\nimport json\nsummary=json.loads((R5/'calibration_summary.json').read_text())\nif not summary['all_groups_pass']:\n    try:\n        run(frozen_incidence(),[],[],[],[],calibration_passed=False)\n    except InputBlocked as e:\n        print('Real-input run failed closed:',e)\n    else:\n        raise AssertionError('failed open')\nelse:\n    rows=run(frozen_incidence(),read_csv(R5/'inputs/case_fatality_parameters.csv'),read_csv(R5/'inputs/other_cause_mortality.csv'),read_csv(R5/'inputs/effective_disability_weights.csv'),read_csv(R5/'inputs/yll_per_death.csv'),calibration_passed=True)\n    print('Provisional real-input rows:',len(rows))"),
        ('05_results_validation',"from src.common import R5,read_csv,frozen_incidence\nfrom src.dynamic_cohort_model import OUTCOMES\nimport json\nreport=json.loads((R5/'results/model_validation_report.json').read_text())\nrows=read_csv(R5/'results/dynamic_results_age_sex_year.csv')\nfrozen_incidence()\nassert not any('SYNTHETIC' in str(r) for r in rows)\nif report['status']=='BLOCKED_TRANSITION_CALIBRATION':\n    assert all(r[m]=='' for r in rows for m in OUTCOMES[1:])\nelse:\n    assert all(abs(float(r['DALY_averted'])-float(r['YLD_averted'])-float(r['YLL_averted']))<1e-7 for r in rows)\nprint('Model status:',report['status'],'rows:',len(rows))\nprint('Frozen incidence totals retained; no burden endpoint multiplied by PIF')")]
    import nbformat
    for name,code in topics:
        cells=[nbformat.v4.new_markdown_cell('# '+name+'\nUses the same src modules as the local runner. Calibration gates are scientific results, independent of software execution success.'),nbformat.v4.new_code_cell(code)]
        for index,cell in enumerate(cells):cell['id']=name[:3]+'-cell-'+str(index)
        notebook=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Round 5 project Python','language':'python','name':'round5'}})
        (R5/'notebooks'/f'{name}.ipynb').write_text(nbformat.writes(notebook)+'\n',encoding='utf-8',newline='\n')

def write_reports(audit,pop,summary,weights,years):
    failed=[f"{g['disease']} {g['sex']}: max={g['maximum_relative_error']:.4%}; RMS={g['rms_relative_error']:.4%}; infeasible intervals={len(g['structurally_incompatible_age_intervals'])}" for g in summary['groups']]
    text='''# Round 5 dynamic calibration method

All analysis runs locally in `E:\\工作目录\\China-PA-13\\Analysis`, from remote base `1e2407664e79b75db3f8a5f8d4c79e5435e5e2dc`, branch `codex/dynamic-health-model-calibration-round5-20261112`.

## States and hazards

The model has disease-free, diseased, target-disease-dead states, with an absorbing other-cause-death exit for bookkeeping. Remission is zero; there is no recurrence state. IHD and ischemic stroke are fitted separately by sex. Other-cause hazard is assumed equal in the two live states as a temporary structural assumption.

Death Rate has units per 100,000 person-years: mu=Rate/100000; q(dt)=1-exp(-mu*dt). Other-cause hazard equals all-cause minus the current target disease population mortality hazard. The other target disease is retained in each model's other-cause hazard. Negative differences fail closed.

## Joint calibration and identifiability

We fit a stationary synthetic age profile; a single 2023 cross-section does not identify historical cohort changes. Total-population incidence I is held fixed. At each age susceptible incidence hazard is I/(1-p_model). S'=-(i_s+o)S; D'=i_s*S-(f+o)D. Thus dp/da=I-f*p*(1-p), with equal other-cause hazard cancelling only in the prevalence equation. Predicted population disease mortality is f*p. All-cause mortality is checked as o+f*p. This is a transparent consistency fit, not the IHME DisMod estimator.

Positive case-death hazards use PCHIP interpolation of log hazards across 16 age nodes. Initial D/P and a constant log-hazard start are optimized with scipy least_squares. A fitted first-node prevalence is a nuisance boundary because <20 history is missing. The loss uses equal log residuals for prevalence and target mortality plus weight 0.1 on second differences of log hazards. RK4 dt=0.5 years is checked at dt=0.25. Incidence is not rescaled. All target, fitted, absolute and relative errors are saved. Inputs' marginal UIs are retained in original ZIPs; independent ratio UIs are not fabricated.

Before fitting, computational acceptance thresholds were set to max absolute relative error <=20% and RMS relative error <=10% jointly over prevalence and target mortality. These are provisional screens for Work review, not published scientific adequacy standards. They are not loosened after seeing results. The optimizer converging is distinct from the epidemiologic fit passing. A necessary no-remission bound is delta prevalence <=integral incidence across age; violated intervals are listed. 95+ uses an approximate calibration node at 97.5, flagged for Work review; cohort simulation itself keeps an open 95+ state.

Model consistency is grounded in Barendregt et al. (2003), https://pmc.ncbi.nlm.nih.gov/articles/PMC156029/ . Its disease-state equations inform the implementation; no claim of identical fitting software or assumptions is made.

## Annual cohort engine

Policy affects only avoided incidence. Each calendar-year entry receives 0.5 years of disease/other mortality hazards; existing stock receives 1 year. Under constant within-cycle hazard, survival and person-years use exact exponential integration; target and other deaths are competing exits. All transitions and outcomes are evaluated at current age, then 1/5 of closed-group survivors flows to the next age group at year end; 95+ stays open. No remission or recurrence flow exists.

Local WPP raw inventory contains five-year age files and PPgp group files, not verified single-year population. No single-year population is invented. The 1/5 rule is a mixing approximation: 0.8^5=32.768% remains after five flows, 67.232% has left; it is not a deterministic birth-cohort conveyor. Annual outcome age is attained current group. End-stock and entry/death totals support tracking.

Effective DW=YLD Number/Prevalence Number; YLL/death=YLL Number/Deaths Number. Rate ratios independently match; 95+ uses its original open-age mappings. They are OUTCOME_MAPPING only. Standard YLL life-table external validation remains pending. YLD=person-years*DW; YLL=target deaths*YLL/death; DALY=YLD+YLL. No GBD burden endpoint is multiplied by PIF.

## Gates and conditional assumptions

When joint calibration fails, empirical dynamic endpoints remain blank with BLOCKED_TRANSITION_CALIBRATION. Synthetic software tests use isolated in-memory fixtures. Incidence retains PILOT_CONDITIONAL_RR_DENOMINATOR: all existing >=600 activity levels share the low-active reference in this binary approximation. Future multicate PIF awaits category shares and movement rules. Real dynamic results can at most be DYNAMIC_PILOT_PROVISIONAL.
'''
    (R5/'reports/METHODS_DYNAMIC_CALIBRATION.md').write_text(text,encoding='utf-8',newline='\n')
    review='# Calibration review\n\nStatus: `'+summary['status']+'`.\n\n'+'\n'.join('- '+x for x in failed)+'\n\nThe pre-fit gate applies to all four disease-sex groups. No failing group is admitted and no fit threshold is relaxed. The current stationary no-remission structure and exported incidence/prevalence/mortality definitions require Work review. Do not infer a data transcription error solely from failure. Possible unresolved issues include incident event versus disease-state definitions, prevalent sequelae, historical cohort effects, boundary conditions, and open-age approximation. No disease structure or incidence totals have been changed.\n\nA provisional dynamic result cannot be released until Work selects a defensible calibration path. The simple D/P initial curve is retained only as a diagnostic sensitivity; it is not substituted for the failed joint fit.\n'
    (R5/'reports/CALIBRATION_REVIEW.md').write_text(review,encoding='utf-8',newline='\n')
    provenance='# Data provenance audit\n\nThree original ZIPs are read in place and rehashed each build; full dimensions, citation, size, modification time and audit time are in `raw_input_audit.json`. No ZIP is copied to the new directory or staged in Git.\n\n'+''.join(f"- {a['dataset']}: `{a['local_path']}`; SHA256 `{a['sha256']}`; rows {a['row_count']}.\n" for a in audit)+f"\nCross-export population: 32 sex-age rows, maximum relative difference {max(r['relative_difference'] for r in pop):.12g}. WPP 2025 comparison is external and not an equality gate against GBD 2023.\n\n`F1SO}})17CY[B2_I9SF$J{{OC.png` is INCOMPLETE_QUERY_SCREENSHOT_NOT_USED and was not copied. Complete-final-query screenshot remains unavailable; original export dimensions and citation are retained.\n"
    (R5/'reports/DATA_PROVENANCE_AUDIT.md').write_text(provenance,encoding='utf-8',newline='\n')
    age='# Age progression\n\nVerified local WPP files are grouped, so the authorized five-year-group fallback is used. Death/disease transitions and exact person-years are computed first, followed by annual survivor flow: 20% to next group, 80% retained; 95+ retains all survivors. New midyear incident entries receive only half a cycle of hazards before the same year-end group flow. This annual mixing approximation is not exact single-age aging. Five flows leave 32.768% in the original group. Outcomes are recorded before age flow, with survivor stock tracking for conservation. A single-year comparison remains BLOCKED until verified single-age WPP and matching disease-rate interpolation are approved.\n'
    (R5/'reports/age_progression_method.md').write_text(age,encoding='utf-8',newline='\n')
    handoff='# Round 5 handoff\n\nLocal worktree: `E:\\工作目录\\China-PA-13\\Analysis`\nBranch: `codex/dynamic-health-model-calibration-round5-20261112`\nBase: `1e2407664e79b75db3f8a5f8d4c79e5435e5e2dc`\n\nStatus: `'+summary['status']+'`. Exact delivered commit is recorded by Git (`git rev-parse HEAD`), not embedded in a self-referential file.\n\nThree raw packages pass their expected SHA256 and cross-population gates. Hazard decomposition, outcome mapping, annual 1/5 age flow, half-cycle incident entry, joint smooth positive case-fatality fitting and fail-closed dynamic runner are implemented.\n\n'+ '\n'.join(failed)+f"\n\nEffective DW range: {min(r['effective_disability_weight'] for r in weights):.9g}–{max(r['effective_disability_weight'] for r in weights):.9g}. YLL/death range: {min(r['YLL_per_death'] for r in years):.9g}–{max(r['YLL_per_death'] for r in years):.9g}.\n\n"+'The preserved incidence totals are IHD 45,531.007 / 116,899.570 / 547,363.017 and ischemic stroke 57,420.852 / 143,733.241 / 598,423.448 for 2025–2030 / 2034 / 2050, respectively. Dynamic endpoints are blank if calibration fails. Read CALIBRATION_REVIEW before selecting the next step.\n\nNew files are confined to this round plus repository requirements.txt and run_local.ps1. Five source notebooks and five standard nbclient-executed copies, separate legacy and new test logs, validation report, requirements lock and hash manifest are included. Actual checks and counts are in logs/test_results.json and results/model_validation_report.json.\n\nWork must resolve the incompatible age profile and definitions; cohort history, 95+ approximation and equal other mortality also need review. Thresholds are computational screens only. No old-round files or raw ZIPs were changed. No cost, CEA, PSA or main-branch merge was performed. Synthetic parameters never enter empirical results.\n'
    handoff=handoff.replace('repository requirements.txt and run_local.ps1','repository requirements.txt, run_local.ps1 and README_LOCAL_RUN.md')
    (R5/'reports/HANDOFF_ROUND5.md').write_text(handoff,encoding='utf-8',newline='\n')

def build():
    for name in ['inputs','results','reports','notebooks','notebooks/executed','logs']:(R5/name).mkdir(parents=True,exist_ok=True)
    datasets,audit=load_sources();write_json(R5/'raw_input_audit.json',audit)
    population=reconcile(datasets);write_csv(R5/'results/cross_export_population_reconciliation.csv',population)
    if any(r['status']!='PASS' for r in population):raise InputBlocked('BLOCKED_INPUT: cross-export population mismatch')
    conversions,others=hazards(datasets);weights,years=mappings(datasets['disease'])
    write_csv(R5/'results/rate_hazard_conversion.csv',conversions);write_csv(R5/'inputs/other_cause_mortality.csv',others)
    write_csv(R5/'inputs/effective_disability_weights.csv',weights);write_csv(R5/'inputs/yll_per_death.csv',years)
    parameters,diagnostics,summary=calibrate(datasets)
    write_csv(R5/'inputs/case_fatality_parameters.csv',parameters);write_csv(R5/'results/case_fatality_calibration.csv',parameters)
    write_csv(R5/'results/calibration_fit_diagnostics.csv',diagnostics);write_json(R5/'calibration_summary.json',summary)
    incidence=frozen_incidence()
    try:
        rows=run(incidence,parameters,others,weights,years,calibration_passed=summary['all_groups_pass']);totals=aggregate(rows)
    except InputBlocked:
        rows,totals=blocked_results(incidence)
    write_csv(R5/'results/dynamic_results_age_sex_year.csv',rows);write_csv(R5/'results/dynamic_results_summary.csv',totals)
    write_csv(R5/'results/age_progression_validation.csv',age_checks())
    write_csv(R5/'inputs/age_progression_parameters.csv',[dict(age=a,annual_outflow=.2 if a!='95+' else 0,next_age=AGES[min(j+1,15)],timing='after_current_age_transitions_and_outcomes') for j,a in enumerate(AGES)])
    sensitivities=[
        dict(comparison='single_year_vs_group_annual_flow',status='BLOCKED',reason='No verified single-age WPP locally; no single-age disease-rate interpolation approved'),
        dict(comparison='midyear_vs_startyear_incidence',status='BLOCKED_TRANSITION_CALIBRATION' if not summary['all_groups_pass'] else 'READY',reason='run(first_duration=1) interface; baseline uses .5'),
        dict(comparison='joint_fit_vs_simple_Deaths_Prevalence',status='DIAGNOSTIC_ONLY',reason='Initial ratio and its age-profile residuals retained; no admission by ratio alone'),
        dict(comparison='fixed_2023_vs_historical_trend',status='BLOCKED',reason='No approved trend extrapolation; interface requires age-sex-year hazards'),
        dict(comparison='binary_vs_multicategory_PIF',status='BLOCKED',reason='Observed age-sex category shares and approved movement rule absent')]
    write_csv(R5/'results/structural_sensitivity_status.csv',sensitivities)
    report=dict(status=summary['status'],incidence_status='PILOT_CONDITIONAL_RR_DENOMINATOR',raw_zip_checks='PASS',cross_export_population='PASS',maximum_population_relative_difference=max(r['relative_difference'] for r in population),scientific_calibration_gate='PASS' if summary['all_groups_pass'] else 'FAIL',dynamic_endpoint_status=summary['status'],effective_dw_range=[min(r['effective_disability_weight'] for r in weights),max(r['effective_disability_weight'] for r in weights)],yll_per_death_range=[min(r['YLL_per_death'] for r in years),max(r['YLL_per_death'] for r in years)],dynamic_rows=len(rows),screenshot='NOT_APPLICABLE: INCOMPLETE_QUERY_SCREENSHOT_NOT_USED',standard_life_table_external_check='NOT_CHECKED',no_formal_complete_status=True)
    write_json(R5/'results/model_validation_report.json',report)
    write_reports(audit,population,summary,weights,years);build_notebooks()
    print(json.dumps(report,indent=2),flush=True)
    return report

if __name__=='__main__':build()
