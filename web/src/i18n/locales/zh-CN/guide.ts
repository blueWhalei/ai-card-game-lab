export default {
  guide: {
    button: '使用说明',
    title: '使用说明',
    tocTitle: '目录',
    lookupTitle: '查阅',
    intro:
      'CardLab 以「实验」为主线：提出假设、运行对局、审查决策、比较结果、记录结论。训练是可选的改进手段。',
    hero: {
      goPlayers: '去选手配置',
      goExperiments: '去实验列表',
    },
    groups: {
      pages: '实验与页面',
      analyze: '分析',
      metrics: '指标怎么算',
      setup: '设置与环境',
    },
    diagrams: {
      loop: {
        caption: '推荐研究闭环',
        nodes: [
          { label: '选手配置', icon: 'lucide:flask-conical' },
          { label: '开始实验', icon: 'lucide:play', tone: 'primary' },
          { label: '审查决策', icon: 'lucide:eye' },
          { label: '比较结果', icon: 'lucide:git-compare' },
          { label: '记录结论', icon: 'lucide:notebook-pen' },
        ],
      },
      detail: {
        caption: '实验详情页的五个阶段',
        nodes: [
          { label: '没有对局', icon: 'lucide:circle-dashed', tone: 'muted' },
          { label: '正在对局', icon: 'lucide:play' },
          { label: '产出数据', icon: 'lucide:database' },
          { label: '对照实验', icon: 'lucide:git-branch' },
          { label: '给出结论', icon: 'lucide:git-compare', tone: 'primary' },
        ],
        items: [
          '还没开始：一句说明加一个「开始实验」。',
          '进行中：进度数字，按钮变成「观战」。',
          '对局结束后：审查全部决策，包含不符合训练格式要求的记录。',
          '需要验证变化时：用已有选手创建对照，无需先训练。',
          '对照就绪：一句结论加 Δ；完整矩阵点「看完整对比」。',
        ],
      },
      pipeline: {
        caption: '分析页的五个工具',
        hub: '侧栏「分析」或实验详情的更多菜单',
        nodes: [
          { label: '数据', icon: 'lucide:database' },
          { label: '决策点', icon: 'lucide:crosshair' },
          { label: '训练', icon: 'lucide:brain' },
          { label: '追踪', icon: 'lucide:activity' },
          { label: '题库', icon: 'lucide:puzzle' },
        ],
        items: [
          '规模、质量与各模型表现',
          '筛选可训练样本、人工标注，登记为数据集',
          '创建微调任务，或登记为选手',
          '每次模型调用与响应时间',
          '从高分歧局面抽题，离线跑基线与扰动探针',
        ],
      },
    },
    sections: {
      quickStart: {
        title: '推荐闭环',
        steps: [
          '在「选手配置」按本局人数配好模型（斗地主 3 人）。创建实验不会自动开局。',
          '回首页新建实验，进入详情。',
          '在详情页记录假设，开始实验并审查决策；创建对照或比较已有实验，最后记录结论。训练可从「分析」按需进入。',
        ],
      },
      experiments: {
        title: '实验列表',
        body: '首页是实验列表：新建、导入实验包，或加载演示对局（无需密钥）。',
        bullets: ['基准测试用固定发牌，方便对比模型。', '每行显示状态和下一步。'],
      },
      experimentDetail: {
        title: '实验详情页',
        body: '当前阶段突出下一步行动；研究区始终提供假设与结论编辑、比较实验和创建对照。',
        bullets: [
          '对照就绪后是一句结论加 Δ。证据不够时，主句改成「还不足以下结论」，Δ 降为附注。',
          '基准测试在阶段下给出本实验数字；对照用同一手牌再跑一遍。',
          '更多菜单：本实验的决策、数据、训练、追踪，以及档案（假设、协议、导出）。',
        ],
      },
      playerConfigs: {
        title: '选手配置',
        body: '定义决策方式、模型与采样参数。新建实验时按游戏人数选取。',
        bullets: [
          '决策方式：大模型（单次问答）、工具循环（主动调工具）、搜索增强（候选 + rollout）、或启发式 / 随机 / 首位动作基线（零 API）。',
          '提示词在「提示词」页管理，不在这里改。',
          '训练完成的模型可登记为新选手，用来做对照。',
        ],
      },
      games: {
        title: '试玩对局',
        body: '快速开一局，不计入任何实验。适合试配置或演示。',
        bullets: [
          '要记入实验，请从详情页点「开始实验」。',
          '对局结束后会标出 3–5 步高光，可跳到回放或决策点。',
        ],
      },
      pipeline: {
        title: '分析',
        body: '侧栏「分析」下面五个工具（数据 / 决策点 / 训练 / 追踪 / 题库）。从实验进来时，顶上的条可以回到详情。决策点页可筛可训练样本，并对单条做「好 / 坏 / 存疑」标注。',
      },
      compare: {
        title: '实验对比',
        body: '首页「对比多个实验」并排 2–5 个实验。详情页只回答「相对这一轮对照，变了多少」。',
        bullets: [
          '先核对冻结协议差异，勾选允许变化字段后重新比较；缺失协议和未声明差异仅作描述性分析。',
          '配对指标只使用全部实验共同有效且唯一的种子；重复、未完成和无效胜负分别列出。首列为参照，不按数值最大值判胜。',
          '填写名称后重新计算并保存快照，可从已保存列表重开或导出 JSON。当前声明为事后审查，快照不是完整证据包。',
        ],
      },
      metrics: {
        title: '指标怎么算',
        body: '格子旁的 ? 是一句话说明。下面是同一套定义。',
        bullets: [
          '可用来训练：决策点 train_usable = true 的条数。不是「这手牌下得好」。',
          '地主胜率：地主座位赢的局 / 决胜局（有胜负的局）。平局不计入 n。',
          '胜率区间：Wilson 95% 置信区间。决胜局 < 20 或区间宽度 > 0.3 会标「局数还不够」。',
          '出牌解析成功率：parser_ok = true 的次数 / 有解析记录的决策次数。失败会落到规则兜底。',
          '中位 / 慢尾响应：所有决策响应时间的 P50 与 P95。',
          '每局 Token：各局 Token 之和 / 已结束局数。',
          '地主胜率差：本实验地主胜率 − 对照（或上一轮）实验。单位百分点（pp）。',
          '同牌局胜率差：只统计相同发牌种子的配对局。',
          '配对 McNemar / bootstrap：同种子地主胜负翻转的精确 p，以及对种子差分的百分位区间。',
          '场景子分：叫分 / 出牌 / 残局（任一方手牌 ≤8）/ 炸弹。炸弹优先。展示可训练占比与解析成功率，Δ 不是好坏。',
          '对局结果分：终局胜负代理（赢 0.8 / 输 0.3 / 平 0.5），不是单步质量。微调筛选用「可用来训练」。',
          '基准覆盖：创建时写入的固定发牌种子里，已经结束的副数。失败局计入覆盖。种子用尽后不能再采集。',
        ],
      },
      tune: {
        title: '设置与提示词',
        bullets: [
          '设置：只读查看运行环境、路径、推理预算默认、EV 评估对手 / 自博弈代理、跨局记忆范围，以及 API 密钥是否就绪（均在项目根目录 .env 配置）。',
          '改 .env 后需重启；thinking budget、EV 对手、memory 只影响之后新建的实验（在飞实验的 protocol 已冻结）。',
          'DPO 偏好导出与师生蒸馏对仅有 API（无 UI）；SFT 仍走决策点「登记为训练数据集」。',
          '提示词：从设置页进入，管理对局用模板，支持版本管理与 A/B 对比。',
        ],
      },
      prerequisites: {
        title: '环境与依赖',
        bullets: [
          '复制 .env.example 为 .env，至少配置一个云厂商 API 密钥或本机 Ollama。',
          '可选：THINKING_BUDGET_*、EV_LOSS_OPPONENT_KIND、EV_LOSS_SELF_PROXY、MEMORY_SCOPE（none | per_experiment）；设置页可读到当前值。',
          '开始实验前会校验密钥；未配置将被拒绝。',
          '训练功能需执行：cd server && poetry install --with training',
          '推送到 Ollama 需在 .env 中配置 LLAMA_CPP_DIR。',
          '后端启动后可访问 /api/v1/system/preflight 查看开始前检查；设置页也会展示。',
        ],
      },
    },
  },
  firstRun: {
    title: '从零到第一局',
    subtitle: '按检查项走完即可开始实验；没有密钥也可以先加载演示对局。',
    done: '已完成',
    goSettings: '去设置',
    goPlayers: '去选手配置',
    step: {
      provider: '配置模型供应商',
      players: '创建选手',
      experiment: '新建实验',
    },
    hint: {
      provider: '在 .env 配置至少一个 API 密钥，或启动本机 Ollama。设置页可检查是否就绪。',
      players: '当前游戏需要至少 {n} 名选手（模型与采样参数）。',
      experiment: '选选手与目标局数；创建后不会自动开始对局，从详情页再点「开始实验」。',
    },
  },
  metricHint: {
    aria: '这个数字怎么算',
    moreInGuide: '打开使用说明：指标怎么算',
    usable: {
      plain: '这些决策点可以拿去微调，不是「这手牌下得好」。',
      formula: '计数：train_usable = true 的决策点数。过滤规则见决策点页。',
    },
    landlord: {
      plain: '有明确胜负的局里，地主座位赢了多少。',
      formula: '地主胜局 / 决胜局数。n 是决胜局。平局不计入。',
    },
    parser: {
      plain: '模型回复有多少次成功解析成合法出牌，而不是退回规则兜底。',
      formula: 'parser_ok = true 的次数 / 有解析记录的决策次数。',
    },
    latency: {
      plain: '模型单步决策要多久：中位数，以及最慢的 5%。',
      formula: 'P50 / P95：所有决策响应时间的第 50、95 百分位。',
    },
    tokens: {
      plain: '平均每局消耗多少 Token，用来估算费用。',
      formula: '各局 prompt+completion Token 之和 / 已结束局数。',
    },
    overallDelta: {
      plain: '本实验地主胜率减去对照（或上一轮）实验的地主胜率。正负不表示好坏。',
      formula:
        'Δ = 本实验地主胜率 − 对照（或上一轮）实验地主胜率，单位百分点（pp）。详情页按当前实验视角计算。',
    },
    pairedDelta: {
      plain: '只比较发到同一手牌的那些局，更公平。',
      formula: '相同 deal_seed 的配对局里，地主胜率之差。n 是配对数。',
    },
    pairedStats: {
      plain: '配对 McNemar 检验与自助法区间：看同牌局上的胜负翻转是否可信。',
      formula:
        'McNemar：对同种子地主胜/负的不一致对数做精确二项双侧 p。配对 Δ 的 95% 区间用对种子差分做百分位 bootstrap。',
    },
    ci: {
      plain: '在当前局数下，真实胜率大概落在这个区间。局越少区间越宽。',
      formula: 'Wilson 95% 置信区间。决胜局少于 20 或区间宽于 0.3 会标「局数还不够」。',
    },
    scenario: {
      plain: '按叫分、出牌、残局、炸弹拆开看可训练占比和解析成功率。Δ 不是好坏。',
      formula: '残局：任一方手牌 ≤8。炸弹（BOMB/ROCKET）优先于残局。',
    },
    quality: {
      plain: '这是终局胜负打的分，不是「这一手下得好不好」。',
      formula: '该局该座位：赢 0.8 / 输 0.3 / 平 0.5。微调筛选用的是「可用来训练」，不是这个分。',
    },
    benchmarkCoverage: {
      plain: '声明的固定发牌种子里，已经跑完多少副。',
      formula: '分母是创建时写入的 deal_seeds。失败局计入覆盖，不会再追加随机种子。',
    },
    evLoss: {
      plain: '这一手比模拟出的最优候选少赚了多少。0 表示它就是最优的，空白表示没评估过。',
      formula:
        '让出值 = 最优候选的期望收益 − 实际所选的期望收益。期望收益来自对隐藏手牌抽样后把牌局模拟到底，各候选共用同一批抽样。评估参数随记录一同保存，参数不同的两个数不可直接比。',
    },
  },
}
