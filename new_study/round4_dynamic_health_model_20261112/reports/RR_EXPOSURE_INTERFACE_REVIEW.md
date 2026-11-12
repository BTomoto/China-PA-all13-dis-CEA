# RR–exposure interface review

Kyu et al. (BMJ 2016) Table 1 reports total physical activity classes `<600`, `600–3999`, `4000–7999`, and `≥8000` MET-min/week. The original table is preserved at `new_study/round1_20261112/raw/rr/Kyu2016.html`; its eight IHD/ischemic-stroke estimates are extracted to `inputs/kyu_category_rr.csv` with point and 95% uncertainty intervals. The earlier pilot's inverse RR for `<600` versus `600–3999` agrees with the table after inversion within rounding. No new RR was estimated.

The previous binary PIF treats **all persons ≥600 as if their risk were the 600–3999 reference risk of one**. It is a low-active-reference binary approximation. It is **not** an observed `<600` versus all `≥600` RR and does assume identical reference risk among existing active categories. Its results are now `PILOT_CONDITIONAL_RR_DENOMINATOR`; they are a structural pilot, not a formal main analysis.

The repository contains no approved China age × sex × four-category activity shares. The 2018 CCDRFS data provide only `<600` fractions. Kyu mentions GBD 2013 estimated activity distributions for mapping qualitative studies, but those estimates are not present here as a reusable current China input. `multicategory_pif` requires complete externally supplied shares for both scenarios and fails closed when absent. No individual-level data are used.

For shares `q0_i`, `q1_i` and original Table 1 category risks `r_i` (relative to inactive), the multicate formula is `(Σq0_i r_i − Σq1_i r_i)/Σq0_i r_i`. Work must decide how movers distribute across the active categories and whether the source distribution matches the policy scenario before this can be used.

Source: [Kyu et al., BMJ 2016](https://www.bmj.com/content/354/bmj.i3857), Table 1.
