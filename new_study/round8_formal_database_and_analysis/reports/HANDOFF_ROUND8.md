# Round8交接

分支：codex/formal-database-and-analysis-round8
基线：0aaa68fd8cf7bfd2230d02c28abcdb90e5fa6a37
最终提交：由本目录文件所属Git提交确定（git log -1 --format=%H -- new_study/round8_formal_database_and_analysis），避免提交自引用。

完成两阶段：迁移59张旧工作表及正式CSV数据库；执行二分类静态CRA、情景分解、渐进/立即路径、人口/RR/旧疾病趋势确定性敏感性。正式发病：IHD、IS、女性乳腺癌；T2D及死亡/YLL/YLD/DALY为明确条件性；其他不匹配结局空值。真实结果见MULTISCENARIO_RESULTS.md。费用/生产率没有合格全国接口，未输出节约。

本轮新的暴露基线见exposure_source_comparison.csv，不沿用Round7的21.966%当作同一数据。数据库CSV为模型入口，Excel同值浏览，Notebook调用同一Python函数。

尚需研究解释：旧22层率的2018→2025链缺失；合并达标组的低活动RR近似；T2D亚型；条件性fatal/disability映射；旧70+粗年龄率与WPP再基准化；费用价格年与覆盖。没有再次索取GBD或连续暴露分布。

下一轮可基于正式发病和条件性负担撰写分层结果，并由Work审核这些明确假设。验证报告区分软件与科学门槛，测试通过不是证据补全。没有自然史模型、PSA、CEA、政策成本；没有修改Round1–7、原ZIP或主分支。
