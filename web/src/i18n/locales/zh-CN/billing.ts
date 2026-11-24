import schedule from './billingSchedule'
import reconciliation from './billingReconciliation'
export default {
  billing: {
    schedule,
    reconciliation,
    triggers: { manual: '手动同步', scheduled: '周期同步' },
    validUntil:
      '按查询终点计算的快照时限：{time}（本地时间）。未到时限也可能因失败或超限被拒绝；此时限不表示供应商费用已完整入账。',

    title: '供应商项目费用',
    manualTitle: '人工登记费用',
    scope:
      '来源为 OpenAI Costs API。查询选定组织、项目及 UTC 时间区间内的供应商费用记录；不是最终结算发票，也不代表本研究的完整费用。',
    coverage:
      '共享项目可能包含其他研究的支出；项目以外、组织层级、其他供应商和未入账费用不在此查询覆盖范围。供应商统计可能延迟或修订。明细条数不是研究样本量；无明细和零值均不能证明实际支出为零。',
    accounting:
      '每次同步从所选起点查询至请求时刻，区间含起点、不含终点，最长 366 天。分页全部成功后更新快照；重复同步不累加历史快照。按供应商返回的 USD 金额累加，包含返回的负向调整，不换算汇率。',
    limits:
      '按项目费用独立限制本研究的新受控任务，不与人工登记费用相加、不自动分摊。启用后，达到上限、无有效快照、最后同步失败或同步间隔超限均拒绝新任务。任一已启用限制触发即拒绝；仍不预留未来费用、不停止已接受任务。供应商统计延迟和并行调用可能导致超限，因此不是实际支出硬上限。',
    setup:
      '同步需在服务端配置独立的 OPENAI_BILLING_ADMIN_KEY 与 OPENAI_BILLING_ORGANIZATION_ID，重启服务后生效。模型调用密钥不能代替管理密钥，请勿将密钥填入下方表单。',
    notReady: '管理凭据未配置，或当前服务端组织与已保存范围不一致。费用未知，不能按零处理。',
    organization: '组织',
    project: '供应商项目 ID',
    start: '累计起始日期（UTC）',
    periodHint:
      '预算周期不会自动重置。修改任何配置将建立新版本，需要重新同步才能使用该版本的费用限制。启用限制时起点须在过去 365 天内。',
    limit: '项目费用上限（USD，留空表示未设置）',
    freshness: '允许的最长同步间隔（小时，1–24）',
    enforce: '按供应商项目费用限制本研究的新任务',
    configure: '设置供应商费用同步',
    sync: '立即同步费用',
    syncing: '正在同步费用…',
    syncHint: '同步只读取官方费用接口；可以手动发起或明确启用周期计划，不会自动付款或运行模型。',
    synced: '同步已完成；显示本次查询范围内的供应商记录。',
    syncFailed: '同步未完成，未采用本次部分结果。历史成功快照仍可查看，不能视为当前费用。',
    loadFailed: '无法读取同步状态；不能据此判断费用或任务是否可接受。',
    amount: '最近成功快照金额（USD）',
    unknown: '无成功快照',
    window: '查询范围：{start} 至 {end}（UTC，终点不含）',
    timestamp: '快照保存：{time}',
    readAt: '状态读取：{time}；服务端在接受任务时重新检查。',
    gateBlocked: '供应商费用限制已阻止新的受控任务。',
    gateOpen:
      '供应商费用限制当前未阻止任务；人工登记费用限制仍独立生效，此状态不代表费用完整或实际支出低于预算。',
    states: {
      unconfigured: '未设置查询范围',
      missing: '当前配置尚无成功快照',
      failed: '最后同步失败',
      interrupted: '上次同步未完成',
      stale: '超过允许的同步间隔',
      reached: '快照金额达到上限',
      below: '快照金额未触及已设置上限',
    },
    history: '同步记录（最近 10 次）',
    configHistory: '同步与限制配置记录（最近 10 版）',
    historyScope: '页面只显示最近记录；全部配置版本、同步尝试及成功明细保存在本地数据库中。',
    status: {
      running: '同步中',
      succeeded: '同步成功',
      failed: '同步失败',
      interrupted: '同步中断',
    },
    evidence: '查看来源明细',
    evidenceTitle: '同步来源明细',
    evidenceFailed: '明细读取失败。请重试；失败不表示没有明细。',
    empty: '本次接口查询未返回费用明细；这不表示实际费用为零。',
    noHistory: '尚未发起同步。',
    lineItem: '费用项目未提供',
    recordCount: '返回 {n} 条费用明细；金额合计不受明细页码影响。',
    closeEvidence: '关闭来源明细',
    invalid:
      '请填写有效项目 ID、UTC 起始日期、1–24 小时的同步间隔及修改说明。金额为非负十进制数，最多 9 位整数和 6 位小数；启用限制需设置金额。',
    reload: '重新载入同步配置',
    errors: {
      BILLING_AUTH: '管理凭据被拒绝，请检查组织及费用读取权限。',
      BILLING_RATE_LIMIT: '供应商暂时限制请求频率，请稍后重试。',
      BILLING_REMOTE: '供应商费用接口未成功响应。',
      BILLING_NETWORK: '费用接口连接失败或超时。',
      BILLING_RESPONSE: '费用响应未通过金额、项目范围或分页校验，未采用部分结果。',
      BILLING_PERIOD: '查询周期为空或超过 366 天，请检查 UTC 起始日期。',
      BILLING_INTERRUPTED: '同步中断，未保存部分费用。',
    },
  },
}
