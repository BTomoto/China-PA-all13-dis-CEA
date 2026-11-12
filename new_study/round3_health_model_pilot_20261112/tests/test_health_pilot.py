import csv
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import health_pilot as hp
from dynamic_outcomes import DiseaseTransitions, TransitionParametersMissing, cohort_outcomes


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario = hp.scenario_rows()
        cls.raw, _, _ = hp.raw_gbd()
        cls.rates, cls.numbers, cls.selected = hp.validated_rates(cls.raw)
        cls.detail = hp.incidence_rows(cls.scenario, cls.rates)

    def test_population_and_target(self):
        s2025 = [r for r in self.scenario if r["year"] == 2025]
        self.assertEqual(sum(r["population"] for r in s2025), 1113252964)
        p2025 = sum(r["inactive_persons_baseline"] for r in s2025)/1113252964
        self.assertAlmostEqual(p2025, .219660515, places=9)
        self.assertAlmostEqual(p2025*.85, .186711438, places=9)
        for r in self.scenario:
            self.assertAlmostEqual(r["p_inactive_intervention"], r["p_inactive_baseline"]*hp.reduction_factor(r["year"]))
            if r["year"] >= 2030:
                self.assertAlmostEqual(r["p_inactive_intervention"],r["p_inactive_baseline"]*.85)

    def test_2030_fixed_2025_weights(self):
        s = [r for r in self.scenario if r["year"] == 2025]
        fixed = sum(r["population"]*r["p_inactive_baseline"]*.85 for r in s)/sum(r["population"] for r in s)
        self.assertAlmostEqual(fixed,.186711438,places=9)

    def test_demographic_crude_rate_can_change(self):
        def crude(year):
            x = [r for r in self.scenario if r["year"] == year]
            return sum(r["inactive_persons_intervention"] for r in x)/sum(r["population"] for r in x)
        self.assertNotAlmostEqual(crude(2030), crude(2050), places=7)

    def test_95plus_population_aggregation(self):
        grouped = hp.grouped_scenario(self.scenario)
        for year in range(2025,2051):
            for sex in ("Male","Female"):
                source = [r for r in self.scenario if r["year"]==year and r["sex"]==sex and r["age_group"] in ("95-99","100+")]
                target = next(r for r in grouped if r["year"]==year and r["sex"]==sex and r["age_group"]=="95+")
                self.assertEqual(target["population"],sum(r["population"] for r in source))

    def test_pif_sign_and_zero(self):
        for disease in hp.RR:
            rr = hp.RR[disease][2]
            self.assertEqual(hp.pif(.3,.3,rr),0.)
            self.assertGreaterEqual(hp.pif(.3,.255,rr),0.)

    def test_disease_mapping_and_subtypes(self):
        self.assertEqual(set(hp.RR), {"IHD","IS"})
        self.assertNotEqual(hp.RR["IHD"][2],hp.RR["IS"][2])
        self.assertNotIn("Intracerebral hemorrhage", str(hp.RR))
        self.assertNotIn("Subarachnoid hemorrhage", str(hp.RR))
        for r in self.detail:
            self.assertEqual(r["cause_name"],hp.RR[r["disease"]][0])
            self.assertLessEqual(r["incident_cases_averted"],r["baseline_expected_incidence"])

    def test_detail_summary_reconciliation(self):
        summary = hp.summaries(self.detail)
        for s in summary:
            year_end = int(s["period"][-4:]) if s["period_type"] != "annual" else int(s["period"])
            subset = [r for r in self.detail if r["disease"] == s["disease"] and
                      (r["year"] == year_end if s["period_type"] == "annual" else r["year"] <= year_end)]
            self.assertTrue(math.isclose(s["incident_cases_averted"],sum(r["incident_cases_averted"] for r in subset),rel_tol=1e-12,abs_tol=1e-6))

    def test_gbd_missing_fails_closed(self):
        with self.assertRaisesRegex(FileNotFoundError,"BLOCKED_GBD_RATE_INPUT"):
            hp.raw_gbd(HERE/"raw"/"not_an_export.zip")
        broken = self.raw[:-1]
        with self.assertRaisesRegex(ValueError,"BLOCKED_GBD_RATE_INPUT"):
            hp.validated_rates(broken)

    def test_fee_link_exact_semantics(self):
        rows = hp.read_csv(HERE/"frozen_cost_link_semantic_fix.csv")
        dep = next(r for r in rows if r["cost_id"] == "DC-DEP-CN-2015")
        self.assertEqual(dep["link_type"],"CANDIDATE_LINK")
        for r in rows:
            if r["link_type"] == "EXACT_LINK":
                for field in ("same_original_study","exact_amount_match","exact_currency_match","exact_cost_definition_match","assignment_allowed"):
                    self.assertEqual(r[field],"TRUE",(r["cost_id"],field))

    def test_dynamic_missing_fails_closed(self):
        with self.assertRaisesRegex(TransitionParametersMissing,"BLOCKED_DYNAMIC_PARAMETERS"):
            cohort_outcomes(1.0,DiseaseTransitions())


if __name__ == "__main__":
    unittest.main()
