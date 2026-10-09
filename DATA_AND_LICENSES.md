# Data and licensing notes

The workbook contains population, disease burden, relative-risk, policy, cost, and economic inputs. Its `身体活动水平` sheet directly supplies the model baseline: the 22 age–sex proportions already refer to 2025 and are not extrapolated again. Other input tables retain their existing values.

The `psa_precision_n` column retains the original four-province stratum sizes solely as a precision assumption, matching Supplementary Table S18. Beta parameters are n × p + 0.5 and n × (1 − p) + 0.5. These pseudocounts are not national surveillance sample sizes; intervals and probabilities are conditional on this assumption. No individual survey records are included. Inputs and generated outputs are stored in readable formats.

IHME Global Burden of Disease inputs and derived tables remain subject to their source terms and attribution requirements:

- https://www.healthdata.org/data-tools-practices/data-practices/terms-and-conditions
- https://www.healthdata.org/data-tools-practices/data-practices/ihme-free-charge-non-commercial-user-agreement

Population inputs are based on United Nations World Population Prospects 2024: https://population.un.org/wpp/. Other parameter sources are recorded in the workbook and reference tables. Including third-party materials here does not grant additional redistribution rights.

No new open-source license is granted by this update. Project-generated code and documents retain the existing repository licensing position; see `LICENSE`.
