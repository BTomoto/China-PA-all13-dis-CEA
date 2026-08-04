# Pre-publication extension v2.0

本目录由`src/run_prepublication_extensions_v2.py`生成，包含四疾病健康结局、扩展医疗费用、费用排重、Lancet中国同口径卫星分析、GDP等价生产率收益、RAND校准、投资回报和经济卫星不确定性分析。

重要边界：

- 原正式10,000次PSA和programme-only CEA未被替换；
- 直接医疗节约采用首年事件费用和年度患者年费用的混合扩展口径；
- 2025年公共支付比例是全国桥接值，不是病种特异参数；
- GDP结果是机制核算和RAND校准的GDP等价收益，不是动态CGE；
- `12_economic_satellite_uncertainty.csv`是新增经济模块的不确定性分析，不是原联合PSA的重跑。

完整解释见`docs/投稿前扩展分析报告_四病种医疗费用与GDP_v2.0.md`。

`07b_lancet_gap_decomposition.csv`将本模型与Lancet的病例/费用比值乘法拆分为PA暴露差异和PA校准后的剩余疾病模型差异。
