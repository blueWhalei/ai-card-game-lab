export default {
  title: 'Supplier cost reconciliation',
  csv: {
    create: 'Reconcile from cost CSV',
    file: 'Project cost CSV file',
    project: 'Project ID for the cost export',
    instructions:
      'Choose a daily cost CSV for one organization, project and currency (UTF-8, up to 512 KiB and 10,000 data rows). Select the amount and UTC service date columns. Enter the scope from the export settings. All data rows are included, so use an export that covers the selected period.',
    columns: {
      amount: 'Cost amount column',
      date: 'UTC service date column',
      organization: 'Organization ID column',
      project: 'Project ID column',
      currency: 'Currency column',
    },
    declared: 'Use the scope entered by the user',
    required:
      'Choose a file, amount column and service date column. Enter the source, organization, project, UTC period and scope description.',
    invalidFile: 'Could not read the cost CSV. Choose a UTF-8 CSV file up to 512 KiB.',
    evidence: 'CSV source details · {name}',
    dataRows:
      'CSV data rows included: {count}. Earliest and latest service dates: {first} and {last} (UTC).',
    retention:
      'The record saves the column mapping and SHA-256 digest. Keep the original file. Unmapped scope fields use the values entered by the user. The date span and digest cannot verify cost coverage, file origin or settlement.',
  },
  scope:
    'Compare a successful cost snapshot with a project cost CSV or manually entered evidence. Keep the original export or document. Reconciliation compares amounts within the selected scope and leaves snapshot and registered expense totals unchanged.',
  method: 'Comparison basis and limitations',
  methodText:
    'Compare project costs only for the same organization, project, currency and completed UTC period. Difference = API period amount − evidence amount. Preserve negative adjustments and decimal precision; do not prorate time buckets or silently ignore small differences. Invoice totals and payments are not directly comparable with project costs.',
  limitation:
    'Equal amounts establish numerical agreement only within the selected scope. They do not verify authenticity, research attribution, complete billing or settlement. Other projects, organization-level costs, other suppliers, unposted amounts and settlement adjustments may remain outside coverage.',
  create: 'Register reconciliation evidence',
  noSnapshot:
    'Obtain a successful cost snapshot first. Reconciliation reads existing snapshots; it does not sync costs or run models.',
  sourceSnapshot: 'Successful snapshot to compare',
  snapshotChoice: 'Configuration {revision} · {project} · Query ends {time} UTC',
  sourceType: 'Evidence type',
  types: {
    cost_export: 'Project cost export',
    invoice_project_subtotal: 'Project cost subtotal on invoice',
    invoice_total: 'Invoice total',
    payment_receipt: 'Payment receipt',
  },
  reference: 'Document reference or location description',
  organization: 'Organization ID on the evidence',
  project: 'Project ID on the evidence (blank if not separated)',
  currency: 'Evidence currency',
  amount: 'Evidence amount',
  start: 'Service period start (UTC, inclusive)',
  end: 'Service period end (UTC, exclusive)',
  dates:
    'Use completed UTC days, at most 366 days. For example, November 1 to December 1 covers all of November. Use cost/service dates, not payment or invoice issue dates.',
  note: 'Cost items, filters and excluded scope',
  noteHint:
    'Describe whether the amount contains only project costs and how taxes, credits, top-ups or organization-level costs are treated. Do not enter secret keys. A document reference does not verify authenticity.',
  preview: 'Preview reconciliation',
  save: 'Save this reconciliation record',
  previewOnly:
    'Preview only: not saved and does not trigger a review hold. Preview again after changing the evidence.',
  saved:
    'Reconciliation action saved. Original amounts and other budget checks remain independent; review the current admission status.',
  invalid:
    'Enter a source, organization, amount, UTC period and scope description. Use decimal text with at most 12 integer and 18 fractional digits; negative adjustments are allowed.',
  result: {
    matched: 'Amounts agree within the selected scope',
    difference: 'Amounts differ within the selected scope',
    not_comparable: 'Evidence and snapshot are not directly comparable',
  },
  reasons: {
    basis: 'An invoice total or payment is not a comparable project cost subtotal.',
    organization: 'Organization scopes differ.',
    project: 'Project is unspecified or differs from the snapshot.',
    currency: 'Currencies differ; no exchange conversion is applied.',
    period: 'The snapshot query does not cover the selected service period.',
    bucket_boundary: 'A cost bucket crosses the period boundary; it is not prorated.',
  },
  interfaceAmount: 'Amount returned by the API for the selected period (USD)',
  difference: 'API period amount − evidence amount (USD)',
  unknown: 'Not computable',
  count: '{n} API lines included; line counts are not research sample sizes.',
  empty:
    'No cost lines were returned for this period. A numerical zero does not establish zero actual spending.',
  snapshot: 'Snapshot configuration {revision} · Organization {organization} · Project {project}',
  query: 'Original snapshot query: {start} to {end} (UTC, end exclusive)',
  sourceSaved: 'Snapshot saved: {time} (local time)',
  evidence: 'View the selected snapshot lines',
  policyTitle: 'Task limits for pending reconciliations',
  policyEnable:
    'Block new controlled tasks in this research while reconciliation records await review',
  policyEdit: 'Configure reconciliation task limits',
  policyHint:
    'Off by default. When enabled, any unresolved difference or incomparable record, including older configurations, blocks new controlled tasks. Pausing sync, a new snapshot or changed cost settings does not dispose of differences. Existing amount and freshness checks remain independent.',
  pending:
    'Records awaiting review: {n}, across all pages and cost configuration versions in this research.',
  blocked: 'Pending reconciliation records block new controlled tasks.',
  notBlocked:
    'Reconciliation does not currently block tasks. This does not establish complete costs or that other budget checks pass.',
  policyHistory: 'Reconciliation policy changes (latest 10 versions)',
  history: 'Saved reconciliation records',
  noRecords: 'No reconciliation records yet.',
  recordTime: 'Registered: {time} (local time) · Record ID: {id}',
  details: 'View evidence and calculation scope',
  review: {
    pending: 'Awaiting review',
    resolve: 'Review disposition recorded',
    reopen: 'Reopened for review',
    void: 'Voided',
    matched: 'No difference requiring review',
  },
  actions: {
    resolve: 'Record review disposition',
    reopen: 'Reopen for review',
    void: 'Void this record',
  },
  reviewHint:
    'Document the evidence, cause and reason for disposition. Disposition ends this record’s review hold without changing original amounts or establishing complete billing. Missing, stale, failed or over-limit cost snapshots still block tasks. Voiding retains the record and history; register a new record to correct inputs.',
  reviewReason: 'Review or void reason and supporting evidence',
  reviewHistory: 'View review history',
  noReviews: 'No review events yet.',
  loadFailed:
    'Could not read reconciliation status. This does not establish no differences or that task limits were removed.',
  readAt:
    'Reconciliation status read: {time} (local time); the server checks again when admitting tasks.',
  refresh: 'Refresh reconciliation status',
  leave: 'The reconciliation form is not saved. Discard the input and leave?',
  reload: 'Discard input and load current status',
}
