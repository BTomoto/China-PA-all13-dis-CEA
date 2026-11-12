# 审计修订记录

修订清单见 `registers/audit_revision_log.csv`。第二轮 `work_decisions.csv` 和 `disease_endpoint_admission_work_v1.csv` 原样保留，作为历史决定。**本轮撤销“同一个疾病PIF自动接六结局”的准入**。现按来源数值、风险比较、目标暴露接口、结局计算、GBD原件和最终`model_ready`逐门槛记录。Kyu发病/事件类别RR并没有分别量到死亡、YLL、YLD、DALY及患病；采用比例归因或动态转移须由Work确定，并取得相应资料。

高血压当前独立模块只考虑新发和累计患病患者年。死亡、YLL、YLD、DALY四项均标 `NOT_APPLICABLE`；新发到患者年的关系仍缺方法和数据。抑郁死亡/YLL继续标不适用。癌症性别与亚型限制照第二轮保留，但均未达到最终model_ready。

年龄映射只复制2018年CCDRFS粗年龄组的率及原95%CI。共享的两条细年龄组带同一`shared_parameter_id`，以后不应当作为独立调查抽样。人口表每行注明来自官方`PopMale`或`PopFemale`，千人转换为人。

旧费用表的`price_year`有些是旧模型假设，并非原文确认的价格年。本轮费用表将二者分列，并补入已有T2D 2019和中国CRC 2014候选。全部费用仍未准入。Jia原文见另份证据记录。

验证报告使用`PASS`、`FAIL`、`NOT_CHECKED`、`NOT_APPLICABLE`。其中“未运行模型”只按本次实际执行命令与生成脚本说明；删除第二轮无依据的自动通过布尔值。GBD 2023登录后真实菜单的年龄/cause可选层级尚未检查，不以旧版通用说明冒充2023已验证能力。
