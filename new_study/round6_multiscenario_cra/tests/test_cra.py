import ast,copy,json,math,subprocess,unittest
from src.common import R6,ROOT,AGES,VARIANTS,InputBlocked,config,read_csv,verify_old_inputs
from src.sources import population_exposure,gbd_rates,extract_continuous_rr,category_rr
from src.exposure import transformed_distribution,inactive_share,completion,known_inactive_share,validate_atoms
from src.risk import categorical_pif,continuous_pif,category_identification_bounds,published_grid_risk,map_incidence,map_other_outcome,validate_domain
from src.analysis import exposure_rows,risk_and_incidence,legacy_regression,legacy_summaries,comparison_summary
from src.evidence import endpoint_admission

class CRATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b=population_exposure();cls.rates,_=gbd_rates();cls.grid=extract_continuous_rr();cls.cats=category_rr()
        cls.pifs,cls.events=risk_and_incidence(cls.b,cls.rates,cls.cats)
        cls.toy=[(0.,.1),(300.,.2),(550.,.1),(600.,.1),(2400.,.2),(10000.,.3)]
        cls.risk=staticmethod(lambda x:1/(1+x/1000))

    def test_01_baseline_pif_zero(self):self.assertEqual(continuous_pif(self.toy,self.toy,self.risk),0)
    def test_02_category_identity(self):self.assertEqual(categorical_pif([.2,.3,.3,.2],[.2,.3,.3,.2],[1,.84,.77,.75]),0)
    def test_03_weight_conservation(self):
        for scenario,path in VARIANTS:
            for year in [2025,2027,2030,2050]:self.assertAlmostEqual(sum(w for _,w in transformed_distribution(self.toy,scenario,year,path)),1)
    def test_04_p15_target(self):
        b=inactive_share(self.toy);self.assertAlmostEqual(inactive_share(transformed_distribution(self.toy,'P15',2030,'gradual_2030')),.85*b)
    def test_05_r1_threshold(self):self.assertTrue(all(x>=600 for x,w in transformed_distribution(self.toy,'R1',2025,'immediate_2025') if w>0))
    def test_06_r2_zero(self):self.assertAlmostEqual(sum(w for x,w in transformed_distribution(self.toy,'R2',2030,'immediate_2025') if x==0),.1)
    def test_07_r2_applies_to_inactive(self):self.assertIn((360.,.2),transformed_distribution(self.toy,'R2',2030,'immediate_2025'))
    def test_08_r3_original_branch(self):
        self.assertEqual(inactive_share(transformed_distribution([(550.,1.)],'R3',2030,'immediate_2025')),0)
        self.assertEqual(sum(x*w for x,w in transformed_distribution([(550.,1.)],'R3',2030,'immediate_2025')),600)
    def test_09_r3_threshold_branch(self):self.assertEqual(sum(x*w for x,w in transformed_distribution([(600.,1.)],'R3',2030,'immediate_2025')),720)
    def test_10_identical_distribution_same_result(self):
        self.assertEqual(continuous_pif(self.toy,copy.deepcopy(self.toy),self.risk),0)
    def test_11_r3_dominates_r1(self):
        r3=continuous_pif(self.toy,transformed_distribution(self.toy,'R3',2030,'immediate_2025'),self.risk)
        r1=continuous_pif(self.toy,transformed_distribution(self.toy,'R1',2030,'immediate_2025'),self.risk)
        self.assertGreaterEqual(r3,r1)
    def test_12_r3_r2_counterexample(self):
        atoms=[(550.,1.)];r2=continuous_pif(atoms,transformed_distribution(atoms,'R2',2030,'immediate_2025'),self.risk);r3=continuous_pif(atoms,transformed_distribution(atoms,'R3',2030,'immediate_2025'),self.risk)
        self.assertGreater(r2,r3)
    def test_13_r3_dominates_r2_when_inactive_le500(self):
        atoms=[(0.,.2),(400.,.3),(600.,.1),(3000.,.4)]
        r2=continuous_pif(atoms,transformed_distribution(atoms,'R2',2030,'immediate_2025'),self.risk);r3=continuous_pif(atoms,transformed_distribution(atoms,'R3',2030,'immediate_2025'),self.risk)
        self.assertGreaterEqual(r3,r2)
    def test_14_bad_weights_close(self):
        with self.assertRaises(ValueError):validate_atoms([(0,.5)])
    def test_15_missing_distribution_close(self):
        with self.assertRaises(InputBlocked):transformed_distribution(None,'R2',2030,'immediate_2025')
    def test_16_unadmitted_incidence_close(self):
        with self.assertRaises(InputBlocked):map_incidence(100,.02,'BLOCKED_ENDPOINT_ALIGNMENT')
    def test_17_other_endpoint_close(self):
        with self.assertRaises(InputBlocked):map_other_outcome(100,.02)
    def test_18_source_locks(self):self.assertEqual(len(verify_old_inputs()),11)
    def test_19_population_total(self):self.assertEqual(sum(r['population'] for r in self.b if r['year']==2025),1113252964)
    def test_20_2025_weighted_baseline(self):
        rows=[r for r in self.b if r['year']==2025];p=sum(r['population']*r['p_inactive'] for r in rows)/sum(r['population'] for r in rows)
        self.assertAlmostEqual(p,.219660515,places=9)
    def test_21_shared_coarse_source(self):
        rows={(r['sex'],r['age']):r for r in self.b if r['year']==2025}
        for s in ['Male','Female']:
            self.assertEqual(rows[(s,'20-24')]['p_inactive'],rows[(s,'25-29')]['p_inactive']);self.assertEqual(rows[(s,'20-24')]['shared_parameter_id'],rows[(s,'25-29')]['shared_parameter_id'])
    def test_22_two_sexes_only(self):self.assertEqual({r['sex'] for r in self.b},{'Male','Female'})
    def test_23_95_alignment(self):self.assertEqual({r['age'] for r in self.b},set(AGES));self.assertEqual(len(self.rates),64)
    def test_24_all_p15_age_sex_target(self):self.assertTrue(all(math.isclose(known_inactive_share(r['p_inactive'],'P15',2030,'gradual_2030'),.85*r['p_inactive'],abs_tol=1e-12) for r in self.b))
    def test_25_post2030_fixed(self):self.assertEqual(known_inactive_share(.3,'P15',2030,'gradual_2030'),known_inactive_share(.3,'P15',2050,'gradual_2030'))
    def test_26_r2_not_filled_zero(self):self.assertIsNone(known_inactive_share(.2,'R2',2030,'immediate_2025'))
    def test_27_common_start_is_baseline(self):self.assertEqual(inactive_share(transformed_distribution(self.toy,'R3',2025,'common_2030')),inactive_share(self.toy))
    def test_28_common_end_equals_immediate(self):
        for s in ['R1','R2','R3']:self.assertEqual(transformed_distribution(self.toy,s,2030,'common_2030'),transformed_distribution(self.toy,s,2030,'immediate_2025'))
    def test_29_mixture_not_rr_interpolation(self):
        self.assertEqual(completion(2027,'common_2030'),.4)
        target=transformed_distribution(self.toy,'R2',2030,'immediate_2025');mixed=transformed_distribution(self.toy,'R2',2027,'common_2030')
        expected=.6*sum(w*self.risk(x) for x,w in self.toy)+.4*sum(w*self.risk(x) for x,w in target)
        self.assertAlmostEqual(sum(w*self.risk(x) for x,w in mixed),expected)
    def test_30_exact_knots_not_category_rr(self):
        ihd=[r for r in self.grid if r['disease']=='IHD'];self.assertEqual(published_grid_risk(600,ihd),.909);self.assertNotEqual(published_grid_risk(600,ihd),self.cats['IHD'][1])
    def test_31_published_grid_dimensions(self):self.assertEqual(len(self.grid),104);self.assertEqual({r['dose'] for r in self.grid},set(range(0,30601,600)))
    def test_32_no_tail_extrapolation(self):
        with self.assertRaises(InputBlocked):published_grid_risk(33000,[r for r in self.grid if r['disease']=='IS'])
    def test_33_no_automatic_interpolation(self):
        with self.assertRaises(InputBlocked):published_grid_risk(300,[r for r in self.grid if r['disease']=='IS'])
    def test_34_wrong_domain_close(self):
        for args in [('MET-min/week','leisure','gross'),('MET-min/week','total','marginal')]:
            with self.assertRaises(InputBlocked):validate_domain(*args)
    def test_35_identification_envelope_contains_all_active_allocations(self):
        p=.25;alpha=.15;rr=self.cats['IHD'];lo,hi=category_identification_bounds(p,alpha,rr)
        for active in [[.75,0,0],[0,.75,0],[0,0,.75],[.2,.25,.3]]:
            p0=[p]+active;p1=[p*(1-alpha),active[0]+p*alpha,active[1],active[2]];value=categorical_pif(p0,p1,rr)
            self.assertGreaterEqual(value+1e-12,lo);self.assertLessEqual(value-1e-12,hi)
    def test_36_envelope_identity(self):self.assertEqual(category_identification_bounds(.2,0,self.cats['IS']),(0,0))
    def test_37_old_p15_reproduced(self):
        rows=legacy_regression(self.b,self.rates);self.assertEqual(len(rows),1664);self.assertLess(max(r['absolute_difference'] for r in rows),1e-7);self.assertEqual(len(legacy_summaries(rows)),6)
    def test_38_no_new_unadmitted_events(self):self.assertTrue(all(r['avoided_incident_units']=='' for r in self.events if r['scenario']!='B0'))
    def test_39_same_baseline_all_scenarios(self):
        bykey={}
        for r in self.events:
            key=(r['year'],r['sex'],r['age'],r['disease']);v=r['baseline_expected_incident_units']
            if key in bykey:self.assertEqual(bykey[key],v)
            bykey[key]=v
    def test_40_inclusive_six_year_window(self):self.assertTrue(all(r['calendar_years']==6 for r in comparison_summary(self.events) if r['period']=='2025-2030'))
    def test_41_previous_rounds_unchanged(self):
        files=subprocess.check_output(['git','diff','--name-only',config()['baseline_commit'],'--','new_study'],cwd=ROOT,text=True).splitlines()
        self.assertTrue(all(p.startswith('new_study/round6_multiscenario_cra/') for p in files))
    def test_42_no_natural_history_or_economic_imports(self):
        forbidden={'dynamic_model','dynamic_cohort_model','transition_calibration','health_pilot','dynamic_outcomes','build_round5','build_round4'}
        for p in list((R6/'src').glob('*.py'))+[R6/'build_round6.py']:
            for node in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
                if isinstance(node,ast.ImportFrom):self.assertFalse(set((node.module or '').split('.'))&forbidden)
                if isinstance(node,ast.Import):self.assertTrue(all(not set(a.name.split('.'))&forbidden for a in node.names))
    def test_43_registry_unique(self):
        rows=read_csv(R6/'inputs/parameter_register.csv');ids=[r['parameter_id'] for r in rows];self.assertEqual(len(ids),len(set(ids)))
    def test_44_endpoint_matrix_complete(self):self.assertEqual(len(endpoint_admission()),14);self.assertEqual(len(read_csv(R6/'results/outcome_admission_matrix.csv')),70)
    def test_45_repeat_numeric_results(self):self.assertEqual(risk_and_incidence(self.b,self.rates,self.cats),(self.pifs,self.events))
    def test_46_no_hemorrhagic_RR(self):self.assertEqual({r['disease'] for r in self.pifs},{'IHD','IS'})
    def test_47_preserve_pointwise_UI_crossing_one(self):
        row=next(r for r in self.grid if r['disease']=='IS' and r['dose']==1200);self.assertEqual(row['upper'],1.001)
    def test_48_no_negative_or_nonfinite_weights(self):
        for atoms in [[(1.,float('nan'))],[(-1.,1.)],[(1.,-1.),(2.,2.)]]:
            with self.assertRaises(ValueError):validate_atoms(atoms)
    def test_49_unknown_scenario_fails(self):
        with self.assertRaises(ValueError):transformed_distribution(self.toy,'BAD',2030,'immediate_2025')
    def test_50_no_point_PIF_for_unknown_active_distribution(self):self.assertTrue(all(r['pif']=='' for r in self.pifs if r['scenario']!='B0'))
    def test_51_fixed_2025_target_weighting(self):
        cells=[r for r in self.b if r['year']==2025];n=sum(r['population'] for r in cells)
        p=sum(r['population']*known_inactive_share(r['p_inactive'],'P15',2030,'gradual_2030') for r in cells)/n
        self.assertAlmostEqual(p,.186711438,places=9)
    def test_52_b0_aggregation_equals_details(self):
        summary=comparison_summary(self.events)
        for disease in ['IHD','IS']:
            total=next(r['baseline_expected_incident_units'] for r in summary if r['scenario']=='B0' and r['disease']==disease and r['period']=='2030' and r['period_type']=='annual')
            detail=sum(r['baseline_expected_incident_units'] for r in self.events if r['scenario']=='B0' and r['disease']==disease and r['year']==2030)
            self.assertEqual(total,detail)
    def test_53_paired_P15_risk_comparison(self):
        for r in self.pifs:
            if r['scenario']=='P15':self.assertEqual((r['categorical_difference_vs_P15_lower'],r['categorical_difference_vs_P15_upper']),(0,0))
            if r['scenario']=='R1' and r['year']==2030:
                self.assertAlmostEqual(r['categorical_difference_vs_P15_lower'],.85*r['categorical_pif_bound_lower'])
                self.assertAlmostEqual(r['categorical_difference_vs_P15_upper'],.85*r['categorical_pif_bound_upper'])

if __name__=='__main__':unittest.main()
