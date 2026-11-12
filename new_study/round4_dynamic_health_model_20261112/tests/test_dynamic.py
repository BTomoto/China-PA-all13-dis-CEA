import csv
import math
import unittest

from src.dynamic_model import (R3, R4, RAW_SHA, InputBlocked, Transition, age_at,
                               competing_exits, incidence_input, missing_parameter, pif, multicategory_pif,
                               read_csv, run_cohorts, summarize, synthetic_fixture,
                               verify_rate_number_pairs, verify_raw)


class DynamicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=incidence_input()

    def test_01_raw_sha(self): self.assertEqual(verify_raw(),RAW_SHA)
    def test_02_row_count(self): self.assertEqual(len(self.source),1664)
    def test_03_no_policy_pif(self): self.assertEqual(pif(.2,.2,1.2),0)
    def test_04_lower_exposure_positive(self): self.assertGreaterEqual(pif(.3,.25,1.2),0)
    def test_05_avoided_le_baseline(self): self.assertTrue(all(float(r['incident_cases_averted'])<=float(r['baseline_expected_incidence']) for r in self.source))
    def test_06_2025_zero(self): self.assertTrue(all(float(r['incident_cases_averted'])==0 for r in self.source if r['year']=='2025'))
    def test_07_2030_target(self): self.assertTrue(all(math.isclose(float(r['p_inactive_intervention']),float(r['p_inactive_baseline'])*.85,abs_tol=1e-12) for r in self.source if r['year']=='2030'))
    def test_08_post2030_fixed(self): self.assertTrue(all(math.isclose(float(r['p_inactive_intervention']),float(r['p_inactive_baseline'])*.85,abs_tol=1e-12) for r in self.source if int(r['year'])>2030))
    def test_09_disease_specific_rr(self): self.assertEqual({d:{r['rr_inactive_vs_low_active'] for r in self.source if r['disease']==d} for d in ('IHD','IS')},{'IHD':{'1.19474313'},'IS':{'1.18623962'}})
    def test_10_no_hemorrhagic(self): self.assertEqual({r['disease'] for r in self.source},{'IHD','IS'})
    def test_11_population_2025(self): self.assertEqual(sum(int(r['population']) for r in read_csv(R3/'inputs'/'scenario_age_sex_2025_2050.csv') if r['year']=='2025'),1113252964)
    def test_12_age_advance(self): self.assertEqual(age_at('20-24',5),'25-29')
    def test_13_age_95_open(self): self.assertEqual(age_at('90-94',5),'95+')
    def test_14_competing_conservation(self):
        exits,survive=competing_exits(100,(.1,.2,.3));self.assertAlmostEqual(sum(exits)+survive,100)
    def test_15_rate_number_pairs(self): self.assertEqual(len(verify_rate_number_pairs()),64)
    def test_16_missing_parameters_close(self):
        with self.assertRaises(InputBlocked):run_cohorts(self.source[:1],missing_parameter)
    def test_17_fixture_cannot_formal(self):
        with self.assertRaises(InputBlocked):run_cohorts(self.source[:1],synthetic_fixture)
    def test_18_nonnegative_patient_years(self):
        rows,_=run_cohorts(self.source[69:70],synthetic_fixture,allow_provisional=True)
        self.assertTrue(all(r['prevalent_patient_years_averted']>=0 for r in rows))
    def test_19_daly_identity(self):
        rows,_=run_cohorts(self.source[69:70],synthetic_fixture,allow_provisional=True)
        self.assertTrue(all(math.isclose(r['DALY_averted'],r['YLD_averted']+r['YLL_averted']) for r in rows))
    def test_20_deaths_bounded_by_entry(self):
        rows,_=run_cohorts(self.source[69:70],synthetic_fixture,allow_provisional=True)
        self.assertLessEqual(sum(r['disease_deaths_averted'] for r in rows),float(self.source[69]['incident_cases_averted'])+1e-8)
    def test_21_no_pre_entry(self):
        source=self.source[200:201];rows,_=run_cohorts(source,synthetic_fixture,allow_provisional=True)
        self.assertTrue(all(r['year']>=int(source[0]['year']) for r in rows))
    def test_22_repeat_determinism(self):
        one,_=run_cohorts(self.source[200:201],synthetic_fixture,allow_provisional=True)
        two,_=run_cohorts(self.source[200:201],synthetic_fixture,allow_provisional=True)
        self.assertEqual(one,two)
    def test_23_aggregation(self):
        rows,_=run_cohorts(self.source[200:202],synthetic_fixture,allow_provisional=True)
        summary=summarize(rows);total=next(r for r in summary if r['disease']=='TOTAL')
        self.assertAlmostEqual(total['DALY_averted'],sum(r['DALY_averted'] for r in rows))
    def test_24_no_active_dynamic_results(self): self.assertTrue(all(r['result_status']=='BLOCKED_DYNAMIC_PARAMETERS' and r['DALY_averted']=='' for r in read_csv(R4/'results'/'dynamic_results_summary.csv')))
    def test_25_multicategory_missing_blocks(self):
        with self.assertRaises(InputBlocked): multicategory_pif(None,None,[1,.84,.77,.75])
    def test_26_multicategory_identity(self): self.assertEqual(multicategory_pif([.2,.3,.3,.2],[.2,.3,.3,.2],[1,.84,.77,.75]),0)
    def test_27_frozen_cumulative(self):
        for disease,expected in (('IHD',547363.017),('IS',598423.448)):
            actual=sum(float(r['incident_cases_averted']) for r in self.source if r['disease']==disease)
            self.assertAlmostEqual(actual,expected,places=3)
    def test_28_category_rr_present(self):
        rows=read_csv(R4/'inputs'/'kyu_category_rr.csv')
        self.assertEqual(len(rows),8)
        self.assertTrue(all(r['exposure_share_status']=='MISSING_AGE_SEX_CATEGORY_SHARES' for r in rows))
    def test_29_zero_policy_zero_dynamic(self):
        zero=[dict(self.source[200],incident_cases_averted='0')]
        rows,_=run_cohorts(zero,synthetic_fixture,allow_provisional=True)
        self.assertTrue(all(r['DALY_averted']==0 and r['disease_deaths_averted']==0 for r in rows))
    def test_30_cross_disease_transition_rejected(self):
        source=[self.source[200]]
        def wrong(disease,sex,age,duration):return synthetic_fixture('IS' if disease=='IHD' else 'IHD',sex,age,duration)
        with self.assertRaises(ValueError):run_cohorts(source,wrong,allow_provisional=True)
    def test_31_two_disease_aggregation(self):
        source=[next(r for r in self.source if r['disease']==d and int(r['year'])>2025) for d in ('IHD','IS')]
        rows,_=run_cohorts(source,synthetic_fixture,allow_provisional=True)
        summary={r['disease']:r for r in summarize(rows)}
        self.assertAlmostEqual(summary['TOTAL']['DALY_averted'],summary['IHD']['DALY_averted']+summary['IS']['DALY_averted'])

if __name__=='__main__':unittest.main()
