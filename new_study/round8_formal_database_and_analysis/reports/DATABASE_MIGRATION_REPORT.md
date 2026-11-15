# 数据库迁移

CSV为唯一模型数值入口，Excel为同值人工浏览版。原值均在legacy_tables留存；主表保留origin_path、sheet/table、哈希与source_status。新规则不继承旧APPROVED文字。旧费用6225美元及T2D/CRC价格年仍遵守Round2逐来源修复，未升级。

暴露对照（比例）：
```csv
source,sex,age,val,population
ROUND8_MAIN_WPP_WEIGHTED,Both,20+,0.236441,1113252964
LEGACY_ROUNDED_POP_WEIGHTS,Both,20+,0.236441,1113260000
ROUND8_MAIN_WPP_WEIGHTED,Male,20+,0.258596,559008312
LEGACY_ROUNDED_POP_WEIGHTS,Male,20+,0.258596,559010000
ROUND8_MAIN_WPP_WEIGHTED,Female,20+,0.214095,554244652
LEGACY_ROUNDED_POP_WEIGHTS,Female,20+,0.214096,554250000
ROUND7_2018_STRUCTURE_MODEL,Both,20+,0.219661,1113252964
```
主分析采用ROUND8_MAIN_WPP_WEIGHTED。与Round7的21.9660515%不同是明确的研究者本轮基线选择；不平均。与2018差异包含年龄边界、人口权重、年份及未恢复旧转换，不能定量分摊成真实趋势。
