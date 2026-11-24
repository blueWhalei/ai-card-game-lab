import schedule from './billingSchedule'
import reconciliation from './billingReconciliation'
export default {
  billing: {
    schedule,
    reconciliation,
    triggers: { manual: 'Manual sync', scheduled: 'Scheduled sync' },
    validUntil:
      'Snapshot time limit, measured from the query end: {time} (local time). Failures or a reached cap may block tasks earlier. This time limit does not establish complete supplier reporting.',

    title: 'Supplier project costs',
    manualTitle: 'Manually registered expenses',
    scope:
      'Source: OpenAI Costs API, filtered by organization, project and UTC query interval. These are supplier cost records, not a final invoice or the complete cost of this research.',
    coverage:
      'A shared project may include other research. Costs outside the selected project, organization-level costs, other suppliers and unposted charges are outside this query scope. Supplier data may be delayed or revised. Cost lines are not research samples; no lines or a zero value do not prove zero actual spending.',
    accounting:
      'Each sync queries from the chosen start to the request time, inclusive of the start and exclusive of the end, up to 366 days. A new snapshot replaces the current one only after every page succeeds; historical snapshots are not added together. Returned USD amounts include negative adjustments. No currency conversion is applied.',
    limits:
      'This project cost limit independently controls new research tasks. It is not added to manual expenses or automatically allocated to research. An enabled limit rejects new tasks when reached, when no valid snapshot exists, after the latest sync fails or when the allowed sync interval expires. Either enabled limit can block admission. Future costs are not reserved and accepted tasks continue. Reporting delays and concurrent calls may exceed the limit; this is not a hard cap on actual spending.',
    setup:
      'Configure a separate OPENAI_BILLING_ADMIN_KEY and OPENAI_BILLING_ORGANIZATION_ID on the server and restart it. Model API keys cannot substitute for an Admin API key. Never enter credentials in the form below.',
    notReady:
      'Admin credentials are not configured, or the server organization differs from the saved scope. Costs are unknown, not zero.',
    organization: 'Organization',
    project: 'Supplier project ID',
    start: 'Accumulation start date (UTC)',
    periodHint:
      'The budget period does not reset automatically. Any configuration change creates a new version requiring a new sync. An enabled limit requires a start date within the preceding 365 days.',
    limit: 'Project cost limit (USD; blank means unset)',
    freshness: 'Maximum interval between syncs (hours, 1–24)',
    enforce: 'Use supplier project costs to limit new research tasks',
    configure: 'Configure supplier cost sync',
    sync: 'Sync costs now',
    syncing: 'Syncing costs…',
    syncHint:
      'Sync reads only the official cost endpoint, manually or through an explicitly enabled periodic plan. It does not make payments or run models.',
    synced: 'Sync completed for the displayed supplier query scope.',
    syncFailed:
      'Sync did not complete; partial results were not adopted. Earlier successful snapshots remain available but do not represent current costs.',
    loadFailed:
      'Could not read sync status. Costs and task admission cannot be determined from this failure.',
    amount: 'Latest successful snapshot amount (USD)',
    unknown: 'No successful snapshot',
    window: 'Query interval: {start} to {end} (UTC; end exclusive)',
    timestamp: 'Snapshot saved: {time}',
    readAt: 'Status read: {time}; the server checks again when admitting a task.',
    gateBlocked: 'The supplier cost limit blocks new controlled tasks.',
    gateOpen:
      'The supplier cost limit currently does not block tasks. The manual expense limit still applies independently. This does not establish complete cost coverage or spending below budget.',
    states: {
      unconfigured: 'Query scope not configured',
      missing: 'No successful snapshot for this configuration',
      failed: 'Latest sync failed',
      interrupted: 'Previous sync did not complete',
      stale: 'Allowed sync interval exceeded',
      reached: 'Snapshot amount reached the limit',
      below: 'Snapshot amount does not trigger the configured limit',
    },
    history: 'Sync history (latest 10 attempts)',
    configHistory: 'Sync and admission settings (latest 10 versions)',
    historyScope:
      'Only recent records are displayed. All configuration versions, sync attempts and successful source lines are retained in the local database.',
    status: {
      running: 'Syncing',
      succeeded: 'Succeeded',
      failed: 'Failed',
      interrupted: 'Interrupted',
    },
    evidence: 'View source lines',
    evidenceTitle: 'Supplier source lines',
    evidenceFailed:
      'Could not load source lines. Retry; this failure does not mean no lines exist.',
    empty:
      'The API returned no cost lines for this query. This does not imply zero actual spending.',
    noHistory: 'No sync has been requested.',
    lineItem: 'Cost item not provided',
    recordCount: '{n} cost lines returned; pagination does not change the snapshot amount.',
    closeEvidence: 'Close source lines',
    invalid:
      'Enter a valid project ID, UTC start date, interval of 1–24 hours and change reason. Amounts must be nonnegative decimals with up to 9 integer and 6 fractional digits; an enabled limit requires an amount.',
    reload: 'Reload sync configuration',
    errors: {
      BILLING_AUTH:
        'Admin credentials were rejected. Check the organization and cost-read permissions.',
      BILLING_RATE_LIMIT: 'The supplier rate-limited the request. Retry later.',
      BILLING_REMOTE: 'The supplier cost endpoint did not respond successfully.',
      BILLING_NETWORK: 'The cost endpoint connection failed or timed out.',
      BILLING_RESPONSE:
        'Amount, project scope or pagination validation failed. Partial results were not adopted.',
      BILLING_PERIOD: 'The query period is empty or exceeds 366 days. Check the UTC start date.',
      BILLING_INTERRUPTED: 'Sync was interrupted; partial costs were not saved.',
    },
  },
}
