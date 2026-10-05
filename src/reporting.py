from model_io import install as _configure_io
_configure_io()
from pathlib import Path
import json
import numpy as np
import pandas as pd

AGES=['20-24','25-29','30-34','35-39','40-44','45-49','50-54','55-59','60-64','65-69','70+']
DISEASES=['coronary_heart_disease','stroke','type2_diabetes','hypertension','depression','dementia','bladder_cancer','breast_cancer','colon_cancer','endometrial_cancer','oesophageal_cancer','gastric_cancer','renal_cancer']
LABELS=['缺血性心脏病','卒中','2型糖尿病','高血压','抑郁症','痴呆','膀胱癌','乳腺癌','结直肠癌','子宫内膜癌','食管癌','胃癌','肾癌']
LABEL=dict(zip(DISEASES,LABELS))

def save(root,name,frame):
    path=root/'outputs'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    frame.to_csv(path,index=False,encoding='utf-8-sig')
    return frame

def value_summary(a,prefix):
    return {prefix+'_mean':a.mean(),prefix+'_lower':a.quantile(.025),prefix+'_upper':a.quantile(.975)}

def ceac_grid(draws,ids,grid):
    rows=[]
    for h in [5,10]:
        g=draws[draws.horizon_years.eq(h)&draws.scenario_id.isin(ids)]
        effect=g.pivot(index='draw_id',columns='scenario_id',values='discounted_dalys_averted')
        cost=g.pivot(index='draw_id',columns='scenario_id',values='discounted_programme_cost_2025_cny').reindex(columns=effect.columns)
        for w in grid:
            nmb=effect*w-cost
            best=nmb.idxmax(axis=1)
            optimum=nmb.mean().idxmax()
            for s in effect.columns:
                rows.append({'horizon_years':h,'wtp':w,'scenario_id':s,'probability':(best==s).mean(),'expected_nmb':nmb[s].mean(),'ceaf_scenario':optimum,'ceaf_probability':(best==optimum).mean()})
    return pd.DataFrame(rows)

def build_tables(root):
    root=Path(root);out=root/'outputs';work=root/'work';econ=work/'economic'
    draws=pd.read_csv(work/'psa_rerun/merged/01_joint_PSA_draws_merged.csv.gz')
    summary=pd.read_csv(out/'PSA_summary.csv')
    strata=pd.read_csv(out/'disease_age_sex_health.csv')
    disease=pd.read_csv(out/'disease_DALY_YLL_YLD_deaths.csv')
    htn=pd.read_csv(work/'deterministic/data/hypertension_detail_primary.csv.gz')
    medical=pd.read_csv(econ/'03_medical_savings_detail.csv')
    med=medical[medical.scenario_id.eq('S6')&medical.cost_stream.eq('direct_medical')]
    det=pd.read_csv(work/'deterministic/results/05_primary_horizon_summary.csv')
    save(root,'tables/Main_Table1.csv',summary[summary.scenario_id.eq('S6')&summary.horizon_years.isin([5,10])])
    q=summary[summary.scenario_id.isin(['S1','S2','S3','S4','S5'])&summary.horizon_years.isin([5,10])]
    save(root,'tables/S19.csv',q)
    means=q.pivot(index=['horizon_years','scenario_id'],columns='metric',values='mean').reset_index()
    means['icer_ratio_of_means']=means.discounted_programme_cost_2025_cny/means.discounted_dalys_averted
    means['statistics']='PSA means; ICER is ratio of mean cost to mean DALY'
    save(root,'tables/Main_Table2.csv',means)
    f=pd.read_csv(out/'frontier.csv');save(root,'tables/S20.csv',f[f.perspective.eq('PROGRAMME_ONLY')&f.horizon_years.isin([5,10])])
    ceaf=pd.read_csv(out/'CEAF.csv');evpi=pd.read_csv(out/'EVPI.csv')
    m=ceaf.merge(evpi,on=['horizon_years','perspective','wtp_cny_per_daly'],suffixes=('','_evpi'))
    save(root,'tables/S21.csv',m[m.perspective.eq('PROGRAMME_ONLY')&m.horizon_years.isin([5,10])])
    ceac=pd.read_csv(out/'multi_strategy_CEAC.csv')
    save(root,'tables/S22.csv',ceac[ceac.perspective.eq('PROGRAMME_ONLY')&ceac.horizon_years.isin([5,10])])
    grid=ceac_grid(draws,[f'S{i}' for i in range(1,6)],range(0,200001,500))
    save(root,'figure_data/restricted_S1_S5_CEAC.csv',grid)
    save(root,'figure_data/reference_S0_S6_CEAC.csv',ceac_grid(draws,[f'S{i}' for i in range(7)],range(0,200001,500)))
    paired=[]
    for h in [5,10]:
        d=draws[draws.horizon_years.eq(h)]
        a=d[d.scenario_id.eq('S6')].set_index('draw_id');b=d[d.scenario_id.eq('S4')].set_index('draw_id')
        e=a.discounted_dalys_averted-b.discounted_dalys_averted;c=a.discounted_programme_cost_2025_cny-b.discounted_programme_cost_2025_cny
        row={'horizon_years':h,**value_summary(e,'delta_DALY'),**value_summary(c,'delta_cost'),'icer_ratio_of_means':c.mean()/e.mean(),'probability_more_effective':(e>0).mean()}
        for w in [50000,100000,150000]:row[f'probability_ce_{w}']=(e*w-c>0).mean()
        paired.append(row)
    save(root,'tables/S23.csv',pd.DataFrame(paired))
    mr=[]
    for h in [5,10,26]:
        g=med[med.year.le(2024+h)].groupby('outcome_id',as_index=False)[['discounted_savings_main_2025_cny','discounted_savings_low_2025_cny','discounted_savings_high_2025_cny']].sum()
        g['horizon_years']=h;g['share']=g.discounted_savings_main_2025_cny/g.discounted_savings_main_2025_cny.sum();mr.append(g)
    mt=pd.concat(mr,ignore_index=True);save(root,'tables/S24.csv',mt)
    wide=mt[mt.horizon_years.isin([5,10])].pivot(index='outcome_id',columns='horizon_years',values='discounted_savings_main_2025_cny')
    wide.columns=['medical_5y','medical_10y'];wide['ratio_10_to_5']=wide.medical_10y/wide.medical_5y.replace(0,np.nan)
    wide['ratio_from_displayed_values']=(wide.medical_10y/1e9).round(4)/(wide.medical_5y/1e9).round(4).replace(0,np.nan)
    for h in [5,10]:wide[f'rank_{h}y']=wide[f'medical_{h}y'].rank(ascending=False,method='min')
    save(root,'tables/S25.csv',wide.reset_index())
    ext=[]
    for h,n in [(5,26),(10,27),(26,28)]:
        g=disease[disease.horizon_years.eq(h)].pivot(index='outcome_id',columns='measure_short',values='discounted_value')
        g.loc['depression',['YLL','Deaths']]=0
        t=htn[htn.scenario_id.eq('S6')&htn.year.le(2024+h)]
        hd=(t.avoided_value/1.03**(t.year-2025)).sum()*.36
        g.loc['hypertension',['DALY','YLL','YLD','Deaths']]=[hd,0,hd,np.nan]
        original=g.drop(index='hypertension').sum()
        all_=g.sum();g['daly_share_extended']=g.DALY/all_.DALY;g['death_share_original']=g.Deaths/original.Deaths
        g.loc['subtotal_original_12',['DALY','YLL','YLD','Deaths']]=original
        g.loc['total_with_HTN_extension',['DALY','YLL','YLD','Deaths']]=all_
        g.loc['subtotal_original_12','daly_share_extended']=original.DALY/all_.DALY
        g.loc['subtotal_original_12','death_share_original']=1
        g.loc['total_with_HTN_extension',['daly_share_extended','death_share_original']]=1
        g=g.reset_index();g['horizon_years']=h;g['disease']=g.outcome_id.map(LABEL).fillna(g.outcome_id)
        save(root,f'tables/S{n}.csv',g);ext.append(g)
    extended=pd.concat(ext,ignore_index=True)
    save(root,'hypertension_extension.csv',extended[extended.outcome_id.eq('hypertension')])
    quantity=pd.read_csv(out/'disease_age_sex_quantity.csv')
    q=quantity[quantity.horizon_years.eq(10)].groupby(['outcome_id','basis'],as_index=False).avoided_value.sum()
    h=extended[extended.horizon_years.eq(10)&extended.outcome_id.isin(q.outcome_id)]
    s29=q.merge(h[['outcome_id','DALY','daly_share_extended']],on='outcome_id').merge(mt[mt.horizon_years.eq(10)],on='outcome_id')
    s29['daly_rank']=s29.DALY.rank(ascending=False,method='min');s29['medical_rank']=s29.discounted_savings_main_2025_cny.rank(ascending=False,method='min')
    save(root,'tables/S29.csv',s29)
    d=strata[strata.measure_short.eq('DALY')]
    for n,col in [(30,'age_group'),(31,'sex')]:
        q=d.groupby(['horizon_years',col],as_index=False).discounted_value.sum();q['share']=q.discounted_value/q.groupby('horizon_years').discounted_value.transform('sum');save(root,f'tables/S{n}.csv',q)
    q=strata[strata.horizon_years.eq(10)].groupby(['age_group','sex','measure_short'],as_index=False).discounted_value.sum()
    w=q.pivot(index='age_group',columns=['sex','measure_short'],values='discounted_value').reindex(AGES)
    w.columns=['_'.join(x) for x in w.columns]
    for m in ['DALY','Deaths']:w[m+'_male_female_ratio']=w['Male_'+m]/w['Female_'+m]
    save(root,'tables/S32.csv',w.reset_index()[['age_group','Male_DALY','Female_DALY','DALY_male_female_ratio','Male_Deaths','Female_Deaths','Deaths_male_female_ratio']])
    for sex in ['Male','Female']:w[sex+'_YLL_share']=w[sex+'_YLL']/w[sex+'_DALY']
    save(root,'tables/S33.csv',w.reset_index()[['age_group','Male_YLL','Male_YLD','Male_YLL_share','Female_YLL','Female_YLD','Female_YLL_share']])
    conc=[]
    for disease_id,g in d[d.horizon_years.eq(10)].groupby('outcome_id'):
        total=g.discounted_value.sum();top=g.loc[g.discounted_value.idxmax()]
        conc.append({'outcome_id':disease_id,'DALY':total,'male_share':g.loc[g.sex.eq('Male'),'discounted_value'].sum()/total,'age60plus_share':g.loc[g.age_group.isin(AGES[-3:]),'discounted_value'].sum()/total,'age70plus_share':g.loc[g.age_group.eq('70+'),'discounted_value'].sum()/total,'top_sex':top.sex,'top_age':top.age_group,'top_share':top.discounted_value/total})
    save(root,'tables/S34.csv',pd.DataFrame(conc))
    d=d.copy();d['age_band']=d.age_group.map({a:('20-39' if i<4 else '40-59' if i<8 else '60-69' if i<10 else '70+') for i,a in enumerate(AGES)})
    groups=d.groupby(['horizon_years','age_band','sex','outcome_id'],as_index=False).discounted_value.sum()
    tops=[]
    for (age,sex),g in groups[groups.horizon_years.eq(10)].groupby(['age_band','sex']):
        total=g.discounted_value.sum();g=g.sort_values('discounted_value',ascending=False).head(3)
        r={'age_band':age,'sex':sex,'DALY':total,'top3_share':g.discounted_value.sum()/total}
        for rank,row in enumerate(g.itertuples(),1):r.update({f'rank{rank}_outcome':row.outcome_id,f'rank{rank}_share':row.discounted_value/total})
        tops.append(r)
    save(root,'tables/S35.csv',pd.DataFrame(tops))
    q=groups.groupby(['horizon_years','age_band','sex'],as_index=False).discounted_value.sum();q['share']=q.discounted_value/q.groupby('horizon_years').discounted_value.transform('sum');save(root,'tables/S36.csv',q)
    probabilities=[];thresholds=[]
    for h in [5,10]:
        a=draws[draws.horizon_years.eq(h)&draws.scenario_id.eq('S6')]
        r={'horizon_years':h}
        for w in range(0,200001,500):
            p=(a.discounted_dalys_averted*w-a.discounted_programme_cost_2025_cny>0).mean()
            probabilities.append({'horizon_years':h,'wtp':w,'S6_probability':p,'S0_probability':1-p})
            for target in [.5,.75,.9]:
                key=f'wtp_probability_{target}'
                if key not in r and p>=target:r[key]=w
            if w in [50000,100000,150000]:r[f'probability_at_{w}']=p
        thresholds.append(r)
    save(root,'tables/S37.csv',pd.DataFrame(thresholds));save(root,'figure_data/S0_S6_CEAC.csv',pd.DataFrame(probabilities))
    unc=pd.read_csv(econ/'12_economic_satellite_uncertainty.csv');save(root,'tables/S38.csv',unc[unc.scenario_id.eq('S6')])
    roi=pd.read_csv(econ/'10_return_on_investment_annual.csv')
    roi['cumulative_public_payer_net_cost']=-roi.cum_discounted_public_net
    save(root,'tables/S39.csv',roi[roi.scenario_id.eq('S6')])
    save(root,'tables/S40.csv',pd.read_csv(out/'annual_cumulative_economic_trajectory.csv'))
    import merge_and_qc_psa_v1_2 as merge
    conv=merge.convergence(draws,True);save(root,'figure_data/convergence.csv',conv);save(root,'tables/S41.csv',conv[conv.checkpoint_draws.eq(10000)])
    roi_sum=pd.read_csv(econ/'11_return_on_investment_horizon.csv');med_sum=pd.read_csv(econ/'05_medical_savings_horizon.csv')
    save(root,'tables/Main_Table3_central.csv',roi_sum[roi_sum.scenario_id.eq('S6')])
    save(root,'tables/Main_Table3_uncertainty.csv',unc[unc.scenario_id.eq('S6')])
    save(root,'tables/Main_Table3_medical.csv',med_sum[med_sum.scenario_id.eq('S6')])
    gdp=pd.read_csv(econ/'08_gdp_equivalent_mechanism_annual.csv')
    combined=[]
    for h in [5,10,26]:
        z=med_sum[med_sum.scenario_id.eq('S6')&med_sum.horizon_years.eq(h)].iloc[0]
        combined.append({'horizon_years':h,'metric':'direct_medical_savings','estimate':z.direct_medical_savings_main_2025_cny,'lower':z.direct_medical_savings_low_2025_cny,'upper':z.direct_medical_savings_high_2025_cny,'statistic':'central_and_parameter_bounds','unit':'2025_CNY'})
        z=gdp[gdp.scenario_id.eq('S6')&gdp.year.le(2024+h)].groupby('variant').discounted_gdp_equivalent_gain_2025_cny.sum()
        combined.append({'horizon_years':h,'metric':'GDP_equivalent_gain','estimate':z['MAIN'],'lower':z['LOW'],'upper':z['HIGH'],'statistic':'central_and_parameter_bounds','unit':'2025_CNY'})
        for metric in ['public_payer_net_cost_2025_cny','societal_net_benefit_2025_cny','societal_benefit_cost_ratio']:
            z=unc[unc.scenario_id.eq('S6')&unc.horizon_years.eq(h)&unc.metric.eq(metric)].iloc[0]
            combined.append({'horizon_years':h,'metric':metric,'estimate':z['mean'],'lower':z.p2_5,'upper':z.p97_5,'statistic':'mean_and_95_UI','unit':'ratio' if metric.endswith('ratio') else '2025_CNY'})
    save(root,'tables/Main_Table3.csv',pd.DataFrame(combined))
    print('Computed result tables S19–S41 and main tables.')

def build_cost_and_parameters(root):
    root=Path(root);src=root/'input/cost_reconstruction'
    a=pd.read_csv(src/'coordination_activities.csv');a['recomputed_cost']=a['数量']*a['假设单位价格_2025CNY']
    a['difference']=a.recomputed_cost-a['年度成本_CNY'];save(root,'cost_reconstruction/activity_costs.csv',a)
    annual=pd.read_csv(src/'annual_reconstruction.csv')
    annual=annual.merge(a.groupby('年份',as_index=False).recomputed_cost.sum(),on='年份')
    annual['recomputed_S6']=annual['S1–S5合计_CNY']+annual.recomputed_cost-annual['共享资源排重平衡项_CNY']
    annual['difference_from_locked']=annual.recomputed_S6-annual['锁定S6_CNY']
    frozen=pd.read_csv(root/'work/deterministic/results/19_policy_cost_payer_2025_2050.csv')
    locked=frozen[frozen.scenario_id.eq('S6')].set_index('year').annual_programme_cost_2025_cny
    annual['frozen_unrounded_S6']=annual['年份'].map(locked)
    annual['discounted_S6']=annual.frozen_unrounded_S6/1.03**(annual['年份']-2025)
    save(root,'cost_reconstruction/annual_closure.csv',annual)
    save(root,'cost_reconstruction/discounted_totals.csv',pd.DataFrame([{'horizon_years':h,'discounted_S6':annual.loc[annual['年份'].le(2024+h),'discounted_S6'].sum()} for h in [5,10]]))
    for p in sorted((root/'reference/parameter_tables').glob('*.csv')):
        save(root,'parameter_tables/'+p.name,pd.read_csv(p))
    from aggregate_inputs import read_parent
    import run_d1_d10_stage as det
    inputs=det.load_inputs();pop=det.build_population(inputs)
    save(root,'parameter_tables/S02_computed_population.csv',pop[pop.year.eq(2025)])
    save(root,'parameter_tables/S03_formal_model_baseline.csv',inputs['pa'])
    save(root,'parameter_tables/S06_RR.csv',det.build_rr_interface(inputs,'COMMON_STROKE_PIF'))
    save(root,'parameter_tables/S10_lags.csv',inputs['lag'])
    for filename in ['policy_effect_parameters_v1.2.csv','programme_cost_parameters_v1.2.csv','PSA_parameter_registry_v1.2.csv','pa_beta_parameters_binary_v2.0.csv']:
        save(root,'parameter_tables/'+filename,pd.read_csv(root/'work/psa_input'/filename))
    save(root,'parameter_tables/S16_medical_inputs.csv',pd.read_csv(root/'input/prepublication_extensions/medical_cost_parameters_2025cny.csv'))
    save(root,'parameter_tables/S17_economic_inputs.csv',pd.read_csv(root/'input/prepublication_extensions/macro_and_payer_parameters.csv'))
    trajectories=pd.read_csv(root/'work/deterministic/data/PA_trajectory_primary.csv.gz')
    b=trajectories[trajectories.scenario_id.eq('S0')].merge(pop[['year','sex','age_group','population_model']],on=['year','sex','age_group'],validate='one_to_one')
    annual=[]
    for year,g in b.groupby('year'):
        for sex,z in list(g.groupby('sex'))+[('Both',g)]:
            annual.append({'year':year,'sex':sex,'inactive_proportion':np.average(z.inactive_policy,weights=z.population_model),'population':z.population_model.sum()})
    save(root,'parameter_tables/S05_formal_model_annual_baseline.csv',pd.DataFrame(annual))
    print('Exported parameter records and recorded cost reconstruction.')
