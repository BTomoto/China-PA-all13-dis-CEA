"""Derived reporting metrics and reproducibility checks; no new scientific inputs."""
from round8 import *
def run():
 for name in ['scenario_health_benefits','scenario_comparison']:
  d=read(HERE/'results'/f'{name}.csv')
  for col in ['baseline_total','benefit','attributable_B0','remaining_burden']:d[col]=pd.to_numeric(d[col],errors='coerce')
  d['benefit_percent_of_baseline']=100*d.benefit/d.baseline_total
  keys=['disease','measure']+(['year'] if name=='scenario_health_benefits' else ['end_year'])
  p15=d[d.scenario.eq('P15_GRADUAL')][keys+['benefit']].rename(columns={'benefit':'P15_reference_benefit'})
  d=d.merge(p15,on=keys,how='left',validate='many_to_one');d['difference_vs_P15']=d.benefit-d.P15_reference_benefit
  if name=='scenario_health_benefits':
   p=collapsed_population();p=p[p.variant.eq('Medium')];total=p.groupby('year').population.sum();female=p[p.sex.eq('Female')].groupby('year').population.sum()
   d['eligible_population']=[float((female if r.disease in ['breast_cancer','uterine_cancer'] else total).loc[r.year]) for r in d.itertuples()];d['benefit_rate_per100000']=d.benefit/d.eligible_population*100000
  save(d,'results/'+name+'.csv')
 # Every result table has the requested status fields, including descriptive comparisons.
 for p in (HERE/'results').glob('*.csv'):
  d=read(p)
  defaults={'result_status':'DESCRIPTIVE_INPUT_OR_TOTAL','evidence_tier':'SEE_DATABASE_SOURCE_MANIFEST','outcome_admission':'NOT_A_CAUSAL_ENDPOINT_RESULT','formal_point_estimate':False,'conditional_result':False,'structural_range':False,'limitation':'Descriptive source/total table; see field-specific methods and primary result tables'}
  for c,v in defaults.items():
   if c not in d:d[c]=v
  save(d,p.relative_to(HERE))
 pa=read(HERE/'database/pa_binary_exposure.csv');p=collapsed_population();rows=[]
 p=p[p.variant.eq('Medium')].merge(pa[['sex','age_group','p_inactive']],on=['sex','age_group'],validate='many_to_one')
 for r in p.itertuples():
  for sc,a in [('B0',0),('P15_GRADUAL',min(.15,max(0,.03*(r.year-2025)))),('P15_IMMEDIATE',.15),('R1',1)]:rows.append(dict(year=r.year,sex=r.sex,age_group=r.age_group,scenario=sc,population=r.population,p_inactive_B0=r.p_inactive,p_inactive_scenario=r.p_inactive*(1-a),inactive_persons_B0=r.population*r.p_inactive,inactive_persons_scenario=r.population*r.p_inactive*(1-a),result_status='MODEL_SCENARIO',evidence_tier='LEGACY_BINARY_MODEL',outcome_admission='EXPOSURE_INTERFACE',formal_point_estimate=True,conditional_result=False,structural_range=False,limitation='22 model strata; not observed2025; WPP Medium'))
 save(pd.DataFrame(rows),'results/scenario_exposure_age_sex.csv')
 txt('DATA_DICTIONARY.md','''# 数据字典

database CSV是模型入口；Excel为同值浏览，不提供独立计算逻辑。variable_id标识源记录；source_id与文件SHA定位来源；origin_path是仓库相对路径，source_file指原导出名称。val/lower/upper保留原字段，空值不等于0。GBD Rate单位为每10万人；Number按measure区分事件、死亡、现患人数和健康年。source_status与outcome_admission分离。

PAF_B0是模型二分类反事实归因分数。remaining_attributable_fraction_B0_denominator使用B0公共分母；不是通常以干预人口疾病率为分母的PAF。PIF是同年干预减少占B0总负担比例。baseline_total是未归因的疾病总量；attributable_B0、benefit和remaining_burden相互对应但不能跨单位相加。benefit_percent_of_baseline为百分数，benefit_rate_per100000以同年适用人口为分母。累计事件是年度反事实之和，可能涉及同一人在不同年份的事件。

FORMAL：当前指定二分类假设下正式发病点估计。CONDITIONAL_CRA_MAPPING：额外疾病亚型或fatal/disability映射假设，另列。BLOCKED_OUTCOME_MISMATCH：未通过风险接口，归因结果空白。NOT_APPLICABLE：结局不适用。疾病总负担的可用性不由风险接口是否通过决定。M1_BINARY、M2_LEGACY_PA、M3_FIXED_RATE、M4_WPP_REBASED详见METHODS_STATIC_CRA.md。

R1即时转类；P15_GRADUAL逐步15%；P15_IMMEDIATE立即15%。同一2030目标的时间路径不同；6/10/26年窗口分别截至2030/2034/2050。Low/High为已归档WPP变体，70+细结构保留Medium，是条件性敏感性。RR端点敏感性不是结果95%UI。不得把缺失UI视为0或合并lower/upper。
''')
if __name__=='__main__':run()
