# 证据提取与局限

## WHO目标与中国背景

[WHO指标组](https://www.who.int/data/gho/data/themes/topics/indicator-groups/insufficient-physical-activity-indicator-group)明确2030年相对2010年下降15%。[WHO成人指标元数据](https://www.who.int/data/gho/data/indicators/indicator-details/GHO/prevalence-of-insufficient-physical-activity-among-adults-aged-18-years-(age-standardized-estimate)-(-))定义18岁以上、低于推荐中高强度活动阈值；国别年度结果采用模型并用WHO标准人口计算年龄标准化率。这与本地CCDRFS调查估计不是同一统计序列。

[《健康中国2030》官方文本](https://www.sport.gov.cn/n10503/c772542/content.html)列出2030年经常参加体育锻炼人数5.3亿；[《全民健身计划（2026—2030年）》发布信息](https://www.mohrss.gov.cn/SYrlzyhshbzb/dongtaixinwen/shizhengyaowen/202607/t20260724_580834.html)提出2030年经常参加体育锻炼人数比例约40%。这些是不同定义的参与指标，只作中国政策背景。

## 2010年基准与可比性

已存的[Zhang等2023原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10351178/) Table 2：2010年中国18岁以上不足率17.9%（95%CI 16.3%—19.5%）；男性20.1%（18.5%—21.8%）、女性15.7%（13.9%—17.4%）。另外有18—34、35—49、50—64、65+各年龄组**单独**率，没有性别×年龄联合率。调查使用GPAQ并覆盖职业、交通与休闲领域；所有估计按2010年中国标准人口年龄调整。2018 Gao原文则给18岁以上的性别×粗年龄分层加权率；第二轮2025起点是2018率×WPP 20岁以上人口构成，不是实测值。调查框架在2013年后扩张，权重和年龄边界需继续对齐。可比性表全为FAIL，因此不发布目标数值或差额，也不凭全国率推2010分层。

## Kyu与Schuch

第一轮已存[Kyu 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4979358/)附录1协议第2页研究对象为15岁及以上；第3—4页糖尿病检索词含type 2。附录4 Table C第21页起标题是diabetes，纳入研究展示OR、HR及RR。检索词不能证明每项研究均为成人2型糖尿病，也不能单独完成模型20+准入；T2D继续条件状态。

[Schuch 2018 PubMed原文摘要](https://pubmed.ncbi.nlm.nih.gov/29690792/)报告成人高活动相对低活动的调整后 **OR 0.78（0.70—0.87）**。旧1.28约为倒数，但不应标RR；总活动<600与600—3999的精确比较未证实。旧保存的`Schuch2018.html`是验证页而非全文，本轮只达到摘要核查。

## RAND与Ding

[RAND RR4291报告](https://www.rand.org/content/dam/rand/pubs/research_reports/RR4200/RR4291/RAND_RR4291.pdf) Table 4.1引用Guthold等国别模型估计，中国男性16.0%（11.7%—21.4%），女性12.2%（8.5%—17.3%），不能替代CCDRFS 2010或2018观察。附录C.1说明因多数国家无可比活动量连续分布，借Eurobarometer 88.4五个欧洲国家的形状，再按Guthold不活动比例平移生成国别分布；五岁年龄组从25岁起。RAND“全人群+20%”实际让**非零**活动者的量增加20%，零活动者不变。中国连续MET分布及国内适用性未核，扩展情景仍阻断。公开PDF直下遇CloudFront 403，本轮仅网页索引阅读，未归档原件。

[Ding等2016](https://pubmed.ncbi.nlm.nih.gov/27475266/)是以国别不足率及疾病PAF估算经济负担，未提供中国连续MET分布。[公开存档的原文](https://www.icsspe.org/system/files/Ding%20et%20al.%20-%20The%20economic%20burden%20of%20physical%20inactivity%20a%20global%20analysis.pdf) Table 1给中国2013年直接医疗归因成本3,075,139千国际元（区间1,194,333—6,635,493千），这是**已发表输出**而非可回填的基础费用或活动分布；单列`ding_china_published_outputs.csv`。公开PDF直下因站点证书时间无效而失败，没有绕过TLS验证。旧RAND GDP输出不能当中国健康或费用模型输入。

## Jia费用

新增归档首都医科大学公开[Jia等2018 PDF](https://news.ccmu.edu.cn/docs/2018-06/20180621160034890292.pdf)。Table 2第487页给每名AD患者2015年年度总社会成本19,144.36美元，以及门诊2,501.18、住院9,692.09、自付468.97美元各自服务使用者均值和人数。正文给全国直接医疗费用占总成本32.51%。以已四舍五入数字相乘为6,223.83美元，**不能精确恢复旧6,225美元**；表中项目均值不能直接相加为全体患者人均值。痴呆已退出主分析，且AD不等于GBD全部痴呆，故该费用仍不准入。

## GBD与结局转换

[IHME工具指南](https://www.healthdata.org/sites/default/files/2024-06/IHME_GBD_2021_DATA_TOOLS_GUIDE_06262024.pdf)确认结果工具支持下载CSV并要求登录；它是2021版通用指南，不能据此确认2023工具支持100+、结肠单独cause、食管/胃亚型及每个measure组合。旧值追溯四组ZIP与新模型2023率查询分列；`gbd_new_model_detailed_requests.csv`把病种×六结局、性别、年份、Rate/Number及20—24至100+逐项列出。未证实的cause ID保持空白，真实选项需用户正常登录后截图/代码簿核实。

发病减少转为患病患者年需要发病、存活、死亡、缓解、时滞及现患基线的连接规则；转死亡/YLL/YLD/DALY还需对应风险证据和Work认可的归因结构。费用需与患者年或新发数的单位、治疗覆盖、价格年及重复费用边界一致。本轮只登记所需数据，没有冻结疾病模型。
