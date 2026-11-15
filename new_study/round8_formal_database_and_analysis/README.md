# Round8正式数据库与静态比较风险分析

基线`0aaa68fd8cf7bfd2230d02c28abcdb90e5fa6a37`；分支`codex/formal-database-and-analysis-round8`。

运行：仓库Python环境执行 `python new_study/round8_formal_database_and_analysis/run_round8.py`。使用pathlib定位；不执行任何历史模型。CSV为数值入口，人工浏览数据库Excel由build_workbook.mjs从CSV导出。

先读reports/METHODS_STATIC_CRA.md和HANDOFF_ROUND8.md。结果标记FORMAL仅表示在本轮指定二分类近似下的正式模型点估计，非全部输入为实测；CONDITIONAL_CRA_MAPPING不得混入正式发病合计。
