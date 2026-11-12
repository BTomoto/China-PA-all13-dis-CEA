import copy
import json
import math
import unittest
import numpy as np
from src.common import R5,AGES,InputBlocked,config,frozen_incidence,read_csv
from src.population_reconciliation import load_sources,reconcile
from src.hazard_conversion import rate_to_hazard,hazard_to_probability,subtract_target,prepare as hazards
from src.outcome_mapping import prepare as mappings,checked_ratio
from src.transition_calibration import profile,calibrate
from src.dynamic_cohort_model import advance_age,cycle,run,aggregate,OUTCOMES

def fixture():
    """In-memory unit-test fixture; never written to input or real result files."""
    parameters=[];others=[];weights=[];years=[]
    for d in ['IHD','IS']:
        for s in ['Male','Female']:
            for a in AGES:
                base=dict(disease=d,sex=s,age=a)
                parameters.append(dict(base,calibrated_case_fatality_hazard=.01 if d=='IHD' else .03,admission_status='SYNTHETIC_TEST_ONLY'))
                others.append(dict(disease_model=d,sex=s,age=a,other_cause_hazard=.02))
                weights.append(dict(base,effective_disability_weight=.1))
                years.append(dict(base,YLL_per_death=10.))
    return parameters,others,weights,years

class Round5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data,cls.audit=load_sources();cls.pop=reconcile(cls.data)
        cls.conversions,cls.others=hazards(cls.data);cls.weights,cls.years=mappings(cls.data['disease'])
        cls.parameters=read_csv(R5/'inputs/case_fatality_parameters.csv')
        cls.summary=json.loads((R5/'calibration_summary.json').read_text())
        cls.inc=frozen_incidence();cls.fixture=fixture()

    def test_01_cross_export_population(self):self.assertTrue(all(r['relative_difference']<1e-8 for r in self.pop))
    def test_02_rate_hazard(self):self.assertAlmostEqual(rate_to_hazard(1200),.012)
    def test_03_probability(self):self.assertAlmostEqual(hazard_to_probability(.012),1-math.exp(-.012))
    def test_04_hazard_subtraction(self):self.assertAlmostEqual(subtract_target(.03,.01),.02)
    def test_05_negative_other_fails(self):
        with self.assertRaises(InputBlocked):subtract_target(.01,.02)
    def test_06_no_double_death(self):
        for r in self.others:self.assertAlmostEqual(r['other_cause_hazard']+r['target_disease_population_mortality_hazard'],r['all_cause_hazard'])
    def test_07_first_half_cycle(self):self.assertEqual(cycle(1,0,0,.5),(1,.5,0,0))
    def test_08_later_full_cycle(self):self.assertEqual(cycle(1,0,0,1),(1,1,0,0))
    def test_09_half_competition(self):
        survive,py,d,o=cycle(100,.02,.03,.5)
        self.assertAlmostEqual(d+o,100*(1-math.exp(-.05*.5)))
        self.assertAlmostEqual(d/(d+o),.4)
    def test_10_annual_flow(self):
        v=np.zeros(16);v[0]=100;out=advance_age(v)
        self.assertEqual((out[0],out[1]),(80,20))
    def test_11_flow_conservation(self):
        v=np.arange(16,dtype=float);self.assertAlmostEqual(sum(advance_age(v)),sum(v))
    def test_12_dw_range(self):self.assertTrue(all(0<=r['effective_disability_weight']<=1 for r in self.weights))
    def test_13_dw_metric_ratio(self):self.assertTrue(all(math.isclose(r['effective_disability_weight'],r['rate_ratio'],rel_tol=1e-9) for r in self.weights))
    def test_14_yll_metric_ratio(self):self.assertTrue(all(math.isclose(r['YLL_per_death'],r['rate_ratio'],rel_tol=1e-9) for r in self.years))
    def test_15_daly_identity(self):
        rows=run(self.inc,*self.fixture,calibration_passed=True,synthetic=True)
        self.assertTrue(all(r['DALY_averted']==r['YLD_averted']+r['YLL_averted'] for r in rows))
    def test_16_death_entry_bound(self):
        rows=run(self.inc,*self.fixture,calibration_passed=True,synthetic=True)
        for d in ['IHD','IS']:
            self.assertLessEqual(sum(r['target_disease_deaths_averted'] for r in rows if r['disease']==d),sum(r['incident_cases_averted'] for r in rows if r['disease']==d))
    def test_17_no_policy_zero(self):
        rows=run([dict(r,incident_cases_averted=0) for r in self.inc],*self.fixture,calibration_passed=True,synthetic=True)
        self.assertTrue(all(r[m]==0 for r in rows for m in OUTCOMES))
    def test_18_disease_parameter_isolation(self):
        changed=copy.deepcopy(self.fixture)
        for r in changed[0]:
            if r['disease']=='IHD':r['calibrated_case_fatality_hazard']=.5
        a=run(self.inc,*self.fixture,calibration_passed=True,synthetic=True)
        b=run(self.inc,*changed,calibration_passed=True,synthetic=True)
        self.assertEqual([r for r in a if r['disease']=='IS'],[r for r in b if r['disease']=='IS'])
    def test_19_synthetic_not_empirical(self):
        with self.assertRaises(InputBlocked):run(self.inc,*self.fixture,calibration_passed=True)
    def test_20_outputs_never_synthetic(self):
        self.assertFalse(any('SYNTHETIC' in str(r) for r in read_csv(R5/'results/dynamic_results_age_sex_year.csv')))
    def test_21_fit_gate_not_optimizer_success(self):
        cfg=config()['calibration']
        for group in self.summary['groups']:
            expected=group['optimizer_success'] and group['maximum_relative_error']<=cfg['maximum_relative_error'] and group['rms_relative_error']<=cfg['rms_relative_error']
            self.assertEqual(group['status']=='PASS',expected)
        if not self.summary['all_groups_pass']:
            with self.assertRaises(InputBlocked):run(self.inc,self.parameters,self.others,self.weights,self.years,calibration_passed=False)
    def test_22_repeat_determinism(self):
        self.assertEqual(run(self.inc,*self.fixture,calibration_passed=True,synthetic=True),run(self.inc,*self.fixture,calibration_passed=True,synthetic=True))
    def test_23_95_open(self):
        v=np.zeros(16);v[-1]=100;self.assertTrue(np.array_equal(advance_age(v),v))
    def test_24_five_flows(self):
        v=np.zeros(16);v[0]=100
        for _ in range(5):v=advance_age(v)
        self.assertAlmostEqual(v[0],32.768);self.assertGreater(sum(v[1:]),50)
    def test_25_negative_stock_rejected(self):
        with self.assertRaises(ValueError):advance_age([-1]+[0]*15)
    def test_26_raw_zip_hashes(self):self.assertEqual(len(self.audit),3);self.assertTrue(all(a['sha256']==config()['raw_inputs'][a['dataset']]['sha256'] for a in self.audit))
    def test_27_frozen_incidence_rates(self):
        for r in self.inc:
            self.assertTrue(math.isclose(float(r['baseline_rate_per_100k']),self.data['incidence'][(r['disease'],r['sex'],r['age_group'],'Incidence','Rate')],rel_tol=1e-8))
    def test_28_blank_dynamic_if_blocked(self):
        if not self.summary['all_groups_pass']:
            self.assertTrue(all(r[m]=='' for r in read_csv(R5/'results/dynamic_results_age_sex_year.csv') for m in OUTCOMES[1:]))
    def test_29_outcome_metric_mismatch_rejected(self):
        data=copy.deepcopy(self.data['disease']);data[('IHD','Male','20-24','Prevalence','Number')]*=2
        with self.assertRaises(InputBlocked):mappings(data)
    def test_30_flow_and_death_tracking(self):
        rows=run(self.inc,*self.fixture,calibration_passed=True,synthetic=True)
        for d in ['IHD','IS']:
            for s in ['Male','Female']:
                entries=sum(r['incident_cases_averted'] for r in rows if r['disease']==d and r['sex']==s)
                exits=sum(r['target_disease_deaths_averted']+r['other_cause_deaths_competing'] for r in rows if r['disease']==d and r['sex']==s)
                final=sum(r['end_stock_before_age_flow'] for r in rows if r['disease']==d and r['sex']==s and r['year']==2050)
                self.assertAlmostEqual(entries,exits+final,places=7)
    def test_31_calibration_nonnegative_and_smooth(self):
        self.assertTrue(all(float(p['calibrated_case_fatality_hazard'])>0 for p in self.parameters))
        self.assertTrue(all(g['integration_half_step_max_difference']<1e-5 for g in self.summary['groups']))
    def test_32_no_burden_PIF(self):
        self.assertNotIn('pif(', (R5/'src/dynamic_cohort_model.py').read_text())
        self.assertNotIn('pif(', (R5/'src/outcome_mapping.py').read_text())
    def test_33_synthetic_summary_keeps_status(self):
        rows=run(self.inc,*self.fixture,calibration_passed=True,synthetic=True)
        self.assertTrue(all(r['result_status']=='SYNTHETIC_TEST_ONLY' for r in aggregate(rows)))
    def test_34_actual_incidence_unchanged(self):
        outputs=read_csv(R5/'results/dynamic_results_age_sex_year.csv')
        self.assertEqual([float(r['incident_cases_averted']) for r in outputs],[float(r['incident_cases_averted']) for r in self.inc])
    def test_35_probability_is_not_hazard(self):self.assertLess(hazard_to_probability(.2),.2)
    def test_36_incompatibility_reported(self):
        for g in self.summary['groups']:
            for interval in g['structurally_incompatible_age_intervals']:self.assertGreater(interval['excess'],0)
        self.assertTrue(any(g['structurally_incompatible_age_intervals'] for g in self.summary['groups']))
    def test_37_real_calibration_repeatability(self):
        p1,d1,s1=calibrate(self.data)
        p2,d2,s2=calibrate(self.data)
        self.assertEqual((p1,d1,s1),(p2,d2,s2))
        self.assertEqual(s1,self.summary)
        self.assertEqual([r['calibrated_case_fatality_hazard'] for r in p1],[float(r['calibrated_case_fatality_hazard']) for r in self.parameters])

if __name__=='__main__':unittest.main()
