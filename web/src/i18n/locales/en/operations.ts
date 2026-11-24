export default {
  operations: {
    title: 'Tasks and recorded usage',
    taskKind: 'View',
    kinds: { games: 'Game tasks', training: 'Training tasks', finance: 'Budget and expenses' },
    invalidKind: 'Invalid view. Select game tasks, training tasks, or budget and expenses.',
    trainingScope:
      'Only training tasks explicitly linked to runs in this research are listed, paginated by task without a time limit. Ownership does not mean all training data came from that run. Unlinked tasks remain on the training page. Active states include pending, exporting data and training; saved states do not prove a worker is still running.',
    trainingFilter: 'Filter training tasks by status',
    trainingFilters: { all: 'All tasks', active: 'Active tasks', attention: 'Abnormal records' },
    trainingReadAt:
      '{n} matching training tasks · Read at: {time}. States may change after this read.',
    trainingFailed:
      'Could not read training tasks in this scope. Retry; failure is not an empty result.',
    trainingEmpty: 'No training tasks match the current filter.',
    trainingRun: 'Owning run: {name}',
    trainingProgress: 'Saved execution progress',
    invalidProgress: 'Invalid progress field',
    invalidResult:
      'Result record is damaged or has an invalid format; it cannot support interpretation.',
    invalidConfig:
      'Training configuration is damaged or has an invalid format; training conditions cannot be verified from it.',
    trainingType: 'Training method (saved value)',
    trainingDetails: 'Source and interpretation',
    trainingSource: 'Task ID: {task} · Dataset ID: {dataset}',
    trainingLimit:
      'Progress is the last value saved by the training service, not remaining time, research completion or model quality. Completion does not establish policy improvement; evaluate with independent held-out data and predefined controls. Complete resource usage, costs and budget balances are not recorded here. Failed or interrupted training cannot resume losslessly from the same step; nothing retries automatically.',
    recordedError: 'Recorded error',
    noRecordedError: 'No readable error cause was saved; none is inferred.',
    openTraining: 'Open this training task',
    selectedTraining: 'Selected training task: {id} (read with the current filters)',
    trainingUnavailable:
      'The selected task no longer exists or is outside this scope. No other task was selected.',
    invalidTrainingQuery: 'Invalid training task location. Reopen from research tasks.',
    filter: 'Filter runs by game task status',
    filters: { all: 'All runs', active: 'With active tasks', attention: 'With abnormal records' },
    scope:
      'Current saved game statuses within this research, without a time limit. Awaiting start means a record exists, not that execution is queued. Completed games are not jointly valid samples. Filters examine the entire run; counts are not limited to this page. Switch to Training tasks for training records.',
    readAt:
      '{n} matching runs · Read at: {time}. Statuses may change after this read; refresh as needed.',
    gameCount:
      '{n} saved game records · Run target: {target} games (neither a budget cap nor a guarantee of valid samples)',
    noBid:
      '{n} completed records had no landlord bid. This is a subset of completed games, not an additional count.',
    states: {
      waiting: 'Awaiting start',
      running: 'Running',
      paused: 'Paused',
      finished: 'Completed',
      failed: 'Failed',
      interrupted: 'Interrupted',
      cancelled: 'Cancelled',
      unknown: 'Unknown status',
    },
    recovery:
      'Open the original run to inspect games and connection settings. Failed or interrupted tasks cannot resume losslessly from the same step. New games use the existing confirmation flow; nothing retries automatically. Unrecorded error causes are not inferred.',
    usage: 'Recorded token usage · {n} invocation records',
    usageScope:
      'Sums saved invocation metrics, including unfinished games. Child operations and action records are not added again. Each field accepts only nonnegative integers and is counted independently; missing totals are not derived. Records may omit requests, retries or provider usage and are not a complete bill. Tokens across models have no uniform cost meaning. Costs, budget balances and training usage are not recorded here. Invocation counts are not independent game samples.',
    fields: {
      prompt_tokens: 'Sum of input token fields',
      completion_tokens: 'Sum of output token fields',
      total_tokens: 'Sum of total token fields',
    },
    coverage:
      'Of {n} invocation records: {valid} valid fields, {missing} missing, {invalid} invalid.',
    missing: 'No valid value recorded',
    overflow: 'Total exceeds exact display range',
    failed:
      'Could not read tasks in this research. Retry; a failed read is not shown as an empty result.',
    invalidPosition: 'Invalid task filter or page. Select a filter above to reset the location.',
    empty: 'No runs match the current filter.',
    pageEmpty: 'No records on this page. Go back a page or select a filter again.',
    openRun: 'Open run and inspect tasks',
    back: 'Back to research task location',
  },
}
