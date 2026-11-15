from round8 import *
import time
def plots():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams.update({'font.family':'Arial','font.size':9,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
 out=HERE/'figures';out.mkdir(exist_ok=True)
 txt('reports/FIGURE_CONTRACT.md','Python/matplotlib; quantitative figures 2-7 use only FORMAL incidence results (IHD, IS, female breast). Figure1 schematic. 180mm wide, editable SVG/PDF and PNG preview. Deterministic point estimates, no error bars or simulated data. Source CSV and figure data accompany each image. Conditional DALYs are not mixed into formal figures.\n')
 main=read(HERE/'results/scenario_health_benefits.csv');cum=read(HERE/'results/scenario_comparison.csv');det=read(HERE/'results/disease_age_sex_decomposition.csv')
 main=main[main.outcome_admission.eq('FORMAL')&main.measure.eq('Incidence')];cum=cum[cum.outcome_admission.eq('FORMAL')&cum.measure.eq('Incidence')];det=det[det.outcome_admission.eq('FORMAL')&det.measure.eq('Incidence')]
 for frame in [main,cum,det]:
  for col in ['baseline_total','attributable_B0','benefit','remaining_burden']:frame[col]=pd.to_numeric(frame[col])
 def export(fig,name,data):
  fig.tight_layout();[fig.savefig(out/(name+'.'+ext),dpi=180,bbox_inches='tight') for ext in ['png','svg','pdf']];plt.close(fig);save(data,'figures/'+name+'_source.csv')
 fig,ax=plt.subplots(figsize=(7.1,3.3));ax.axis('off')
 labels=['Archived aggregate data\n22-cell exposure + WPP + GBD','Row-specific source and\noutcome admission','Binary static CRA\ncommon B0 denominator','Formal incidence\nIHD / IS / female breast','Conditional fatal/disability\nCRA mapping reported separately','Economic evidence gate\nno unqualified multiplier']
 positions=[(.02,.72),(.37,.72),(.72,.72),(.02,.25),(.37,.25),(.72,.25)]
 for t,(x,y) in zip(labels,positions):ax.text(x,y,t,transform=ax.transAxes,va='center',fontsize=8,bbox=dict(boxstyle='round',fc='#edf2f7',ec='#53687c'))
 ax.set_title('Figure 1. Static comparative risk assessment');export(fig,'Figure1_framework',pd.DataFrame({'step':labels}))
 b=main[(main.year==2025)&main.scenario.eq('B0')];fig,ax=plt.subplots(figsize=(7.1,3.2));ax.barh(b.disease,b.attributable_B0/1000,color='#547d9b');ax.set_xlabel('Attributable incident events (thousands), 2025');ax.set_title('Figure 2. Binary-model baseline attributable incidence');export(fig,'Figure2_attributable_incidence',b)
 x=cum[cum.scenario.isin(['P15_GRADUAL','R1'])].groupby(['end_year','scenario']).benefit.sum().unstack();fig,ax=plt.subplots(figsize=(7.1,3.3));x.div(1e6).plot.bar(ax=ax,color=['#547d9b','#cf9962'],rot=0);ax.set_xlabel('Inclusive window: 2025 to end year');ax.set_ylabel('Avoided incident events (millions)');ax.set_title('Figure 3. Cumulative formal incidence benefits');export(fig,'Figure3_cumulative',x.reset_index())
 x=main[main.scenario.isin(['P15_GRADUAL','R1'])].groupby(['year','scenario']).benefit.sum().unstack();fig,ax=plt.subplots(figsize=(7.1,3.2));x.div(1000).plot(ax=ax,color=['#547d9b','#cf9962']);ax.set_ylabel('Annual avoided events (thousands)');ax.set_title('Figure 4. Formal incidence benefits over time');export(fig,'Figure4_annual',x.reset_index())
 dd=det[det.scenario.eq('P15_GRADUAL')].copy();dd['age_group']=dd.age_group.map(lambda a:'70+' if int(a.split('-')[0].replace('+',''))>=70 else a);x=dd.groupby(['age_group','sex']).benefit.sum().unstack().reindex(AGE);fig,ax=plt.subplots(figsize=(7.1,4));im=ax.imshow(x.values/1000,aspect='auto',cmap='Blues');ax.set_xticks(range(2),x.columns);ax.set_yticks(range(len(x)),x.index);fig.colorbar(im,ax=ax,label='Avoided events, 2025–2050 (thousands)');ax.set_title('Figure 5. P15 formal incidence by age and sex');export(fig,'Figure5_heatmap',x.reset_index())
 x=cum[cum.scenario.eq('P15_GRADUAL')&cum.end_year.eq(2050)].sort_values('benefit');fig,ax=plt.subplots(figsize=(7.1,3.2));ax.barh(x.disease,x.benefit/1000,color='#547d9b');ax.set_xlabel('Avoided events, 2025–2050 (thousands)');ax.set_title('Figure 6. Disease contributions to P15');export(fig,'Figure6_disease_rank',x)
 x=cum[cum.scenario.isin(['P15_GRADUAL','P15_IMMEDIATE'])].groupby(['end_year','scenario']).benefit.sum().unstack();fig,ax=plt.subplots(figsize=(7.1,3.2));x.div(1000).plot.bar(ax=ax,rot=0,color=['#547d9b','#cf9962']);ax.set_ylabel('Avoided events (thousands)');ax.set_xlabel('Inclusive window: 2025 to end year');ax.set_title('Figure 7. Timing sensitivity, same final target');export(fig,'Figure7_time_path',x.reset_index())
def verify():
 tests=[]
 def check(i,v,detail,gate='software'):tests.append(dict(id=i,status='PASS' if bool(v) else 'FAIL',gate=gate,evidence=detail))
 p=collapsed_population();pa=read(HERE/'database/pa_binary_exposure.csv');d=read(HERE/'results/disease_age_sex_decomposition.csv');a=read(HERE/'registers/outcome_admission.csv');g=pd.concat([read(HERE/'database/gbd_cases.csv'),read(HERE/'database/gbd_burden.csv')]);valid=d[d.outcome_admission.isin(['FORMAL','CONDITIONAL_CRA_MAPPING'])].copy()
 for c in ['PIF','benefit','attributable_B0','remaining_burden']:valid[c]=pd.to_numeric(valid[c])
 check('WPP2025',p[p.variant.eq('Medium')&p.year.eq(2025)].population.sum()==1113252964,'Official Medium male/female sum')
 check('population_grid',len(p)==1716 and not p.duplicated(['variant','year','sex','age_group']).any(),'3 variants x26 years x22 cells; finer Medium retained in database')
 check('PA_22_unique',len(pa)==22 and not pa.duplicated(['sex','age_group']).any(),'Legacy model source copied intact; no synthesized 2018 fine-age observations')
 check('PA_source_unchanged',np.allclose(pa.p_inactive.to_numpy(),read(R1/'candidate_inputs/pa_2025_legacy.csv').p_inactive.to_numpy(),rtol=0,atol=1e-14),'Numeric source preservation within CSV precision')
 check('probabilities',pa.p_inactive.between(0,1).all() and d.p_inactive_scenario.between(0,1).all(),'All model probabilities')
 check('PIF_no_change',fraction(.3,.3,.837)==0,'Independent formula boundary')
 check('PIF_direction',(valid.PIF>=0).all() and (valid.PIF<=1).all(),'All admitted cells')
 check('benefit_le_total',(valid.benefit<=valid.baseline_total+1e-6).all(),'No avoided events exceed total')
 check('B0_zero',(valid[valid.scenario.eq('B0')].benefit==0).all(),'Actual baseline self comparison')
 kk=['year','disease','measure','sex','age_group'];pv=valid.pivot(index=kk,columns='scenario',values='benefit');post=pv[pv.index.get_level_values('year')>=2030]
 check('P15_R1_identity',np.allclose(post.P15_GRADUAL,post.R1*.15,rtol=1e-10,atol=1e-6),'Common baseline denominator: exact mathematical identity')
 check('P15_le_R1',(pv.P15_GRADUAL<=pv.R1+1e-8).all(),'All matched cells, not R3 vsR2')
 check('immediate_ge_gradual',(pv.P15_IMMEDIATE>=pv.P15_GRADUAL-1e-8).all(),'Immediate same endpoint target')
 check('no_male_female_cancer',not ((d.cause_id.isin([429,435]))&d.sex.eq('Male')).any(),'Female-specific burden and attributed results')
 check('ICH_SAH_blocked',a[a.cause_id.isin([496,497])].outcome_admission.eq('BLOCKED_OUTCOME_MISMATCH').all(),'No IS RR on hemorrhagic stroke')
 check('colon_CRC_not_mapped',a[a.cause_id.eq(441)].outcome_admission.eq('BLOCKED_OUTCOME_MISMATCH').all(),'Aggregate CRC totals retained; no colon RR application')
 health=read(HERE/'results/scenario_health_benefits.csv');rejected=health[health.outcome_admission.eq('BLOCKED_OUTCOME_MISMATCH')]
 check('blocked_blank',len(rejected)>0 and rejected.benefit.eq('').all(),'Actually rejected disease endpoints have blank benefits; detail only includes admitted calculations')
 check('nonfatal_depression',a[a.cause_id.eq(567)&a.measure.isin(['Deaths','YLL'])].outcome_admission.eq('NOT_APPLICABLE').all(),'Not applicable rather than numeric0')
 check('source_keys_unique',not g.duplicated(['cause_id','measure_id','metric_id','year','sex','age_group']).any(),'Exact raw export takes precedence over same legacy key')
 check('admission_keys_unique',not a.duplicated(['cause_id','measure']).any(),'One specific gate per disease endpoint')
 rr=read(HERE/'database/rr_admitted.csv');check('risk_direction',np.allclose(rr.rr_inactive_vs_active,1/rr.c_active_vs_inactive) and np.allclose(rr.rr_lower,1/rr.c_upper),'Inverse interval endpoints swapped')
 check('PAF_denominator_equivalence',np.isclose(float(fraction(.3,.255,.837)),(.3+(.7)*.837-(.255+.745*.837))/(.3+.7*.837)),'Independent risk-mixture difference versus common baseline PAF subtraction')
 links=read(HERE/'database/cost_evidence_links_v3.csv');ex=links[links.link_type.eq('EXACT_LINK')]
 check('exact_cost_link_integrity',all(ex[c].astype(str).str.upper().eq('TRUE').all() for c in ['same_original_study','exact_amount_match','exact_currency_match','exact_cost_definition_match','assignment_allowed']),'All exact cost matches require four matching fields plus assignment permission')
 keys=['year','scenario','disease','sex','age_group'];v=valid.pivot(index=keys,columns='measure',values='benefit')
 check('DALY_YLL_YLD',np.allclose(v.DALY,v.YLL+v.YLD,rtol=1e-6,atol=1e-6),'Conditional DALY point reconciliation; no UI addition')
 cum=read(HERE/'results/scenario_comparison.csv');main=read(HERE/'results/scenario_health_benefits.csv');errs=[]
 for r in cum[cum.outcome_admission.isin(['FORMAL','CONDITIONAL_CRA_MAPPING'])].itertuples():
  s=main[(main.scenario==r.scenario)&(main.disease==r.disease)&(main.measure==r.measure)&main.year.le(r.end_year)];errs.append(abs(float(r.benefit)-pd.to_numeric(s.benefit).sum()))
 check('cumulative_matches_annual',max(errs)<1e-5,'All three inclusive windows versus separately saved annual totals')
 check('decomposition_matches_national',np.isclose(valid[valid.scenario.eq('P15_GRADUAL')&valid.year.eq(2030)].benefit.sum(),pd.to_numeric(main[main.scenario.eq('P15_GRADUAL')&main.year.eq(2030)&main.outcome_admission.isin(['FORMAL','CONDITIONAL_CRA_MAPPING'])].benefit).sum()),'Cross-endpoint software reconciliation only; not an epidemiological combined total')
 source=read(HERE/'database/source_manifest.csv');check('source_hashes',all(sha(ROOT/r.origin_path)==r.sha256 for r in source.itertuples()),'Every inspected source still matches migration hash')
 changed=subprocess.check_output(['git','diff',BASE,'--name-only'],cwd=ROOT,text=True).splitlines()
 check('old_files_unchanged',all(x.startswith('new_study/round8_formal_database_and_analysis/') for x in changed),'Tracked prior files compared to baseline')
 check('admitted_incidence_runs',set(valid[valid.outcome_admission.eq('FORMAL')].disease)=={'IHD','IS','breast_cancer'},'Positive acceptance test plus rejected subtype/sex tests','science')
 tests.extend([dict(id='binary_active_approximation',status='CONDITIONAL',gate='science',evidence='Low-active risk represents all>=600 by explicit binary study assumption; not observed pooled active RR'),dict(id='legacy_exposure_provenance',status='CONDITIONAL',gate='science',evidence='Researcher authorized 22 legacy model probabilities;2018->2025 chain not recovered'),dict(id='burden_endpoint_transport',status='CONDITIONAL',gate='science',evidence='Deaths/YLL/YLD/DALY separately conditional under generic CRA assumptions; no direct endpoint RR claim'),dict(id='economic_admission',status='FAIL',gate='science',evidence='No jointly qualified national price-year/coverage/cost endpoint combination; economic values blank'),dict(id='no_natural_history_CEA_PSA',status='PASS',gate='scope',evidence='New runner calls migration, deterministic fraction arithmetic, plots, notebooks only; no legacy executable import')])
 return tests
def reports():
 main=read(HERE/'results/scenario_health_benefits.csv');cum=read(HERE/'results/scenario_comparison.csv');expo=read(HERE/'results/exposure_source_comparison.csv');cross=read(HERE/'database/old_to_new_crosswalk.csv');a=read(HERE/'registers/outcome_admission.csv')
 def tab(d):return d.to_csv(index=False,float_format='%.6g')
 heads=main[(main.year==2030)&main.scenario.eq('P15_GRADUAL')&main.measure.eq('Incidence')&main.outcome_admission.isin(['FORMAL','CONDITIONAL_CRA_MAPPING'])][['disease','baseline_total','benefit','outcome_admission']]
 meth='''# 静态比较风险方法

本轮以研究者指定的旧22层不足率作为模型暴露，不称为2025年实测。所有≥70岁仍共用原70+暴露参数；人口保存官方五岁年龄层，IHD/IS匹配直接GBD细年龄率，其余旧GBD只支持70+，仅在计算该数据时合并人口。2018调查仅作外部核对，不将粗年龄组伪装为独立五岁观测。WPP Medium官方人口是唯一主分母。其他病种2023 Number除以同层WPP历史人口形成工作率，区别于直接IHME Rate。

令c=RR(active low category / inactive)，D0=p0+(1-p0)c。
PAF_B0=p0(1-c)/D0；PIF=(p0-p1)(1-c)/D0。
remaining_attributable_fraction_B0_denominator=p1(1-c)/D0。
收益=Y_B0×PIF=Y_B0×(PAF_B0−remaining fraction)。不能直接将两个各自以不同风险混合分母计算的PAF相减后乘同一个Y_B0：若用通常PAF(p1)，需先计算Y_scenario=Y_B0×D1/D0，再计算其归因负担。代码使用公共B0分母并测试等价关系。

本轮二分类工作模型以Kyu低活动类别600–3999的风险表示合并达标组≥600。此为明确简化假设，并非文献直接测得全部达标者风险相同；原有高活动者的额外保护未单独识别。新达标者进入低活动类别，不是精确600点效应。此研究者指定近似使B0/P15/R1点估计可计算，不需要连续分布。

IHD、IS和女性乳腺癌发病列为当前研究模型下FORMAL；它们仍依赖上述暴露假设、成人中国外推、无滞后及恒定2023率。T2D因纳入研究亚型提取尚未完全解决，所有输出条件性。死亡不是已直接测量的发病RR效果；按疾病比例向死亡的迁移仅列CONDITIONAL_CRA_MAPPING。YLL另假设同层归因死亡平均损失寿命不变；YLD另假设病程/严重度不因暴露而异、静态病因比例可迁移；DALY来自YLL+YLD。四种结局均不进入正式发病合计。Prevalence不自动准入，也不推导患者年。

通用CRA方法依据：https://www.ncbi.nlm.nih.gov/books/NBK11813/（按年龄性别计算风险归因，并在死亡/发病RR不同时分别使用）；https://www.who.int/news-room/questions-and-answers/item/environmental-health-estimations-of-attributable-burden-of-disease-due-to-a-risk-factor（要求暴露与RR、因果及人群适用性匹配）。这些方法支持明确条件的映射，不证明本研究所有具体终点经验等价。Kyu原表：https://doi.org/10.1136/bmj.i3857 。

P15自2025起0%、3%、6%、9%、12%、15%，此后15%。R1即时全部不足者转类。P15_IMMEDIATE从2025立即15%。2030年起同层同年P15收益严格为R1的15%，是数学恒等而非实证发现。累计窗口均含首尾：2025–2030为6年，2025–2034为10年，2025–2050为26年；不称为真实随访队列或不重复患者数。

RR区间仅作逐参数端点确定性敏感性，不称95%结果UI。全国/高龄上下界不相加。Low/High沿用已归档WPP年末平均的年中近似，70+内部结构按Medium保留，均列条件性人口敏感性。旧疾病趋势按历史log率回归、斜率截断±0.1和2034后减弱仅作结构敏感性；主分析恒定率。旧0.84%暴露趋势没有完成来源适用性核验，不执行为正式趋势。
'''
 txt('reports/METHODS_STATIC_CRA.md',meth)
 txt('reports/OLD_DATABASE_REUSE_AUDIT.md',f'# 旧库复用\n\n检查两份完整工作簿、规定目录、历史源代码及Git路径历史。共登记{len(cross)}个文件/工作表/入口。根目录部分input/config为虚拟路径，旧公开模型由input_schema.json和Public_model_inputs.xlsx在运行时生成；本轮直接读工作簿而未运行旧模型。59张原工作表迁入database/legacy_tables，保留政策成本等仅归档。旧GBD共23580行，保留逐行核验标签并优先用新原始细率替换同键。原ZIP未找回不等于数据不存在。\n\n来源文件SHA与新表对应见old_to_new_crosswalk.csv及source_manifest.csv。没有联系第三方，没有新GBD下载要求。\n')
 txt('reports/DATABASE_MIGRATION_REPORT.md','# 数据库迁移\n\nCSV为唯一模型数值入口，Excel为同值人工浏览版。原值均在legacy_tables留存；主表保留origin_path、sheet/table、哈希与source_status。新规则不继承旧APPROVED文字。旧费用6225美元及T2D/CRC价格年仍遵守Round2逐来源修复，未升级。\n\n暴露对照（比例）：\n```csv\n'+tab(expo)+'```\n主分析采用ROUND8_MAIN_WPP_WEIGHTED。与Round7的21.9660515%不同是明确的研究者本轮基线选择；不平均。与2018差异包含年龄边界、人口权重、年份及未恢复旧转换，不能定量分摊成真实趋势。\n')
 txt('reports/BASELINE_BURDEN_RESULTS.md','# 基线负担\n\n疾病总负担与身体活动归因负担分别保存。IHD/IS直接GBD2023率，其他病种Number/WPP历史率，不将原ZIP缺失的数据抹去。病例、死亡和健康年不能混合相加；ICH/SAH只列总负担，不沿用IS风险。CRC总负担不命名结肠癌归因。\n\n2025正式发病归因：\n```csv\n'+tab(main[(main.year==2025)&main.scenario.eq('B0')&main.measure.eq('Incidence')&main.outcome_admission.eq('FORMAL')][['disease','baseline_total','attributable_B0']])+'```\n')
 txt('reports/MULTISCENARIO_RESULTS.md','# 多情景结果\n\n2030年度：\n```csv\n'+tab(heads)+'```\n\n累计正式发病：\n```csv\n'+tab(cum[cum.outcome_admission.eq('FORMAL')&cum.measure.eq('Incidence')&cum.scenario.isin(['P15_GRADUAL','R1'])][['scenario','disease','end_year','benefit']])+'```\n条件性死亡、YLL、YLD、DALY独立列出，不冒称这些终点均有独立测得RR。没有生成全13病种归因合计。\n')
 txt('reports/ECONOMIC_COVERAGE_RESULTS.md','# 经济覆盖\n\n已保留旧费用、修复后cost_id/evidence_id关联以及Round7中国首年卒中证据。当前仍无一病种同时满足全国正式健康接口、价格年、治疗覆盖与不重叠费用界限：没有医疗节约数值。CNSR3首年直接医疗26612.67元来自520名18–80岁首发住院存活者，不能乘全国所有新发；2020工资估值不证明医疗统一价格年。旧年度现患成本不能乘避免发病。生产率缺中国年龄性别就业/工资与适用因果响应，结果空值。未计算GDP、CEA或政策成本。\n')
 txt('reports/RAND_SCENARIO_LIMITATIONS.md','# RAND接口\n\nR1是二分类转类反事实，非精确600。R2=1.2x且0仍0；R3按基线不足者转类、原达标者增加20%。二分类资料不识别R2/R3全国点估计，因此仅保留定义和Round7外部结构范围文件引用，不虚构数据；不阻断P15/R1。550→660与550→600反例否定R3必优R2；不强制该排序。\n')
 txt('reports/HANDOFF_ROUND8.md',f'# Round8交接\n\n分支：{BRANCH}\n基线：{BASE}\n最终提交：由本目录文件所属Git提交确定（git log -1 --format=%H -- new_study/round8_formal_database_and_analysis），避免提交自引用。\n\n完成两阶段：迁移59张旧工作表及正式CSV数据库；执行二分类静态CRA、情景分解、渐进/立即路径、人口/RR/旧疾病趋势确定性敏感性。正式发病：IHD、IS、女性乳腺癌；T2D及死亡/YLL/YLD/DALY为明确条件性；其他不匹配结局空值。真实结果见MULTISCENARIO_RESULTS.md。费用/生产率没有合格全国接口，未输出节约。\n\n本轮新的暴露基线见exposure_source_comparison.csv，不沿用Round7的21.966%当作同一数据。数据库CSV为模型入口，Excel同值浏览，Notebook调用同一Python函数。\n\n尚需研究解释：旧22层率的2018→2025链缺失；合并达标组的低活动RR近似；T2D亚型；条件性fatal/disability映射；旧70+粗年龄率与WPP再基准化；费用价格年与覆盖。没有再次索取GBD或连续暴露分布。\n\n下一轮可基于正式发病和条件性负担撰写分层结果，并由Work审核这些明确假设。验证报告区分软件与科学门槛，测试通过不是证据补全。没有自然史模型、PSA、CEA、政策成本；没有修改Round1–7、原ZIP或主分支。\n')
 txt('README.md',f'# Round8正式数据库与静态比较风险分析\n\n基线`{BASE}`；分支`{BRANCH}`。\n\n运行：仓库Python环境执行 `python new_study/round8_formal_database_and_analysis/run_round8.py`。使用pathlib定位；不执行任何历史模型。CSV为数值入口，人工浏览数据库Excel由build_workbook.mjs从CSV导出。\n\n先读reports/METHODS_STATIC_CRA.md和HANDOFF_ROUND8.md。结果标记FORMAL仅表示在本轮指定二分类近似下的正式模型点估计，非全部输入为实测；CONDITIONAL_CRA_MAPPING不得混入正式发病合计。\n')
def notebooks(execute=True):
 import nbformat
 from nbclient import NotebookClient
 specs=[('01_database_migration','数据库来源与暴露复核',"from round8 import exposure_summary\nexposure_summary()[['sex','age_group','population','p_inactive']].head(8)"),('02_baseline_burden','基线总量与归因负担',"read(HERE/'results/attributable_burden_2025.csv').query('outcome_admission == \"FORMAL\"')[['disease','measure','baseline_total','attributable_B0']]"),('03_multiscenario','正式与条件性情景',"read(HERE/'results/scenario_comparison.csv').query('outcome_admission == \"FORMAL\" and scenario == \"P15_GRADUAL\"')[['disease','end_year','benefit']]"),('04_economic_admission','经济证据门槛',"read(HERE/'registers/economic_admission.csv')[['disease','module','result_status']]"),('05_validation_figures','验证与实际图表',"from deliver import verify\ntests=verify()\nassert not [t for t in tests if t['gate']=='software' and t['status']=='FAIL']\npd.DataFrame(tests)[['id','status','gate']]")]
 logs=[]
 for name,title,code in specs:
  if name=='03_multiscenario':code="recomputed = annual()\nreconciled = aggregate(recomputed, ['year','scenario','disease','measure'])\nreconciled.query('year == 2030 and scenario == \"P15_GRADUAL\" and outcome_admission == \"FORMAL\"')[['disease','measure','benefit']]"
  n=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell('# '+title+'\nCSV模型入口；无隐藏手工参数。'),nbformat.v4.new_code_cell('import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path.cwd()))\nfrom round8 import *'),nbformat.v4.new_code_cell(code)],metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}})
  start=time.time()
  if execute:NotebookClient(n,timeout=240,kernel_name='python3',resources={'metadata':{'path':str(HERE)}}).execute()
  path=HERE/'notebooks'/f'{name}.ipynb';path.parent.mkdir(exist_ok=True);nbformat.write(n,path);logs.append(dict(notebook=name,executed=execute,code_cells=2,error_count=sum(o.output_type=='error' for c in n.cells if c.cell_type=='code' for o in c.get('outputs',[])),seconds=round(time.time()-start,3)))
 js('logs/notebook_execution.json',logs)
def finalize():
 tests=verify()
 p=HERE/'database/New_study_formal_database_v1.xlsx'
 if p.exists():
  sheets=workbook(p);comparisons=[]
  mapping=json.loads((HERE/'logs/workbook_sheets.json').read_text('utf-8'))
  for name,path in mapping.items():
   target=read(HERE/path).fillna('');actual=sheets[name].fillna('')
   ok=target.shape==actual.shape and list(target.columns)==list(actual.columns)
   if ok:
    for c in target:
     x=target[c].astype(str);y=actual[c].astype(str)
     if (x==y).all():continue
     try:ok=ok and np.allclose(pd.to_numeric(target[c]),pd.to_numeric(actual[c]),equal_nan=True,rtol=1e-12,atol=1e-10)
     except (ValueError,TypeError):ok=False
   comparisons.append(dict(sheet=name,rows=len(target),status='PASS' if ok else 'FAIL'))
  js('logs/excel_csv_reconciliation.json',comparisons);tests.append(dict(id='Excel_CSV_equal',status='PASS' if all(x['status']=='PASS' for x in comparisons) else 'FAIL',gate='software',evidence=f'{len(comparisons)} worksheets compared cellwise'))
 else:tests.append(dict(id='Excel_CSV_equal',status='NOT_CHECKED',gate='software',evidence='Workbook export pending'))
 log=HERE/'logs/notebook_execution.json'
 if log.exists():
  n=json.loads(log.read_text('utf-8'));tests.append(dict(id='Notebook_executed',status='PASS' if len(n)==5 and all(x['executed'] and x['error_count']==0 for x in n) else 'FAIL',gate='software',evidence='nbclient execution logs for all5 notebooks'))
 js('results/model_validation_report.json',dict(branch=BRANCH,base_commit=BASE,checks=tests,software_failures=sum(t['gate']=='software' and t['status']=='FAIL' for t in tests),scientific_status='FORMAL_INCIDENCE_WITH_DECLARED_BINARY_ASSUMPTIONS_AND_SEPARATE_CONDITIONAL_CRA',models_not_run=['natural_history','CEA','PSA']))
 rows=[]
 for p in sorted(HERE.rglob('*')):
  if p.is_file() and not any(x in p.parts for x in ['__pycache__','node_modules','.ipynb_checkpoints','runtime']) and p.name!='SHA256SUMS.csv' and not p.name.endswith('.inspect.ndjson'):
   if p.suffix in ['.ipynb','.md']:
    data=p.read_bytes(); normalized=data.replace(b'\r\n',b'\n')
    if data!=normalized:p.write_bytes(normalized)
   rows.append(dict(path=p.relative_to(HERE).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
 save(pd.DataFrame(rows),'SHA256SUMS.csv')
 return tests
