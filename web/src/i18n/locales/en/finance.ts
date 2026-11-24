export default {
  finance: {
    scope:
      'Costs are entered by the user from statements, payment receipts or allocation records; the system does not verify them. Token usage is recorded separately and is not converted into a complete bill.',
    method: 'Sources, accounting scope and limits',
    accounting:
      'The total includes all non-void expense records in this research, without a date filter, independently of pagination. Amounts are added exactly in their original currency with up to six decimal places; no exchange conversion is applied. Missing, omitted and unsettled costs are excluded; no records does not mean actual costs are zero. Entry counts are not independent research samples.',
    limits:
      'Task limits use registered costs only: new covered tasks are rejected once the total reaches or exceeds the budget. Future costs are not reserved and provider balances are not read. Delays, omissions and concurrent tasks can allow actual spending to exceed the budget. This is not a hard cap on actual spending.',
    gateScope:
      'Covers game collection, start and resume, and linked training task creation in this research. Accepted tasks and in-flight calls continue. Trial games, unlinked training, decision previews and other research are outside this scope.',
    readAt: 'Read at: {time}. Costs and budgets may change after this read.',
    budget: 'Budget limit',
    recorded: 'Registered cost total',
    difference: 'Budget minus registered costs',
    notSet: 'Not set',
    noAmount: 'No costs registered',
    unavailable: 'Difference unavailable',
    countsTitle: 'Registered entries',
    counts: '{active} included in total · {voided} voided',
    blocked: 'Registered costs reached the budget limit: new covered tasks will be rejected.',
    below:
      'Registered costs have not reached the limit; this does not establish that actual costs are below budget.',
    disabled: 'Task limits disabled',
    enforced: 'Task limits enabled',
    editBudget: 'Set budget',
    addExpense: 'Register expense',
    setCurrencyFirst:
      'Set the research currency first. The budget amount may remain blank; the saved currency cannot change.',
    forms: {
      budget: 'Set research budget',
      expense: 'Register an expense',
      void: 'Void expense record',
    },
    explicitSave:
      'An explicit save is required. Nothing submits, pays or starts a task automatically.',
    currency: 'Currency (fixed after saving)',
    limitInput: 'Budget amount (blank means unset; zero is a valid limit)',
    enforce: 'Limit new tasks using registered costs',
    changeReason: 'Reason for setting or changing the budget',
    amount: 'Expense amount',
    incurredOn: 'Date incurred',
    sourceType: 'Source type',
    sources: {
      provider_statement: 'Provider statement',
      payment_receipt: 'Payment receipt',
      manual_allocation: 'Manual allocation',
    },
    sourceReference: 'Source reference (include provider and line identifier)',
    referenceHint:
      'References must be unique within the research. Check whether a statement and receipt describe the same cost to avoid registering it twice under different references. Explain allocation calculations and coverage.',
    scopeDescription: 'Cost attribution, coverage and allocation basis',
    voidHint:
      'The original record and reason remain, but the amount leaves the total. This does not request a provider refund. Correct amounts require a new entry with a distinguishable reference.',
    voidReason: 'Reason for voiding',
    void: 'Void',
    confirmVoid: 'Confirm void',
    confirmSave: 'Confirm save',
    saving: 'Saving…',
    discard: 'Discard unsaved input',
    saved: 'Saved.',
    saveFailed: 'Save failed; your input was retained.',
    loadFailed:
      'Cannot read this research’s budget and costs. A read failure does not mean there are no costs.',
    invalidAmount:
      'Use a nonnegative decimal with up to nine integer and six fractional digits. Enabling task limits requires a budget amount.',
    required: 'Complete the required source, date or reason fields.',
    leave: 'The budget or expense form has not been saved. Discard input and leave?',
    reloadBudget: 'Reload current budget',
    replaceInput: 'Reloading will replace your unsaved budget input. Continue?',
    history: 'Budget changes ({n} versions)',
    historyLimit: 'Showing the latest 20 versions; all history remains in the local database.',
    version: 'Version {n}',
    records: 'Expense records',
    empty: 'No expenses have been registered.',
    registeredAt: 'Registered: {time} · Record ID: {id}',
    voided: 'Voided ({time}): {reason}',
  },
}
