# Round 5 dynamic calibration method

All analysis runs locally in `E:\工作目录\China-PA-13\Analysis`, from remote base `1e2407664e79b75db3f8a5f8d4c79e5435e5e2dc`, branch `codex/dynamic-health-model-calibration-round5-20261112`.

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
