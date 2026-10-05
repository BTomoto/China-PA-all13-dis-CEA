# GBD标准化替换接口

本目录的两个文件是D3疾病率投影层的唯一GBD数值入口：

- `GBD_burden_components.csv.gz`：Deaths、YLL、YLD、DALY；
- `GBD_cases_components.csv.gz`：Incidence、Prevalence。

当前v1.3版本由用户提供的IHME GBD 2023原始ZIP（2010—2017）与父数据库v1（2018—2023）拼接而成。官方原始ZIP保留在`input/gbd_raw_2010_2017/`，不被覆盖。

最低必需字段为：

`year, cause_id, cause_name, sex_name, age_name, measure_name, val, lower, upper, lancet_outcome_id, lancet_outcome_name`

卒中必须保留缺血性卒中、脑内出血和蛛网膜下腔出血三个`cause_id`；乳腺癌和子宫癌仅保留女性；抑郁症不要求Deaths和YLL。模型会按`lancet_outcome_id`汇总，并强制检查DALY恒等式。

与当前GBD历史窗口对应的人口分母为：

`input/population/WPP2024_China_age_sex_history.csv`

该人口表包含`year, sex, age_group, population`，并覆盖2010—2023年、男女性别和11个模型年龄组。D3主窗口已封库为2010—2023；2018—2023、2023率保持不变和长期持续趋势作为结构敏感性。

当前标准化文件、确定性模型和PSA参数已完成封库；正式运行请使用`notebooks/PA_study_analysis.ipynb`中的“概率敏感性分析”部分。
