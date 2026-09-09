export default {
  settings: {
    loadFailed: 'Failed to load settings',
    loadError: 'Failed to load settings. Confirm the backend is running, then retry.',
    runtime: 'Runtime',
    runtimeHint:
      'Paths and API keys live in the project-root {env} file and apply after restart. The database path cannot be stored in the database itself. Player models and sampling are in',
    runtimeHintMid: '; prompts are in',
    app: 'App',
    version: 'Version',
    debug: 'Debug',
    maxGames: 'Max concurrent games',
    thinkingEffort: 'Default reasoning effort',
    thinkingMaxTokens: 'Default reasoning token cap',
    thinkingBudgetHint:
      'Snapshotted into protocol.solver.thinking_budget when an experiment is created (in-flight runs stay frozen). Set THINKING_BUDGET_REASONING_EFFORT / THINKING_BUDGET_MAX_TOKENS in {env}.',
    startup: 'Startup check',
    providers: 'Providers',
    configuredN: '{ready} / {total} configured',
    configured: 'Configured',
    unconfigured: 'Not configured',
    showIdle: '{n} not configured',
    hideIdle: 'Hide unconfigured',
    disk: 'Disk',
    storageLink: 'Storage',
    database: 'Database',
    dataDir: 'Data directory',
    paths: 'Paths',
    modelsDir: 'Models directory',
    providerMeta: {
      openai: { name: 'OpenAI', description: 'GPT-4o, GPT-4o-mini, and similar models' },
      deepseek: { name: 'DeepSeek', description: 'deepseek-v4-flash (default) / deepseek-v4-pro' },
      kimi: { name: 'Kimi / Moonshot', description: 'Moonshot-v1 family' },
      dashscope: { name: 'DashScope', description: 'Alibaba Qwen models' },
      zhipu: { name: 'Zhipu AI', description: 'GLM-4 family' },
      minimax: { name: 'MiniMax', description: 'MiniMax-Text-01 and similar models' },
      yi: { name: '01.AI', description: 'Yi-Lightning and similar models' },
      baichuan: { name: 'Baichuan', description: 'Baichuan4 family' },
      ollama: { name: 'Ollama', description: 'Local open-source models' },
    },
  },
  preflight: {
    providers_any:
      'No LLM provider is configured. Set a cloud API key in the project-root .env, or install Ollama and pull a local model (e.g. ollama pull qwen2.5:7b).',
    protocol: 'This experiment has no complete protocol. Recreate the experiment before starting games.',
    providers_seats:
      'Seat provider not configured: {providers}. Set the API key in .env, or change the player configs.',
    providers_seatsIncomplete: 'Cannot check seat providers (protocol is incomplete).',
    training_deps:
      'Training extras are not installed, so tasks cannot be created. Run: cd server && poetry install --with training',
    memory_smoke:
      'About {available_mb}MB RAM free, below the CPU quick-check threshold of {threshold_mb}MB. Creating a task may be rejected.',
  },
}
