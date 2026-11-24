export default {
  pairedBoard: {
    title: '重建牌桌',
    before: '当前步骤：行动前局面；下方为该步记录的动作。',
    basis:
      '依据冻结发牌种子与连续动作重建；当前引擎版本 {version}。记录截止 {cutoff}，读取时间 {read}。',
    showAll: '显示研究者视角的重建手牌',
    actorScope: '行动者视角：显示本人手牌、其他席位剩余张数及公共牌面。',
    allScope: '研究者视角包含其他席位的重建手牌；这些牌不属于行动者当时的可见信息。',
    limits:
      '重建依赖当前引擎与保留记录，不是原始牌桌快照或完整模型输入。引用保存决策字段，不冻结本次重建画面；路径分歧后的相同步骤不能用于直接归因，也不增加独立对局数。',
    unsupported: '当前引擎版本与冻结条件不同，未重建牌桌；下方仍可查阅保留的决策记录。',
    unverified: '该步或此前的记录缺失、不一致或无法核对，未重建牌桌；不能依据后续记录补推牌面。',
  },
  evidenceEntry: {
    open: '引用到比较草稿',
    title: '选择引用所属的比较',
    scope:
      '仅列出冻结共同样本包含此决策来源对局、且决策不晚于统计截止时间的比较。选择后先核对来源，再明确加入草稿。',
    empty: '没有找到符合范围的已保存比较。可先为该运行建立并保存比较；来源必须属于共同有效样本。',
    more: '继续查找比较',
    review: '核对待引用决策',
    previewScope:
      '此决策已通过比较范围核对。打开此页不会添加引用；明确加入后可填写说明。发布时保存当时的决策字段，当前预览不保证来源之后不变。',
  },
  paired: {
    formatDiagnostics:
      '训练格式可用 {train}（{usable}/{n} 条） · 解析成功 {parser}（{ok}/{parser_n} 条有追踪记录）',
    scenarioFilter: '在共同有效样本内按场景定位',
    scenarioScope:
      '按快照冻结的发牌成员和记录截止时间查找当前仍保存的决策。导航计数可能随源记录变化；不是逐条冻结归档，也不是运行整体格式诊断表的原分母。',
    scopeTime: '冻结共同有效发牌 {n} 组 · 记录截止 {cutoff} · 读取于 {time}',
    scenarioCounts:
      'A：{left_n} 条决策 / {left_game_n} 局；B：{right_n} 条决策 / {right_game_n} 局。任一侧有记录的同源对局：{pair_n} 组。',
    scenarioLimits:
      '同局决策相互关联，记录数不是独立样本数；同一对局可出现在多个场景，各组对局数不能相加。任一侧匹配即保留整组，对侧未匹配不代表能力较弱。重复或不完整记录可能无法定位，计数不等于可核验步骤数。',
    dealCounts: '本组所选范围：A {left_n} 条决策，B {right_n} 条决策。',
    emptyScenario: '冻结共同有效样本内没有该场景记录，不能据此判断表现。',
    previousMatch: '上一个匹配步骤',
    nextMatch: '下一个匹配步骤',
    matches: '{n} 个可定位步骤；完整时间线保留上下文。',
    matchesFilter: '符合场景筛选',
    contextOnly: '上下文记录，未匹配所选场景',
    positionMissing: '所选场景、发牌或步骤不存在，或地址不合法。未自动改选其他记录，请重新选择。',
    resetSelection: '重新选择对局',
    matrixScope:
      '此表保存运行整体的格式诊断统计，不能解释为策略能力或场景胜率。下方导航限于冻结共同有效样本，两者分母不同。',
    inspectScenario: '查看该场景的共同有效样本',
    title: '沿着同一副牌，看决策如何分开',
    deal: '同源对局',
    dealN: '第 {n} 副 / 共 {total} 副',
    firstDifference: '跳到首次行动分歧',
    previous: '上一步',
    next: '下一步',
    step: '步骤 {n} / {total}',
    timeline: '共同决策时间线',
    empty: '当前快照还没有可对照的共同有效对局。',
    ended: '这一侧的对局已结束。',
    missing: '本步记录缺失、重复或不完整，无法展示。',
    scope: '对照的是已记录局面；路径分开后，同一步数不代表相同局面。',
    cite: '引用当前对照',
    basis: '查看对齐依据',
    method:
      '核对冻结样本、席位、记录阶段、手牌、对手张数、上一动作、展示菜单与此前动作。缺口之后不恢复同一路径判断；不代表完整模型输入相同或策略更优。',
    seed: '冻结发牌种子：{seed}',
    actionId: '已记录动作标识',
    bidPoints: '叫 {n} 分',
    citationLimit: '这些决策会超过 30 条引用，请先在草稿中移除部分引用。未添加任何新条目。',
    status: {
      same: '此前路径与本步记录一致',
      divergence: '此前记录一致，本步选择分开',
      different_path: '此前已有行动分歧，当前是不同路径',
      different_context: '本步记录局面不同，无法直接归因于动作选择',
      unverified: '记录不足以确认同一路径',
    },
    reason: {
      missing: '至少一侧缺少本步记录，或已结束。',
      duplicate: '同一步存在重复记录，没有自动选择其中一条。',
      invalid_context: '局面、动作菜单或实际选择记录不足以确认，可能包含解析回退。',
    },
  },
}
