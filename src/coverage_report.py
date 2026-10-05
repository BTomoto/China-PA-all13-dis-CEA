from model_io import read_text
from model_io import install as _configure_io
_configure_io()
from pathlib import Path
import json, re
import numpy as np
import pandas as pd
from reporting import DISEASES, LABELS, AGES, save

def build_report(root):
    root=Path(root);out=root/'outputs';ref=json.loads(read_text(root/'reference/current_paper_tables.json'));checks=[]
    def read(name):return pd.read_csv(out/name)
    def rows(key):return ref[key]['rows'][1:]
    def disease(label):
        return dict(zip(LABELS,DISEASES)).get(label,{'全部13类结局':'total','小计（原12类疾病）':'subtotal_original_12','合计（含高血压扩展）':'total_with_HTN_extension'}.get(label))
    def one(d,**kwargs):
        for c,v in kwargs.items():d=d[d[c].eq(v)]
        if len(d)!=1:raise ValueError((kwargs,len(d)))
        return d.iloc[0]
    def compare(key,row_i,col_i,values,note=''):
        s=ref[key]['rows'][row_i][col_i]
        numeric_text=s
        if key=='supp_S35' and col_i in [2,3,4]:numeric_text=re.search(r'（(.*?)）',s).group(1)
        tokens=re.findall(r'(?<![\d.])-?\d+(?:\.\d+)?',numeric_text.replace(',','').replace('–',' ').replace('—',' '))
        actual=np.atleast_1d(values).astype(float).tolist()
        if not tokens:
            status='未估计（与原表一致）' if all(pd.isna(v) for v in actual) else '展示占位'
            tol=[]
        elif len(tokens)!=len(actual):status='需人工核对';tol=[]
        else:
            tol=[.5*10**(-len(x.split('.')[1])) if '.' in x else .5 for x in tokens]
            status='一致' if all(np.isfinite(a) and abs(a-float(t))<=v+1e-8 for a,t,v in zip(actual,tokens,tol)) else '差异'
        checks.append({'table':key,'row':ref[key]['rows'][row_i][0],'column':ref[key]['rows'][0][col_i],'reported':s,'reproduced':json.dumps(actual,ensure_ascii=False),'tolerance':json.dumps(tol),'status':status,'note':note})
    ps=read('PSA_summary.csv')
    metrics=['discounted_dalys_averted','discounted_deaths_averted','undiscounted_incidence_averted','discounted_programme_cost_2025_cny'];scales=[1e6,1e3,1e6,1e9]
    for key in ['main_1','supp_S19']:
        for i,r in enumerate(rows(key),1):
            h=int(re.search(r'\d+',r[0]).group());sid='S6' if key=='main_1' else r[1].split()[0];start=1 if key=='main_1' else 2
            for c,m,scale in zip(range(start,start+4),metrics,scales):
                z=one(ps,horizon_years=h,scenario_id=sid,metric=m);compare(key,i,c,[z['mean']/scale,z.p2_5/scale,z.p97_5/scale])
    m2=read('tables/Main_Table2.csv')
    for i,r in enumerate(rows('main_2'),1):
        for h,c in [(5,1),(10,4)]:
            z=one(m2,horizon_years=h,scenario_id=r[0].split()[0])
            for offset,value in enumerate([z.discounted_dalys_averted/1e6,z.discounted_programme_cost_2025_cny/1e9,z.icer_ratio_of_means]):compare('main_2',i,c+offset,value,'表题称确定性；对应正式PSA均值及均值之比')
    uncertainty=read('tables/Main_Table3_uncertainty.csv');medical=read('tables/Main_Table3_medical.csv')
    gdp=pd.read_csv(root/'work/economic/08_gdp_equivalent_mechanism_annual.csv')
    for c,h in [(1,5),(2,10),(3,26)]:
        z=one(medical,horizon_years=h);compare('main_3',1,c,[z[f'direct_medical_savings_{v}_2025_cny']/1e9 for v in ['main','low','high']])
        g=gdp[gdp.scenario_id.eq('S6')&gdp.year.le(2024+h)].groupby('variant').discounted_gdp_equivalent_gain_2025_cny.sum()
        compare('main_3',2,c,[g[v]/1e9 for v in ['MAIN','LOW','HIGH']])
        for i,m in [(3,'public_payer_net_cost_2025_cny'),(4,'societal_net_benefit_2025_cny'),(5,'societal_benefit_cost_ratio')]:
            z=one(uncertainty,horizon_years=h,metric=m);scale=1 if i==5 else 1e9;compare('main_3',i,c,[z['mean']/scale,z.p2_5/scale,z.p97_5/scale])
    # Source tables are input records, not model outputs.
    pop=pd.read_csv(root/'work/deterministic/results/01_population_2025_2050.csv');pop=pop[pop.year.eq(2025)]
    for i,r in enumerate(rows('supp_S2'),1):
        try:
            sex={'女性':'Female','男性':'Male'}[r[0]];age=r[1].replace('–','-').replace('≥70','70+');z=one(pop,sex=sex,age_group=age)
            compare('supp_S2',i,2,z.population_model/1e6)
        except (KeyError,IndexError):pass
    baseline=pd.read_csv(out/'model_baseline_age_sex.csv')
    for i,r in enumerate(rows('supp_S3'),1):
        sex={'女性':'Female','男性':'Male'}[r[0]];age=r[1].replace('–','-').replace('≥70','70+');z=one(baseline,sex=sex,age_group=age)
        compare('supp_S3',i,3,z.p_inactive*100,'冻结正式模型输入');compare('supp_S3',i,4,z.p_active*100,'冻结正式模型输入')
    base=read('paper_baseline_discrepancy.csv')
    for i,r in enumerate(rows('supp_S4'),1):
        z=one(base,sex={'女性':'Female','男性':'Male','总体':'Both'}[r[0]])
        compare('supp_S4',i,1,z.population/1e8);compare('supp_S4',i,2,z.model_inactive_percent,'稿件描述基线与正式模型基线不一致');compare('supp_S4',i,3,z.population*z.model_inactive_percent/100/1e8)
    cost=read('cost_reconstruction/annual_closure.csv');tot=read('cost_reconstruction/discounted_totals.csv')
    for i,r in enumerate(rows('supp_S14'),1):
        if i<=10:
            z=one(cost,年份=int(r[0]))
            values=[z['S1–S5合计_CNY'],z.recomputed_cost,z['共享资源排重平衡项_CNY'],z['净整合调整_CNY'],z.recomputed_S6]
            for c,v in enumerate(values,1):compare('supp_S14',i,c,v/1e8)
        else:compare('supp_S14',i,5,one(tot,horizon_years=5 if i==11 else 10).discounted_S6/1e8)
    frontier=read('tables/S20.csv')
    for i,r in enumerate(rows('supp_S20'),1):
        z=one(frontier,horizon_years=int(r[0].replace('年','')),scenario_id=r[1].split()[0])
        for c,col,scale in [(2,'mean_discounted_dalys',1e6),(3,'mean_cost_2025_cny',1e9),(5,'incremental_discounted_dalys',1e6),(6,'incremental_cost_2025_cny',1e9),(7,'incremental_icer_cny_per_daly',1)]:compare('supp_S20',i,c,z[col]/scale)
    ceaf=read('tables/S21.csv')
    for i,r in enumerate(rows('supp_S21'),1):
        z=one(ceaf,horizon_years=int(r[0].replace('年','')),wtp_cny_per_daly=int(r[1].replace(',','')))
        for c,v in [(3,z.ceaf_probability*100),(4,z.maximum_expected_nmb_2025_cny/1e9),(5,z.evpi_2025_cny/1e9)]:compare('supp_S21',i,c,v)
    ceac=read('tables/S22.csv')
    for i,r in enumerate(rows('supp_S22'),1):
        h=int(r[0].replace('年',''));sid=re.search(r'S\d',r[1]).group()
        for c,w in [(2,50000),(3,100000),(4,150000)]:compare('supp_S22',i,c,one(ceac,horizon_years=h,scenario_id=sid,wtp_cny_per_daly=w).probability_cost_effective*100)
    paired=read('tables/S23.csv')
    for i,r in enumerate(rows('supp_S23'),1):
        z=one(paired,horizon_years=int(r[0].replace('年','')))
        for c,p,scale in [(1,'delta_DALY',1e6),(2,'delta_cost',1e9)]:compare('supp_S23',i,c,[z[p+s]/scale for s in ['_mean','_lower','_upper']])
        compare('supp_S23',i,3,z.icer_ratio_of_means);compare('supp_S23',i,4,z.probability_more_effective*100)
        for c,w in [(5,50000),(6,100000),(7,150000)]:compare('supp_S23',i,c,z[f'probability_ce_{w}']*100)
    mt=read('tables/S24.csv')
    for i,r in enumerate(rows('supp_S24'),1):
        for h,c in [(5,1),(10,3)]:
            g=mt[mt.horizon_years.eq(h)]
            if disease(r[0])=='total':z=g.sum(numeric_only=True)
            else:z=one(g,outcome_id=disease(r[0]))
            compare('supp_S24',i,c,[z[f'discounted_savings_{v}_2025_cny']/1e9 for v in ['main','low','high']]);compare('supp_S24',i,c+1,z.share*100)
    s25=read('tables/S25.csv')
    for i,r in enumerate(rows('supp_S25'),1):
        z=one(s25,outcome_id=disease(r[0]))
        for c,value in [(1,z.medical_5y/1e9),(2,z.medical_10y/1e9),(3,z.ratio_from_displayed_values),(4,z.rank_5y),(5,z.rank_10y)]:compare('supp_S25',i,c,value,'比值按表内4位小数显示值复现；另提供未舍入比值' if c==3 else '')
    for n in [26,27,28]:
        d=read(f'tables/S{n}.csv')
        for i,r in enumerate(rows(f'supp_S{n}'),1):
            z=one(d,outcome_id=disease(r[0]))
            for c,col,scale in [(1,'DALY',1e4),(2,'YLL',1e4),(3,'YLD',1e4),(4,'Deaths',1),(5,'daly_share_extended',.01),(6,'death_share_original',.01)]:compare(f'supp_S{n}',i,c,z[col]/scale)
    s29=read('tables/S29.csv')
    for i,r in enumerate(rows('supp_S29'),1):
        z=one(s29,outcome_id=disease(r[0]));compare('supp_S29',i,2,z.avoided_value/1e4);compare('supp_S29',i,3,z.DALY/1e4)
        compare('supp_S29',i,4,[z.daly_rank,z.daly_share_extended*100]);compare('supp_S29',i,5,z.discounted_savings_main_2025_cny/1e8);compare('supp_S29',i,6,[z.medical_rank,z.share*100])
    for n,col in [(30,'age_group'),(31,'sex')]:
        d=read(f'tables/S{n}.csv')
        for i,r in enumerate(rows(f'supp_S{n}'),1):
            v=r[0].replace('–','-') if n==30 else {'女性':'Female','男性':'Male'}[r[0]]
            for h,c in [(5,1),(10,3),(26,5)]:
                z=one(d,horizon_years=h,**{col:v});compare(f'supp_S{n}',i,c,z.discounted_value/1e4);compare(f'supp_S{n}',i,c+1,z.share*100)
    for n in [32,33]:
        d=read(f'tables/S{n}.csv')
        cols=['Male_DALY','Female_DALY','DALY_male_female_ratio','Male_Deaths','Female_Deaths','Deaths_male_female_ratio'] if n==32 else ['Male_YLL','Male_YLD','Male_YLL_share','Female_YLL','Female_YLD','Female_YLL_share']
        scales=[1e4,1e4,1,1,1,1] if n==32 else [1e4,1e4,.01,1e4,1e4,.01]
        for i,r in enumerate(rows(f'supp_S{n}'),1):
            z=one(d,age_group=r[0].replace('–','-').replace('70岁及以上','70+'))
            for c,(col,scale) in enumerate(zip(cols,scales),1):compare(f'supp_S{n}',i,c,z[col]/scale)
    d=read('tables/S34.csv')
    for i,r in enumerate(rows('supp_S34'),1):
        z=one(d,outcome_id=disease(r[0]))
        for c,col,scale in [(1,'DALY',1e4),(2,'male_share',.01),(3,'age60plus_share',.01),(4,'age70plus_share',.01),(6,'top_share',.01)]:compare('supp_S34',i,c,z[col]/scale)
    d=read('tables/S35.csv');d36=read('tables/S36.csv')
    for key in ['supp_S35','supp_S36']:
        for i,r in enumerate(rows(key),1):
            sex='Male' if '男性' in r[0] else 'Female'
            age='20-39' if '20' in r[0] else '40-59' if '40' in r[0] else '60-69' if '60' in r[0] else '70+'
            if key.endswith('35'):
                z=one(d,sex=sex,age_band=age);compare(key,i,1,z.DALY/1e4)
                for rank in range(1,4):compare(key,i,rank+1,z[f'rank{rank}_share']*100)
                compare(key,i,5,z.top3_share*100)
            else:
                for c,h in [(1,5),(2,10),(3,26)]:compare(key,i,c,one(d36,sex=sex,age_band=age,horizon_years=h).share*100)
    d=read('tables/S37.csv')
    for i,r in enumerate(rows('supp_S37'),1):
        z=one(d,horizon_years=int(r[0].replace('年','')))
        for c,p in [(1,.5),(2,.75),(3,.9)]:compare('supp_S37',i,c,z[f'wtp_probability_{p}'])
        for c,w in [(4,50000),(5,100000),(6,150000)]:compare('supp_S37',i,c,z[f'probability_at_{w}']*100)
    d=read('tables/S38.csv')
    for i,h in enumerate([5,10,26],1):compare('supp_S38',i,1,one(d,horizon_years=h,metric='public_payer_net_cost_2025_cny').probability_favourable*100)
    d=read('tables/S39.csv')
    for i,r in enumerate(rows('supp_S39'),1):compare('supp_S39',i,1,one(d,year=int(r[0])).cumulative_public_payer_net_cost/1e8)
    d=read('tables/S40.csv')
    for i,r in enumerate(rows('supp_S40'),1):
        z=one(d,year=int(r[0]))
        for c,col in enumerate(['annual_medical_bn','cumulative_medical_bn','annual_gdp_equivalent_bn','cumulative_gdp_equivalent_bn'],1):compare('supp_S40',i,c,z[col])
    d=read('tables/S41.csv')
    for i,m in enumerate(['discounted_dalys_averted','discounted_programme_cost_2025_cny','discounted_partial_public_payer_net_cost_2025_cny'],1):
        z=one(d,metric=m);compare('supp_S41',i,1,z.cumulative_mean);compare('supp_S41',i,2,z.standard_error);compare('supp_S41',i,3,z.relative_standard_error*100)
    checks=pd.DataFrame(checks);save(root,'verification/paper_numeric_checks.csv',checks)
    save(root,'verification/paper_differences.csv',checks[checks.status.isin(['差异','需人工核对'])])
    cover=[]
    for key,t in ref.items():
        n=int(key.split('_')[-1].replace('S',''));computed=key.startswith('main') or n>=19 or n in [2,14]
        status='已计算并核对' if computed else '已提供冻结参数／方法记录'
        detail=''
        if key in ['supp_S3','supp_S4','supp_S5']:
            status='作者决定暂缓处理基线对应';detail='依作者决定保留正式模型原有输入；稿件基线对应暂缓处理。'
        if key=='main_2':detail='数值对应PSA均值及均值之比，表题“确定性”需作者统一。'
        failed=checks[checks.table.eq(key)&checks.status.isin(['差异','需人工核对'])]
        if len(failed) and status=='已计算并核对':status='已计算，存在展示值差异'
        paths=sorted(str(p.relative_to(root)) for p in (out/'tables').glob(('Main_Table'+str(n)+'*') if key.startswith('main') else f'S{n}.csv'))
        if not paths:paths=[f'outputs/parameter_tables/S{n:02d}_as_reported.csv']
        cover.append({'location':key,'title':t['title'],'notebook':'06 / 07 / 09','outputs':';'.join(paths),'status':status,'checked_cells':int(checks.table.eq(key).sum()),'different_cells':len(failed),'note':detail})
    for name in ['Main_Figure1','Main_Figure2','Main_Figure3','Main_Figure4']+[f'Supp_FigureS{i}' for i in range(1,7)]:
        status='已由计算结果重绘'
        if name=='Main_Figure1':status='基线图已导出；保持原有输入'
        if name=='Supp_FigureS1':status='模型示意原图保留；非数值分析'
        cover.append({'location':name,'title':name,'notebook':'08','outputs':'outputs/figures/'+name+'*','status':status,'checked_cells':0,'different_cells':0,'note':'统计内容与作图数据可追溯；不保证与Word图片像素一致。'})
    save(root,'result_coverage.csv',pd.DataFrame(cover))
    grouped=checks.groupby(['table','status']).size().unstack(fill_value=0)
    save(root,'verification/check_counts.csv',grouped.reset_index())
    print('Numeric checks:',len(checks),'differences:',len(checks[checks.status.eq('差异')]))
