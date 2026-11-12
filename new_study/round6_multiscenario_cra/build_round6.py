"""Offline repeatable comparative-risk build; no other-round model imports."""
import json,sys
from pathlib import Path
from src.common import R6,ROOT,VARIANTS,config,verify_old_inputs,write_csv,write_json,read_csv,sha
from src.sources import population_exposure,gbd_rates,extract_continuous_rr,category_rr,KYU
from src.evidence import endpoint_admission,exposure_inventory,register_parameters,RAND,WHO,GBD_CVD,KYU_URL
from src.analysis import exposure_rows,national_exposure,risk_and_incidence,comparison_summary,legacy_regression,legacy_summaries

def notebooks():
    import nbformat
    topics=[
        ('01_inputs_and_evidence',"from src.common import verify_old_inputs\nfrom src.sources import population_exposure,gbd_rates,extract_continuous_rr\nfrom src.evidence import endpoint_admission\nprint('Locked inputs:',len(verify_old_inputs()))\nprint('Population/exposure rows:',len(population_exposure()))\nprint('GBD incidence rate rows:',len(gbd_rates()[0]))\nprint('Published dose RR knots:',len(extract_continuous_rr()))\nprint('Clinical gates:',{r['admission_status'] for r in endpoint_admission()})"),
        ('02_scenario_exposure',"from src.sources import population_exposure\nfrom src.analysis import exposure_rows,national_exposure\nrows=national_exposure(exposure_rows(population_exposure()))\nfor r in rows:\n    if r['year']==2030:print(r['scenario'],r['path'],'inactive prevalence:',r['scenario_p_inactive'],'status:',r['status'])\nprint('R2 missing inactivity estimate is blank, not zero; means require exposure distributions')"),
        ('03_rr_pif_and_incidence',"from src.sources import population_exposure,gbd_rates,category_rr\nfrom src.analysis import risk_and_incidence,legacy_regression,legacy_summaries\nb=population_exposure();rates,_=gbd_rates()\npifs,events=risk_and_incidence(b,rates,category_rr())\nassert all(r['avoided_incident_units']=='' for r in events if r['scenario']!='B0')\nprint('PIF interface rows:',len(pifs),'event interface rows:',len(events))\nprint('New clinical event effects: BLOCKED_ENDPOINT_ALIGNMENT')\nfor r in legacy_summaries(legacy_regression(b,rates)):print(r)"),
        ('04_scenario_comparison',"from src.common import R6,read_csv\nfrom src.exposure import transformed_distribution\nfrom src.risk import continuous_pif\nrows=read_csv(R6/'results/scenario_comparison_summary.csv')\nfor r in rows:\n    if r['period_type']=='annual' and r['period']=='2030':print(r['disease'],r['scenario'],r['path'],r['status'])\n# Isolated mathematical counterexample, not a China exposure estimate.\ntoy=[(550.,1.)];risk=lambda x:1/(1+x/1000)\nr2=continuous_pif(toy,transformed_distribution(toy,'R2',2030,'immediate_2025'),risk)\nr3=continuous_pif(toy,transformed_distribution(toy,'R3',2030,'immediate_2025'),risk)\nassert r2>r3\nprint('SPEC_CONFLICT_R3_VS_R2_ORDERING: the specified formulas do not imply universal R3 dominance')"),
        ('05_validation_and_limitations',"import json\nfrom src.common import R6,verify_old_inputs\nreport=json.loads((R6/'results/model_validation_report.json').read_text(encoding='utf-8'))\nverify_old_inputs()\nprint(report['analysis_status'])\nprint('Scenario status:',report['scenario_status'])\nprint('No natural-history or economic module is imported by this runner')\nprint('New PIF envelopes are identification bounds under category assumptions, not uncertainty intervals or admitted health effects')")]
    for name,code in topics:
        cells=[nbformat.v4.new_markdown_cell('# '+name+'\nAll calculations call the same src functions as the local build. Source verification, exposure identification and clinical admission are distinct gates.'),nbformat.v4.new_code_cell(code)]
        for i,cell in enumerate(cells):cell['id']=name[:2]+'-cell-'+str(i)
        nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'name':'round6','language':'python','display_name':'Round6 project Python'}})
        (R6/'notebooks'/f'{name}.ipynb').write_text(nbformat.writes(nb)+'\n',encoding='utf-8',newline='\n')

def reports(report,regression):
    methods='''# Round 6 multi-scenario comparative risk methods

Local execution: E:\\工作目录\\China-PA-13\\Analysis. Base e307f03b1fb824711365378c940bcd0c25544d86; branch codex/multiscenario-cra-round6. Round5 remains BLOCKED_TRANSITION_CALIBRATION and is not called. All current computations use round6 src only.

## Population, exposure and scenarios

WPP2024 Medium July1 is model-estimated population. The 2025 exposure start is modelled using 2018 CCDRFS sex/coarse-age insufficient-activity observations assigned without interpolation to fine age groups. Shared-source CIs remain shared, not independent fine-age estimates. WPP95-99 and100+ are combined for original GBD95+ rates. National crude exposure may change with population composition; 2030 rates equal .85 of baseline within each stratum, not a nationally fixed crude target.

B0 preserves age-sex prevalence. P15 moves .03 additional shares of baseline inactive mass each year through2030, capped .15. With measured activity atoms, every originally <600 atom splits its weight proportionately between its original dose and600. R1 uses max(x,600); R2 uses1.2*x including zeros; R3 uses600 for baseline x<600 and1.2*x otherwise. R1-R3 have both immediate2025 and common2030 mixture paths. A common path mixes baseline and transformed distributions, never interpolates RR. These are scenario assumptions, not observed behaviour. In the present data only inactivity margins are identified: R1/R3 target inactivity0, P15 .85*p0, R2 generally unknown. Means and full activity distributions remain blank.

Only total conventional gross MET-min/week is contemplated. A marginal-MET or leisure-only scalar is not converted without duration, intensity and domain evidence. No category midpoints, generic European shape, individual exposure or within-category density is imputed.

## Dose-response evidence and PIF

Kyu appendix4 TableF p79-80 supplies 52 published dose knots per disease,0 to30600 in600 steps. At600 the original point RRs are IHD .909 (.857-.964) and IS .910 (.831-1.000), distinct from category averages .837 and .843. Exact knots are supported in code. Optional piecewise-linear interpolation is explicitly a numerical structural sensitivity, disabled by default; it is not the original Bayesian curve. No tail extrapolation is allowed. Marginal pointwise UIs do not supply joint curve uncertainty.

Continuous PIF=(weighted baseline RR-weighted scenario RR)/weighted baseline RR. Category PIF uses normalized category probabilities. Missing distributions fail closed. P15 and R1 also have an identifiable *categorical-model diagnostic envelope*, despite unknown active-category shares: for p=inactive fraction, alpha=moved fraction, rL=low-active category RR, the numerator is alpha*p*(1-rL); denominator is p+(1-p)*mean(active RR). Bounding the unknown active mean by the minimum/maximum published active-category RR yields the reported interval. No active distribution is estimated. It is a STRUCTURAL_SENSITIVITY_ONLY source-risk identification envelope, not a95%UI, continuous600-point effect, or admitted GBD burden effect. New effect point estimates remain blank. R2/R3 remain BLOCKED_EXPOSURE_DISTRIBUTION rather than artificial zero.

## Clinical endpoint gate

Kyu protocol appendix1 p2 permits new diagnoses and mortality; appendix4 TablesD/E includes reports of incidence and mortality. A separately selected incidence-only fitted RR curve has not been established. Consequently no new intervention PIF is multiplied by GBD incidence in this build. The IHD GBD2023 primary disease appendix still needs its exact MI/event aggregation and first/recurrent rules verified. The GBD-author stroke factsheet2026 Methods corroborates first-ever lifetime stroke; this does not by itself resolve Kyu's pooled outcome selection. Broad chronic IHD prevalence cannot be inferred from MI incidence or vice versa.

Other endpoints remain BLOCKED_OUTCOME_RISK_MAPPING, including deaths,YLD,YLL,DALY,prevalence and prevalent-equivalent patient-years. No dynamic model is restored. A publicly cited and Work-approved cross-endpoint mapping could later be a separately labelled STRUCTURAL_CRA_SENSITIVITY; none is silently enabled here. Prevalence*population*one year would mean prevalent-equivalent years, never followed incident-cohort patient-years.

## Comparisons and time

All scenario comparisons use the same WPP and verified GBD2023 rate tables. Primary endpoint comparison is2030;2034 and2050 are separate annual endpoints. Intervention incidence effects and differences versusP15 are blank pending admission. B0 model-estimated incident units are supplied as the common descriptive reference. The code records all years and cumulative2025-2030/2034/2050 windows;2025-2030 contains six calendar years. Calendar sums, if admitted later, require the explicitly recorded instantaneous-risk-response assumption; no lag length is invented. Endpoint counterfactual burdens are not claims of immediately realised annual policy benefits. Disease rates are held constant; only population changes. Historical disease trends are not extrapolated.

Old binary P15 is independently recomputed from locked WPP, exposure and raw GBD rates solely for regression. It assigns all active people the low-active risk in its denominator. Its six historical totals and1664 rows are preserved as REGRESSION_ONLY_NOT_RR_ADMISSION, never renamedR1 or merged into current admitted results.

## Mathematical specification conflict

R3>=R1 holds under a monotone decreasing risk function. UniversalR3>=R2 does not follow from the mandated formulas: baseline550 gives R2=660 andR3=600. Tests retain this counterexample and check R3>=R2 only under sufficient support restrictions (all initially inactive doses<=500). No scenario formula is changed to manufacture the requested ranking. This conflict is reported for Work; no clinical ordering is inferred with the present data.
'''
    methods=methods.replace('Only total conventional gross MET-min/week is contemplated.','Gao Methods sections2-3 define <150 moderate-equivalent minutes/week and retain bouts>=10min. Under conventional4MET moderate/8MET vigorous scoring,4*(moderate+2*vigorous)<600 is the same binary threshold; this does not recover a continuous exposure distribution. Only total conventional gross MET-min/week is contemplated.')
    methods=methods.replace('New effect point estimates remain blank.','New effect point estimates remain blank. Category-risk differences versusP15 retain the same unknown denominator: replace alpha by alpha_s-alpha_P15 and reorder endpoints for negative differences. These are within-stratum source-risk comparisons, not GBD event-count differences or clinical confidence intervals.')
    (R6/'reports/METHODS_MULTISCENARIO_CRA.md').write_text(methods,encoding='utf-8',newline='\n')
    rand=f'''# RAND scenario source review

Primary source: {RAND}
Publisher metadata: https://www.rand.org/pubs/research_reports/RR4291.html ; DOI10.7249/RR4291;2019.

Executive summary printed p v-vi (PDF7-8), section4.1 printed p27 (PDF52), and AppendixC.1 printed p151 (PDF177) define: R1=max(x,600); R2=1.2x for everyone, including zero remaining zero; R3=600 for baseline x<600, otherwise1.2x. At exactly600 this round follows the researcher's explicit >=600 branch. Improvements are assumed at the outset (printed pvi/PDF8); the report does not prescribe this study's2025 start. That start and the common2030 ramp are research scenario choices.

AppendixC.1 p150-151/PDF176-177 imputes distributions from a European template shifted to country inactivity margins. Its shape is not Chinese observed exposure. AppendixC.2 p152/PDF178 describes600-step risk inputs and interpolation; its numerical RR table and endpoint mapping are not recovered/admitted for this project. No economic parameter or output is reused.

The original PDF was reviewed through the web PDF parser. Direct local download returned403; no local complete PDF or SHA is claimed. Web screenshot rendering also failed with a cache miss. Retrieval attempts are saved in raw/source_retrieval_log.json. A future local copy should retain its filename and SHA; the current scenario formulas are independently explicit in config/scenarios.yaml.
'''
    (R6/'reports/RAND_SCENARIO_SOURCE_REVIEW.md').write_text(rand,encoding='utf-8',newline='\n')
    change='''# Round5 to Round6 change log

Natural-history fitting is paused. Round5 files and status BLOCKED_TRANSITION_CALIBRATION remain unchanged. The new runner neither imports nor executes that calibration or its tests, since those tests themselves run natural-history examples. The prior85-test report is retained as historical evidence, not re-counted as current passes.

New work comprises weighted exposure pushforwards, normalized continuous/category PIF functions, endpoint gates, eight variants across five named scenarios, actual categorical risk-identification envelopes forP15/R1, B0 descriptive projections, and a1664-row independent oldP15 regression. No new effect counts are published without clinical endpoint admission.

The Kyu600-point grid is newly extracted from already-local TableF; it is not a replacement for its category averages. Inactive margins cannot identify the full risk denominator orR2/R3 effects. A counterexample disproves the requested universalR3>=R2 check under the specified formulas. Config retains those formulas; no ranking rule overrides them.

Only round6 and root run_local.ps1, requirements.txt, README_LOCAL_RUN.md change. No raw ZIP is copied or overwritten. No individual exposure is uploaded. No cost, economic model, PSA, natural-history model or main-branch merge is run.
'''
    change=change.replace('Only round6 and root run_local.ps1, requirements.txt, README_LOCAL_RUN.md change.','All new files are confined to round6, including its own runner, requirements and README. Shared root files are preserved.')
    (R6/'reports/ROUND5_TO_ROUND6_CHANGELOG.md').write_text(change,encoding='utf-8',newline='\n')
    gap='''# Precise evidence release steps

1. Exposure: provide approved survey-weighted China age-sex distributions of total gross MET-min/week, with zero mass, inactive dose distribution,600-3999/4000-7999/>=8000 shares and tails. Local individual data may be used only with explicit permission; do not commit raw individual records or unapproved distributions. R2 needs mass around thresholds after1.2x;R3 needs the active-dose distribution. P15/R1 continuous effects also need inactive mean risks and the baseline denominator.
2. RR: use Kyu appendix1 p2 and appendix4 TablesD/E to audit each fitted outcome's source-estimate selection. Recover an incidence-only fitted curve, or supply a matching original incidence-specific risk model; document first vs recurrent, fatal/nonfatal and MI vs broaderIHD definitions. Do not silently pool or average endpoints. TableF knots alone do not resolve that gate.
3. GBD2023: primary disease appendix1 mmc1.pdf, expected82,917,810bytes, publisher DOI10.1016/S0140-6736(25)01637-X. The open fulltextXML is locally archived and identifies the appendix. Exact IHD MI event aggregation and IS first/recurrent adjustment require that appendix. Public JACC2023 CVD methods URL is listed below; direct download returned403. No user database query is needed to redownload the already-verified incidence rates.
4. Other endpoints: endpoint-specific risk function or a cited, separately approved structural CRA mapping; rawGBD endpoint availability does not suffice.
5. Work: reconcile universalR3>=R2 with baseline-branchR3. The current formulas supply a counterexample550->660 versus600; retain the formulas unless Work explicitly changes them. Confirm whether an original Bayesian dose-function reconstruction or labelled grid interpolation is acceptable after distributions and endpoints are resolved.
'''+f'\nGBD CVD methods: {GBD_CVD}\nWHO monitoring reference: {WHO}\n'
    (R6/'reports/INPUT_RELEASE_REQUIREMENTS.md').write_text(gap,encoding='utf-8',newline='\n')
    handoff=f'''# Round6 handoff

Worktree: E:\\工作目录\\China-PA-13\\Analysis
Directory: new_study/round6_multiscenario_cra
Branch: codex/multiscenario-cra-round6
Base: e307f03b1fb824711365378c940bcd0c25544d86
Commit: obtain the exact delivered SHA with git rev-parse HEAD; no self-referential commit string is embedded.

Status: {report['analysis_status']}.
Five scenarios/eight path variants are implemented. B0 population and incidence reference projections run. P15 andR1 inactivity margins and categorical source-risk PIF envelopes run. R2/R3 full effects remain BLOCKED_EXPOSURE_DISTRIBUTION. All new intervention incident outcomes remain BLOCKED_ENDPOINT_ALIGNMENT. Deaths,YLD,YLL,DALY,prevalence and patient-year effects remain BLOCKED_OUTCOME_RISK_MAPPING. No missing effect is filled with0.

Recovered evidence:104 source-verified Kyu continuous-dose knots with pointwiseUI (52 per disease), including exact600 estimates distinct from low-active category means. Protocol and supplied-study tables show an unresolved incidence/mortality selection gate. GBD2023 original fulltextXML is archived locally; exact disease appendix download and primary definition checks remain pending. RAND formulas and outset timing were verified through the web PDF parser; its local PDF download failed403. See the retrieval log and source review. WHO formal monitoring uses2010 reference, age-standardized18+; P15 remains the researcher's15%-from2025 magnitude scenario.

P15 regression:1664 rows independently match old results, maximum absolute difference {max(r['absolute_difference'] for r in regression):.12g}. The old totals are IHD45531.007/116899.570/547363.017 andIS57420.852/143733.241/598423.448 for2025-2030/2034/2050, respectively. They are regression evidence only; they are not newly admitted or renamedR1.

New clinical scenario comparisons therefore expose blank effect cells and explicit release conditions. Their B0 rates/popuIations are common. Uncertainty in RR knots and surveyCI is retained at source; no independent joint uncertainty or economicPSA is generated. Immediate and common-time paths are explicit; cumulative windows record inclusive calendar-year counts and the instantaneous-response assumption.

Specification conflict: mandatedR3 does not universally dominateR2 (baseline550 yields600 versus660). Tests retain the counterexample, rather than changing the scenario. Work must decide this condition; risk ordering is not frozen.

Read METHODS_MULTISCENARIO_CRA.md, INPUT_RELEASE_REQUIREMENTS.md and results/outcome_admission_matrix.csv before admitting any effect. No old-round file or rawZIP was changed. No individual data was uploaded. No medical/care costs, productivity, GDP, CEA, economicPSA or natural-history model was executed. Main was not merged.
'''
    (R6/'reports/HANDOFF_ROUND6.md').write_text(handoff,encoding='utf-8',newline='\n')

def build():
    for name in ['inputs','results','reports','logs','notebooks','notebooks/executed']:(R6/name).mkdir(parents=True,exist_ok=True)
    locks=verify_old_inputs();baseline=population_exposure();rates,metadata=gbd_rates();grid=extract_continuous_rr();cats=category_rr()
    write_csv(R6/'inputs/kyu_continuous_rr_knots.csv',grid)
    write_csv(R6/'inputs/parameter_register.csv',register_parameters(grid,cats,rates,baseline))
    admission=endpoint_admission();write_csv(R6/'inputs/rr_endpoint_admission.csv',admission)
    write_csv(R6/'inputs/exposure_input_inventory.csv',exposure_inventory())
    matrix=[]
    for r in admission:
        for scenario in ['B0','P15','R1','R2','R3']:matrix.append(dict(r,scenario=scenario,effect_status='REFERENCE_ONLY' if scenario=='B0' else r['admission_status']))
    write_csv(R6/'results/outcome_admission_matrix.csv',matrix)
    exposures=exposure_rows(baseline);write_csv(R6/'results/scenario_exposure_age_sex.csv',exposures)
    write_csv(R6/'results/scenario_exposure_summary.csv',national_exposure(exposures))
    pifs,events=risk_and_incidence(baseline,rates,cats);write_csv(R6/'results/pif_age_sex_disease_scenario.csv',pifs)
    write_csv(R6/'results/incidence_age_sex_year_scenario.csv',events)
    write_csv(R6/'results/scenario_comparison_summary.csv',comparison_summary(events))
    regression=legacy_regression(baseline,rates);write_csv(R6/'results/legacy_p15_regression.csv',regression)
    write_csv(R6/'results/legacy_p15_regression_summary.csv',legacy_summaries(regression))
    blocked=[dict(gap_id='EXPOSURE_FULL_DISTRIBUTION',scenarios='P15/R1 continuous; R2/R3 all',status='BLOCKED_EXPOSURE_DISTRIBUTION',requirement='Approved weighted China age-sex total gross MET distribution; no European shape substitution'),dict(gap_id='EXPOSURE_ACTIVE_CATEGORY_SHARES',scenarios='P15/R1 category point estimate',status='BLOCKED_EXPOSURE_DISTRIBUTION',requirement='Measured active category shares; current envelope remains a structural diagnostic'),dict(gap_id='RR_INCIDENCE_SELECTION',scenarios='all intervention incidence effects',status='BLOCKED_ENDPOINT_ALIGNMENT',requirement='Incidence-only fitted curve matched to GBD disease/event definition'),dict(gap_id='GBD_IHD_EVENT_DEFINITION',scenarios='IHD intervention incidence',status='BLOCKED_NO_SOURCE',requirement='GBD2023 appendix1 exact MI first/recurrent event aggregation; do not infer from cause name'),dict(gap_id='OTHER_ENDPOINTS',scenarios='all intervention deaths/YLD/YLL/DALY/prevalence/patient-years',status='BLOCKED_OUTCOME_RISK_MAPPING',requirement='Endpoint-specific RR or approved cited structural CRA mapping'),dict(gap_id='R3_ORDERING_CONFLICT',scenarios='R3 vs R2',status='SPEC_CONFLICT_R3_VS_R2_ORDERING',requirement='Work decision: formulas do not imply universal R3 dominance'),dict(gap_id='RR_INTERPOLATION_TAILS',scenarios='continuous distribution evaluation',status='BLOCKED_NO_SOURCE',requirement='Original spline function/joint draws or approved labelled interpolation; tails >30600 cannot be extrapolated')]
    write_csv(R6/'results/blocked_inputs.csv',blocked)
    report=dict(analysis_status='PARTIAL_CRA_INTERFACES_COMPLETE_CLINICAL_EFFECTS_BLOCKED',branch=config()['branch'],baseline=config()['baseline_commit'],population_2025=sum(r['population'] for r in baseline if r['year']==2025),baseline_2025_p=sum(r['population']*r['p_inactive'] for r in baseline if r['year']==2025)/sum(r['population'] for r in baseline if r['year']==2025),source_locks=locks,gbd=metadata,continuous_rr_knots=len(grid),scenario_variants=len(VARIANTS),scenario_status={'B0':'REFERENCE_PROJECTION_READY','P15':'INACTIVITY_MARGIN_AND_CATEGORY_RISK_ENVELOPE_READY; CLINICAL_EFFECT_BLOCKED','R1':'INACTIVITY_MARGIN_AND_CATEGORY_RISK_ENVELOPE_READY; CLINICAL_EFFECT_BLOCKED','R2':'BLOCKED_EXPOSURE_DISTRIBUTION','R3':'BLOCKED_EXPOSURE_DISTRIBUTION'},clinical_effect_status='BLOCKED_ENDPOINT_ALIGNMENT',other_outcomes='BLOCKED_OUTCOME_RISK_MAPPING',ordering_requirement='SPEC_CONFLICT_R3_VS_R2_ORDERING',round5_status='BLOCKED_TRANSITION_CALIBRATION; NOT_EXECUTED',old_p15_regression_rows=len(regression),old_p15_max_difference=max(r['absolute_difference'] for r in regression),pif_rows=len(pifs),incidence_rows=len(events),evidence_admission_is_separate_from_software_tests=True)
    write_json(R6/'results/model_validation_report.json',report);write_json(R6/'raw/GBD_incidence_source_pointer.json',metadata)
    reports(report,regression);notebooks()
    print(json.dumps({k:report[k] for k in ['analysis_status','continuous_rr_knots','population_2025','old_p15_regression_rows','old_p15_max_difference','pif_rows','incidence_rows']},indent=2),flush=True)
    return report

if __name__=='__main__':build()
