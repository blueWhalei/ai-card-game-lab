export default {
  settings: {
    loadFailed: '加载系统设置失败',
    loadError: '设置加载失败，请确认后端已启动后重试。',
    runtime: '运行环境',
    runtimeHint:
      '路径与 API 密钥写在项目根目录 {env}，重启后生效。库路径不能存进数据库本身。选手的模型与采样在',
    runtimeHintMid: '，提示词在',
    app: '应用',
    version: '版本',
    debug: '调试',
    maxGames: '并发对局上限',
    thinkingEffort: '推理 effort 默认',
    thinkingMaxTokens: '推理 token 上限默认',
    thinkingBudgetHint:
      '新建实验时写入 protocol.solver.thinking_budget（在飞实验不受改动影响）。在 {env} 设置 THINKING_BUDGET_REASONING_EFFORT / THINKING_BUDGET_MAX_TOKENS。',
    evOpponentKind: 'EV 评估对手',
    evSelfProxy: '自博弈代理',
    memoryScope: '跨局记忆',
    evalMemoryHint:
      '新建实验时写入 protocol.scorer.evaluator（对手 / 代理）与 protocol.solver.memory（在飞实验不受改动影响）。在 {env} 设置 EV_LOSS_OPPONENT_KIND / EV_LOSS_SELF_PROXY / MEMORY_SCOPE。',
    startup: '启动检查',
    providers: '供应商',
    configuredN: '{ready} / {total} 已配置',
    configured: '已配置',
    unconfigured: '未配置',
    showIdle: '未配置 {n} 个',
    hideIdle: '收起未配置',
    disk: '磁盘',
    storageLink: '存储管理',
    database: '数据库',
    dataDir: '数据目录',
    paths: '路径',
    modelsDir: '模型目录',
    providerMeta: {
      openai: { name: 'OpenAI', description: 'GPT-4o、GPT-4o-mini 等' },
      deepseek: { name: 'DeepSeek', description: 'deepseek-v4-flash（默认）/ deepseek-v4-pro' },
      kimi: { name: 'Kimi / Moonshot', description: 'Moonshot-v1 系列' },
      dashscope: { name: 'DashScope', description: '阿里云通义千问系列' },
      zhipu: { name: '智谱 AI', description: 'GLM-4 系列' },
      minimax: { name: 'MiniMax', description: 'MiniMax-Text-01 等' },
      yi: { name: '零一万物', description: 'Yi-Lightning 等' },
      baichuan: { name: '百川智能', description: 'Baichuan4 系列' },
      ollama: { name: 'Ollama', description: '本机开源模型' },
    },
  },
  preflight: {
    providers_any:
      '未配置可用模型供应商。请在项目根目录 .env 填写云厂商 API 密钥，或安装 Ollama 并拉取至少一个本地模型（如 ollama pull qwen2.5:7b）。',
    protocol: '实验协议缺失或不完整，请重新创建实验后再开始对局',
    providers_seats: '实验座位供应商未配置：{providers}。请在 .env 配置密钥，或改选手配置。',
    providers_seatsIncomplete: '无法校验座位供应商（协议不完整）',
    training_deps:
      '未安装训练依赖，无法创建训练任务。请执行：cd server && poetry install --with training',
    memory_smoke:
      '可用内存约 {available_mb}MB，低于 CPU 快速验证建议阈值 {threshold_mb}MB；创建任务时可能被拒绝。',
  },
}
