export default {
  app: {
    name: 'CardLab',
    lab: 'CardLab',
  },
  locale: {
    zh: '中文',
    en: 'English',
    switchToZh: '切换为中文',
    switchToEn: 'Switch to English',
  },
  theme: {
    toLight: 'Switch to light mode',
    toDark: 'Switch to dark mode',
    light: 'Light mode',
    dark: 'Dark mode',
  },
  nav: {
    experiments: 'Experiments',
    analyze: 'Analyze',
    playerConfigs: 'Player configs',
    games: 'Trial games',
    data: 'Data',
    decisions: 'Decision points',
    training: 'Training',
    prompts: 'Prompts',
    traces: 'Invocation records',
    puzzles: 'Puzzles',
    settings: 'Settings',
    guide: 'Guide',
    experimentDetail: 'Experiment detail',
    experimentCompare: 'Compare experiments',
    collapseSidebar: 'Collapse sidebar',
    expandSidebar: 'Expand sidebar',
  },
  common: {
    exportSaved: 'JSON file saved.',
    exportReveal: 'Show in folder',
    exportRevealFailed:
      'Unable to locate the saved file. Check that it has not been moved or deleted, then retry after the current operation finishes.',
    exportDownloadStarted: 'Download handed to your browser. Check its download list.',
    exportSaveFailed:
      'The file could not be saved. Finish any current save or close operation, then retry and check that the selected location is writable. Only JSON files are supported.',
    exportTooLarge: 'This export exceeds the 32 MiB desktop JSON limit. Reduce the export scope.',
    noOutcomes: 'No decided games',
    cancel: 'Cancel',
    confirm: 'Confirm',
    ok: 'OK',
    save: 'Save',
    create: 'Create',
    delete: 'Delete',
    edit: 'Edit',
    close: 'Close',
    back: 'Back',
    retry: 'Retry',
    loading: 'Loading…',
    loadingEllipsis: 'Loading...',
    select: 'Select',
    optional: 'Optional',
    none: 'None',
    all: 'All',
    name: 'Name',
    notes: 'Notes',
    status: 'Status',
    progress: 'Progress',
    actions: 'Actions',
    createdAt: 'Created',
    updatedAt: 'Updated',
    model: 'Model',
    player: 'Player',
    players: 'Players',
    games: 'Games',
    rounds: 'Rounds',
    winRate: 'Win rate',
    wins: 'Wins',
    winner: 'Winner',
    pause: 'Pause',
    resume: 'Resume',
    start: 'Start',
    detail: 'Details',
    expand: 'Expand',
    collapse: 'Collapse',
    noData: 'No data',
    noContent: 'Nothing here',
    emptyRecords: 'No records yet',
    pageSize: 'Per page',
    pageSizeUnit: '',
    pageSizePlaceholder: 'Count',
    totalItems: '{n} total',
    prevPage: 'Previous',
    nextPage: 'Next',
    menu: 'Menu',
    closeMenu: 'Close menu',
    howTo: 'How to use',
    hide: 'Hide',
    enabled: 'On',
    disabled: 'Off',
    on: 'On',
    off: 'Off',
    unknown: 'Unknown',
    demo: 'Demo',
    path: 'Path',
    recent: 'Recent',
    sampling: 'Sampling',
    noId: '(no ID)',
    dash: '—',
    open: 'Open',
    more: 'More',
  },
  error: {
    SUPPLIER_RECONCILIATION_PENDING:
      'Supplier cost reconciliation records await review, so new controlled tasks were refused. Review and document disposition in Budget and expenses; a new sync does not resolve differences.',
    RECONCILIATION_CSV_INVALID:
      'Could not parse the cost CSV. Check the encoding, headers, row lengths, amounts and UTC dates. Dates must use YYYY-MM-DD or a UTC midnight timestamp.',
    RECONCILIATION_CSV_COLUMNS: 'Choose a different file column for each field.',
    RECONCILIATION_CSV_SCOPE:
      'A CSV row is outside the selected service period or conflicts with the organization, project or currency entered. Check the export filters and column mapping.',
    RECONCILIATION_SOURCE:
      'The selected snapshot is missing, unsuccessful or cannot be verified against its stored source. Select a successful snapshot again.',
    RECONCILIATION_CONFLICT:
      'The reconciliation state changed or a repeated request has different contents. Your input was retained; reload the current record and review it.',
    RECONCILIATION_CHANGED:
      'The evidence or snapshot differs from the preview. Preview again before explicitly saving.',
    RECONCILIATION_NOT_FOUND: 'This reconciliation record does not belong to the current research.',
    RECONCILIATION_REVIEW:
      'This review action is not allowed for the current record. Voided records retain their history; register a new record to correct inputs.',
    SUPPLIER_BUDGET_REACHED:
      'The supplier project cost snapshot reached its limit. New controlled tasks are rejected. Review the project, query period and source lines under Budget and expenses. This is not the complete research cost.',
    SUPPLIER_BILLING_UNAVAILABLE:
      'The supplier cost limit is enabled but its snapshot is missing, failed or stale. Sync and review Budget and expenses. Previously accepted tasks continue.',
    BILLING_CONFLICT:
      'Sync configuration changed. Reload before retrying; your input was retained.',
    BILLING_SCHEDULE_CONFLICT: 'The plan changed. Reload and review it; your input was retained.',
    BILLING_SCHEDULE_INTERVAL:
      'An enabled sync interval must not exceed half the allowed snapshot interval.',
    BILLING_INTERRUPTED:
      'Sync was interrupted; partial costs were not adopted. Review the recovery plan or sync manually.',
    BILLING_BUSY: 'This configuration is being synchronized. Refresh the status later.',
    BILLING_NOT_CONFIGURED:
      'Check server Admin credentials and organization against the saved sync scope.',
    BILLING_AUTH:
      'Admin credentials were rejected. Check the organization and cost-read permissions.',
    BILLING_RATE_LIMIT: 'The supplier rate-limited this request. Retry later.',
    BILLING_REMOTE:
      'The supplier cost endpoint did not respond successfully; partial results were not adopted.',
    BILLING_NETWORK:
      'The cost endpoint connection failed or timed out; partial results were not adopted.',
    BILLING_RESPONSE:
      'Amount, project scope or pagination validation failed; partial results were not adopted.',
    BILLING_PERIOD: 'The query period is empty or exceeds 366 days. Check the UTC start date.',
    BILLING_NOT_FOUND: 'This sync record was not found in the current research.',
    STUDY_BUDGET_REACHED:
      'Registered costs reached this research’s budget limit; new covered tasks are no longer accepted. Started tasks do not stop automatically. Review Budget and expenses in the research workspace. This limit does not represent complete costs or a provider balance.',
    BUDGET_CONFLICT:
      'The budget changed in another window. Your input was retained; reload and review the current budget.',
    BUDGET_CURRENCY_LOCKED:
      'The research currency is fixed; currencies cannot be changed or mixed.',
    EXPENSE_CURRENCY: 'Save the research currency first and use it for expense entries.',
    EXPENSE_CONFLICT:
      'This request conflicts with an existing expense or void record. Review the current record before retrying.',
    EXPENSE_DUPLICATE:
      'This source reference is already registered. Review the record to avoid counting costs twice.',
    EXPENSE_NOT_FOUND: 'This research has no matching expense record. Refresh and review.',
    PROMPT_DESIGN_CONFLICT:
      'The baseline or prompt changed. Your input is retained; reload and review before creating the variant.',
    STUDY_NOT_FOUND: 'Research not found. Return to the research studio and select again.',
    STUDY_RUN_CONFLICT:
      'This run belongs to another research. It cannot be reassigned or paired across research.',
    DRAFT_CONFLICT:
      'Another window saved a newer draft. Your input is retained; export a copy, reload and merge.',
    DRAFT_NOT_FOUND: 'The experiment or comparison no longer exists. Export your current input.',
    DRAFT_INVALID: 'The draft does not match the current format. Check it and retry.',
    RESEARCH_CONFLICT:
      'A newer conclusion exists. Refresh and review revisions, then explicitly adopt the publication basis.',
    RESEARCH_TRACE_MISSING: 'The invocation no longer exists.',
    RESEARCH_TRACE_INVALID:
      'Invocation content or game provenance cannot be verified for citation.',
    RESEARCH_TRACE_SCOPE:
      'The invocation falls outside this comparison’s frozen cohort, player identity or time cutoff.',
    RESEARCH_TRACE_CHANGED:
      'The invocation changed after selection. Return to the current record, select a comparison and review again. The existing draft is retained.',
    RESEARCH_TRACE_LIMIT:
      'Each revision accepts up to five distinct invocations, at most 2 MiB each and 8 MiB combined. Oversized content is rejected, not truncated.',
    RESEARCH_PUZZLE_SOURCE:
      'Selection provenance or a position source is missing, changed or unverifiable, or the test exceeds 200 positions. It cannot be formally cited but remains independently readable.',
    RESEARCH_PUZZLE_SCOPE:
      'The source falls outside the frozen jointly valid cohort, or its decision or evaluation settings have changed. Review the source and select again.',
    RESEARCH_PUZZLE_CHANGED:
      'The test file changed after preview. Remove the old reference, review it again and re-add it. Your draft is retained.',
    RESEARCH_PUZZLE_LIMIT:
      'Each revision supports up to five distinct test citations with at most 8 MiB of frozen content. Reduce citations and retry.',
    PUZZLE_RESULT_NOT_FOUND: 'The test record no longer exists. Select again.',
    PUZZLE_RESULT_INVALID: 'The test record is invalid or unreadable and cannot be formally cited.',
    PUZZLE_RESULT_UNSUPPORTED:
      'This record uses an unsupported metric version and cannot be cited using current definitions.',
    operationFailed: 'Operation failed',
    deleted: 'Deleted',
    deleteFailed: 'Failed to delete',
    createFailed: 'Failed to create',
    NETWORK_ERROR: 'Network error. Try again later.',
    AI_RATE_LIMIT_EXCEEDED: 'AI provider rate-limited. Try again later.',
    AI_TIMEOUT: 'AI provider timed out. Try again later.',
    AI_PROVIDER_UNAVAILABLE: 'AI provider unavailable. Try again later.',
    AI_PROVIDER_ERROR: 'AI provider call failed. Try again later.',
    DEPLOY_LLAMA_CPP_MISSING:
      'LLAMA_CPP_DIR is missing or invalid. Set it in .env to a llama.cpp checkout with convert_hf_to_gguf.py.',
    DEPLOY_GGUF_FAILED: 'GGUF conversion failed. Check server logs for details.',
    DEPLOY_OLLAMA_FAILED: 'Failed to push to Ollama. Ensure Ollama is installed and on PATH.',
    DEPLOY_MERGE_FAILED: 'LoRA merge failed. Check server logs for details.',
    DEPLOY_NOT_LORA: 'This task is not a usable LoRA adapter directory. Finish training first.',
    TRAINING_GUARD_FAILED: 'Training environment check failed.',
    PROVIDER_NOT_CONFIGURED:
      'A model seat needs attention. Check the configuration file in Settings and the selected model name. For Ollama, start the service and install the requested tag.',
    EXPERIMENT_VALIDATION_FAILED:
      'Experiment validation failed. Check player count, protocol, or control settings.',
    OLLAMA_UNREACHABLE: 'Cannot reach Ollama at {url}. Ensure Ollama is running and reachable.',
    OLLAMA_TIMEOUT: 'Timed out connecting to Ollama ({url}). Ensure the service is running.',
    OLLAMA_TAG_NOT_FOUND:
      'Model tag "{tag}" not found in Ollama. Push to Ollama or run ollama create first.',
  },
  action: {
    PASS: 'Pass',
    SINGLE: 'Single',
    PAIR: 'Pair',
    TRIPLE: 'Triple',
    TRIPLE_ONE: 'Triple + 1',
    TRIPLE_TWO: 'Triple + pair',
    BOMB: 'Bomb',
    ROCKET: 'Rocket',
    CHAIN: 'Straight',
    CHAIN_PAIR: 'Pair chain',
    AIRPLANE: 'Airplane',
    AIRPLANE_SOLO: 'Airplane + singles',
    AIRPLANE_PAIR: 'Airplane + pairs',
    FOUR_TWO: 'Four + 2',
    BID: 'Bid',
    BID_PASS: 'Pass bid',
    UNKNOWN: 'Unknown',
  },
  card: {
    blackJoker: 'Black joker',
    redJoker: 'Red joker',
    shortBlack: 'B',
    shortRed: 'R',
  },
}
