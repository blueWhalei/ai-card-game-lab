# 供应商费用对账验收

## 准备材料

1. 在获准使用的 OpenAI 组织中导出单个项目的 **Cost data**，格式选 CSV，时间间隔选 1 天。保留原始文件和导出时的组织、项目、币种、分组、筛选条件及 UTC 日期。以已结束的期间为例，导出界面选 10 月 1 日至 10 月 31 日，CardLab 中填 **10 月 1 日至 11 月 1 日（终点不含）**。 [OpenAI 费用导出说明](https://help.openai.com/en/articles/20001072-exporting-monthly-usage-details-from-the-api-usage-dashboard)
2. 在测试研究中选择一个已经保存的成功快照。确认组织、项目、币种及查询范围覆盖整个对账期间，并记录快照 ID、查询终点和保存时间。独立核对文件的导出条件，尤其是 CSV 内没有可映射字段的范围。共享项目的费用归属及供应商入账延迟需要单独核查。 [OpenAI 费用范围与入账说明](https://help.openai.com/en/articles/10478918-reviewing-api-usage-and-costs)
3. 如有对应发票，先确认发票的组织、服务期间和项目费用小计。组织级发票总额涉及的其他项目、组织级费用以及税费或调整需要逐项说明。当前工具的比较单位是单项目费用，组织级总额的完整对账另行记录。 [OpenAI 发票对账说明](https://help.openai.com/en/articles/20001072-exporting-monthly-usage-details-from-the-api-usage-dashboard)

## 保存并只读复算

在「预算与费用 → 从费用 CSV 对账」中选择文件及列映射，填写范围说明，预览并保存。记录研究 URL 中的研究 ID 和已保存列表显示的对账记录 ID。保存差异或不可比记录会进入待复核状态。真实验收使用明确指定的测试研究和对应数据库副本。

在 `server` 目录下，使用项目 Python 环境执行：

```powershell
poetry run python -m scripts.verify_cost_reconciliation `
  --db 'D:\acceptance\app.db' `
  --study 'study-id' --record 'reconciliation-id' `
  --csv 'D:\acceptance\original-cost-export.csv'
```

脚本用只读连接读取明确指定的数据库，在同一读取事务中复算所选记录。可以使用应用结束后的数据库，或通过 SQLite 备份得到的一致性副本。复算使用保存的列映射、范围、快照及所选原始文件，无需提供凭据。输出组织和项目范围、金额、行数、文件摘要和版本等核验信息，原始 CSV 数据行由使用者保管。

`reproduction=reproduced` 表示该记录可复算。另读 `comparison.result` 判断范围内金额一致、有差异或不可比；差额是快照区间金额减 CSV 合计。作废及复核状态独立显示；复算不更改记录或任务限制。只有文件摘要一致且结果与保存内容完全相符时，程序退出码为 0。失败返回退出码 1，并报告文件变化、找不到本研究记录、快照内容变化或读取失败等原因。

## 记录验收结论

记录导出条件、资料来源、快照时间、复算结果、人工核对范围和未纳入费用。差异或不可比需要记录原因及对应依据。若导出、快照和原始账单的项目小计范围无法核实，保留该口径为未确认。输出中的 `invoice_verified` 和 `complete_costs_verified` 均为 false，它们不由程序复算自动确认。

2026-11-24 已用隔离的合成对账记录通过复算验收。复现 -0.100000000000000000 USD 差额并保持数据库字节不变。文件字节改变、所属研究不符、数据库不存在和同金额快照明细改变均被拒绝。对账组件 18 项回归、前端类型检查及脚本 Ruff 和 mypy 通过。

真实验收状态为待执行。当前没有可授权使用的真实账单样例。
