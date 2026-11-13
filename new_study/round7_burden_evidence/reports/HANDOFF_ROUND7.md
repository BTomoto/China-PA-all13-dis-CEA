# Round7 handoff
Local path: `E:\工作目录\China-PA-13\Analysis\new_study\round7_burden_evidence`
Branch: `codex/burden-evidence-round7`
Base: `1a2a8f11a0dd5c813d2cd35b18e906ea66dedc50`
Publication commit: obtain full SHA from the isolated branch tip / final delivery message; no self-referential commit hash embedded in its own contents.

## What changed
Only this new directory. Inventory acquisition scripts, src/model.py + src/pipeline.py, run_round7.py, config, evidence registers, source-locked aggregate inputs,5executable Notebooks, computed totals and identification envelopes, figures, reports, run logs, dependency versions and SHA manifest. Raw new public documents remain local in raw/; links, hashes and metadata are published, original source files stay untouched.

## New evidence actually obtained
Downloaded CKB published aggregate quintile data and extracted5rows; CHNS public main text recovered category definitions/sampling, but required joint proportions and supplement were not recovered. Kyu TableF expanded from104to260rows covering5diseases, and the incorrect blanket endpoint veto was revised. Brazilian Kyu mortalityCRA public primary text archived; new Chinese firsteverIS firstyear medical and patient productivity amounts verified; official2025urban wage parameters verified. RAND workplace sample is confirmed not mainlandChina.

## Results actually generated
9984 age-sex-year disease total cells, 312 national disease-endpoint-year totals; 82025attribution rows; 428annual bounded/blocked scenario rows and 9984age-sex decomposition rows. The new calculations comprise conservative exact600 identification envelopes and separate low-category proxy sensitivities for IHD/IS events and30–69mortality. They are real executed numeric analyses, NOT national point estimates or95%UIs. Baseline disease burden is never labelled alreadyPAattributed. R2/R3national benefits remain unidentified. YLD/YLL/DALY/Prevalence attribution is not released; their disease totals exist separately.

Population2025=1,113,252,964; weighted inactivity=21.9660515204%. Fixed2025weights at85%=18.6711437924%; future crude rates vary. P15=.15R1 completed-target identity is algebra, not a finding. Both inactive/active decomposition, zero/within-inactive shape and active tail remain needed forR3.

## Remaining actions
1. Request the precise authorised China weighted dose-bin aggregates specified in remaining_data_requests.csv, including zeros, below600, active support and tail>25500/30600. No need to upload individual records. No nationwide fine distribution recovered in checked inventory.
2. Work decides whether event endpoint transport, public-precedent30–69 mortality sensitivity and proposed local-shape calibration are appropriate for manuscript analyses. No sensitivity is silently promoted to main.
3. User-login GBD2023risk-attributed export query is specified with unverified filter capabilities labelled.13local export members contain no risk dimensions. Need actual2023TMREL/method source, not2019/2021assumption; externalGBD attribution must remain separate.
4. Obtain recent rawT2D/breast and colon-only burden (if tool supports); resolve Carlsson selectedT2DvsLADA table; preserve all13candidate disease distinctions.
5. Follow up CNSRIII pricecalendar/survivor coverage and Chinese age-sex employment/wage/WPAI inputs. No economic aggregate qualifies yet.

## Reproduce and scope
From repo `.venv/Scripts/python.exe new_study/round7_burden_evidence/run_round7.py --execute-notebooks`. Evidence download scripts are optional acquisition only; computational run is offline with local locked inputs. Checks distinguish software/data integrity from scientific gates. See validation_report.json and notebook_execution.json for actual statuses. Figures show observed grid/identified ranges only.
No R1–6 or original ZIP modifications; no individual-record access, natural-history, patient-years, CEA, policy cost, CGE orPSA run; no main merge. Some objectives remain evidence-blocked and must not be described as full national scenario point-result completion.

## 2030 numerical illustration: conservative identification envelopes

Disease | Endpoint | Scope | Scenario | Lower | Upper
--- | --- | --- | --- | ---: | ---:
IHD | Incidence | China20+ | R1 | 0.0 | 198,699.5
IHD | Incidence | China20+ | P15 | 0.0 | 29,804.9
IHD | Deaths | China30-69 | R1 | 0.0 | 46,370.7
IHD | Deaths | China30-69 | P15 | 0.0 | 6,955.6
IS | Incidence | China20+ | R1 | 0.0 | 274,684.8
IS | Incidence | China20+ | P15 | 0.0 | 41,202.7
IS | Deaths | China30-69 | R1 | 0.0 | 16,581.9
IS | Deaths | China30-69 | P15 | 0.0 | 2,487.3

These are weak outer bounds conditional on a cause-event/mortality transport sensitivity, not an expected benefit or95%UI. They demonstrate the consequence of unidentified within-inactive and active dose distributions. Low-category proxy results are separate rows and must not be substituted for exact600.

Additional resolved risk facts: Schuch2018 adult high-vs-low adjustedOR0.78(0.70–0.87), notRR; older subgroup is separate. Liu2017 leisure PA per10MET-h/week RR0.94(0.92–0.96); inactive-vs-recommended contrast has upperCI0.97, a distinct contrast. Exposure domains and high/low categories still do not match totalgross600. No OR-to-RR substitution. Original abstracts PMID29690792/28348016 are recorded separately from fulltext. ChinaT2D incident-complication cost source DOI10.1007/s13300-020-00967-y was additionally reviewed: MI onset-quarter cost19633CNY is NOT T2D-own firstyear cost and must not duplicate IHD costs.
