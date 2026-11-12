# Round6 handoff

Worktree: E:\工作目录\China-PA-13\Analysis
Directory: new_study/round6_multiscenario_cra
Branch: codex/multiscenario-cra-round6
Base: e307f03b1fb824711365378c940bcd0c25544d86
Commit: obtain the exact delivered SHA with git rev-parse HEAD; no self-referential commit string is embedded.

Status: PARTIAL_CRA_INTERFACES_COMPLETE_CLINICAL_EFFECTS_BLOCKED.
Five scenarios/eight path variants are implemented. B0 population and incidence reference projections run. P15 andR1 inactivity margins and categorical source-risk PIF envelopes run. R2/R3 full effects remain BLOCKED_EXPOSURE_DISTRIBUTION. All new intervention incident outcomes remain BLOCKED_ENDPOINT_ALIGNMENT. Deaths,YLD,YLL,DALY,prevalence and patient-year effects remain BLOCKED_OUTCOME_RISK_MAPPING. No missing effect is filled with0.

Recovered evidence:104 source-verified Kyu continuous-dose knots with pointwiseUI (52 per disease), including exact600 estimates distinct from low-active category means. Protocol and supplied-study tables show an unresolved incidence/mortality selection gate. GBD2023 original fulltextXML is archived locally; exact disease appendix download and primary definition checks remain pending. RAND formulas and outset timing were verified through the web PDF parser; its local PDF download failed403. See the retrieval log and source review. WHO formal monitoring uses2010 reference, age-standardized18+; P15 remains the researcher's15%-from2025 magnitude scenario.

P15 regression:1664 rows independently match old results, maximum absolute difference 5.00222085975e-12. The old totals are IHD45531.007/116899.570/547363.017 andIS57420.852/143733.241/598423.448 for2025-2030/2034/2050, respectively. They are regression evidence only; they are not newly admitted or renamedR1.

New clinical scenario comparisons therefore expose blank effect cells and explicit release conditions. Their B0 rates/popuIations are common. Uncertainty in RR knots and surveyCI is retained at source; no independent joint uncertainty or economicPSA is generated. Immediate and common-time paths are explicit; cumulative windows record inclusive calendar-year counts and the instantaneous-response assumption.

Specification conflict: mandatedR3 does not universally dominateR2 (baseline550 yields600 versus660). Tests retain the counterexample, rather than changing the scenario. Work must decide this condition; risk ordering is not frozen.

Read METHODS_MULTISCENARIO_CRA.md, INPUT_RELEASE_REQUIREMENTS.md and results/outcome_admission_matrix.csv before admitting any effect. No old-round file or rawZIP was changed. No individual data was uploaded. No medical/care costs, productivity, GDP, CEA, economicPSA or natural-history model was executed. Main was not merged.

<!-- ACTUAL_CHECKS -->
CurrentCRA tests:53/53; prior85 are historical, not rerun; standard notebooks5/5; checks10; scientific admissionBLOCKED; specification conflict1.

Uncommitted scientific source artifact: raw/GBD2023_nonfatal_fulltext.xml is intentionally LOCAL_ONLY_PUBLIC_SOURCE (hash in logs/input_integrity_manifest.csv). RAND and GBD appendix PDFs were not obtained and are not claimed as archived. Existing ignored ZIPs remain in their original paths. Unrelated user untracked files preserved: []. Git-tracked round6 changes are committed separately; Python environment, runtime kernels and rendered evidence-page previews are excluded.
