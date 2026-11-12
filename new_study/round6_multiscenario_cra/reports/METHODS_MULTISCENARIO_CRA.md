# Round 6 multi-scenario comparative risk methods

Local execution: E:\工作目录\China-PA-13\Analysis. Base e307f03b1fb824711365378c940bcd0c25544d86; branch codex/multiscenario-cra-round6. Round5 remains BLOCKED_TRANSITION_CALIBRATION and is not called. All current computations use round6 src only.

## Population, exposure and scenarios

WPP2024 Medium July1 is model-estimated population. The 2025 exposure start is modelled using 2018 CCDRFS sex/coarse-age insufficient-activity observations assigned without interpolation to fine age groups. Shared-source CIs remain shared, not independent fine-age estimates. WPP95-99 and100+ are combined for original GBD95+ rates. National crude exposure may change with population composition; 2030 rates equal .85 of baseline within each stratum, not a nationally fixed crude target.

B0 preserves age-sex prevalence. P15 moves .03 additional shares of baseline inactive mass each year through2030, capped .15. With measured activity atoms, every originally <600 atom splits its weight proportionately between its original dose and600. R1 uses max(x,600); R2 uses1.2*x including zeros; R3 uses600 for baseline x<600 and1.2*x otherwise. R1-R3 have both immediate2025 and common2030 mixture paths. A common path mixes baseline and transformed distributions, never interpolates RR. These are scenario assumptions, not observed behaviour. In the present data only inactivity margins are identified: R1/R3 target inactivity0, P15 .85*p0, R2 generally unknown. Means and full activity distributions remain blank.

Gao Methods sections2-3 define <150 moderate-equivalent minutes/week and retain bouts>=10min. Under conventional4MET moderate/8MET vigorous scoring,4*(moderate+2*vigorous)<600 is the same binary threshold; this does not recover a continuous exposure distribution. Only total conventional gross MET-min/week is contemplated. A marginal-MET or leisure-only scalar is not converted without duration, intensity and domain evidence. No category midpoints, generic European shape, individual exposure or within-category density is imputed.

## Dose-response evidence and PIF

Kyu appendix4 TableF p79-80 supplies 52 published dose knots per disease,0 to30600 in600 steps. At600 the original point RRs are IHD .909 (.857-.964) and IS .910 (.831-1.000), distinct from category averages .837 and .843. Exact knots are supported in code. Optional piecewise-linear interpolation is explicitly a numerical structural sensitivity, disabled by default; it is not the original Bayesian curve. No tail extrapolation is allowed. Marginal pointwise UIs do not supply joint curve uncertainty.

Continuous PIF=(weighted baseline RR-weighted scenario RR)/weighted baseline RR. Category PIF uses normalized category probabilities. Missing distributions fail closed. P15 and R1 also have an identifiable *categorical-model diagnostic envelope*, despite unknown active-category shares: for p=inactive fraction, alpha=moved fraction, rL=low-active category RR, the numerator is alpha*p*(1-rL); denominator is p+(1-p)*mean(active RR). Bounding the unknown active mean by the minimum/maximum published active-category RR yields the reported interval. No active distribution is estimated. It is a STRUCTURAL_SENSITIVITY_ONLY source-risk identification envelope, not a95%UI, continuous600-point effect, or admitted GBD burden effect. New effect point estimates remain blank. Category-risk differences versusP15 retain the same unknown denominator: replace alpha by alpha_s-alpha_P15 and reorder endpoints for negative differences. These are within-stratum source-risk comparisons, not GBD event-count differences or clinical confidence intervals. R2/R3 remain BLOCKED_EXPOSURE_DISTRIBUTION rather than artificial zero.

## Clinical endpoint gate

Kyu protocol appendix1 p2 permits new diagnoses and mortality; appendix4 TablesD/E includes reports of incidence and mortality. A separately selected incidence-only fitted RR curve has not been established. Consequently no new intervention PIF is multiplied by GBD incidence in this build. The IHD GBD2023 primary disease appendix still needs its exact MI/event aggregation and first/recurrent rules verified. The GBD-author stroke factsheet2026 Methods corroborates first-ever lifetime stroke; this does not by itself resolve Kyu's pooled outcome selection. Broad chronic IHD prevalence cannot be inferred from MI incidence or vice versa.

Other endpoints remain BLOCKED_OUTCOME_RISK_MAPPING, including deaths,YLD,YLL,DALY,prevalence and prevalent-equivalent patient-years. No dynamic model is restored. A publicly cited and Work-approved cross-endpoint mapping could later be a separately labelled STRUCTURAL_CRA_SENSITIVITY; none is silently enabled here. Prevalence*population*one year would mean prevalent-equivalent years, never followed incident-cohort patient-years.

## Comparisons and time

All scenario comparisons use the same WPP and verified GBD2023 rate tables. Primary endpoint comparison is2030;2034 and2050 are separate annual endpoints. Intervention incidence effects and differences versusP15 are blank pending admission. B0 model-estimated incident units are supplied as the common descriptive reference. The code records all years and cumulative2025-2030/2034/2050 windows;2025-2030 contains six calendar years. Calendar sums, if admitted later, require the explicitly recorded instantaneous-risk-response assumption; no lag length is invented. Endpoint counterfactual burdens are not claims of immediately realised annual policy benefits. Disease rates are held constant; only population changes. Historical disease trends are not extrapolated.

Old binary P15 is independently recomputed from locked WPP, exposure and raw GBD rates solely for regression. It assigns all active people the low-active risk in its denominator. Its six historical totals and1664 rows are preserved as REGRESSION_ONLY_NOT_RR_ADMISSION, never renamedR1 or merged into current admitted results.

## Mathematical specification conflict

R3>=R1 holds under a monotone decreasing risk function. UniversalR3>=R2 does not follow from the mandated formulas: baseline550 gives R2=660 andR3=600. Tests retain this counterexample and check R3>=R2 only under sufficient support restrictions (all initially inactive doses<=500). No scenario formula is changed to manufacture the requested ranking. This conflict is reported for Work; no clinical ordering is inferred with the present data.
