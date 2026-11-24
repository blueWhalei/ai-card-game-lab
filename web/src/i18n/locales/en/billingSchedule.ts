export default {
  title: 'Periodic cost sync',
  scope:
    'Off by default. Explicitly enable a plan to read costs for the selected organization, project and UTC interval. Runs only while the backend service is running, not while the computer is asleep or the service is stopped.',
  method: 'Timing, failure handling and budget limits',
  behavior:
    'The service checks due plans every 30 seconds. Queues, sleep or network failures can delay execution. Success schedules the next check from completion time. Missed intervals are not replayed in a burst. Repeated queries replace snapshots without adding historical costs together.',
  retryPolicy:
    'Network, rate-limit or remote failures delay attempts by 2, 4, 8 times the interval and so on, up to 24 hours. Credential, query-period or response-validation errors suspend automatic attempts. After resolving the cause, a successful manual sync or an explicit plan save resumes scheduling. Changed cost configurations require plan confirmation.',
  budget:
    'Pausing a schedule does not disable budget limits or interrupt accepted tasks. Admission independently checks missing, failed or stale snapshots and reached limits. Periodic syncing does not expand cost coverage or guarantee spending stays within budget.',
  interval: 'Sync interval (minutes)',
  intervalHint:
    '15–720 minutes; when enabled, at most half the allowed snapshot interval to leave time for syncing. This is not the supplier posting interval or a completeness guarantee.',
  reason: 'Reason for setting or changing the plan',
  enable: 'Enable periodic sync',
  edit: 'Configure periodic sync',
  refresh: 'Refresh plan status',
  reload: 'Reload current plan',
  replaceInput: 'Reloading replaces unsaved plan input. Continue?',
  invalid: 'Enter an integer interval of 15–720 minutes and a change reason.',
  binding:
    'This plan binds to cost configuration version {n}. Enabling it requests a sync at the next scheduler check.',
  configFirst: 'First configure the supplier project, query start and cost limit above.',
  planSummary: 'Plan version {revision} · Cost configuration {config} · Every {minutes} minutes',
  linkedRevision: 'Linked plan version {n}',
  next: 'Next scheduled check: {time} (local time; execution may be delayed)',
  lastCheck:
    'Last scheduler check: {time} (local time; not proof of continuous operation or a successful sync)',
  failures:
    '{n} consecutive failures for the current plan. Interpret costs within their stated source scope.',
  workerDisabled:
    'Periodic scheduling is disabled on the server. Enabled budget limits still apply.',
  workerUnknown:
    'No recent scheduler check has been confirmed; the plan may be delayed. Check the service. Budget limits are not automatically lifted.',
  readAt:
    'Plan status read: {time} (local time). Refreshes every 30 seconds while visible and not editing. The server checks budgets again when admitting tasks.',
  loadFailed:
    'Could not read plan status. This does not mean the plan is disabled or costs are zero.',
  saved:
    'Plan saved. This did not change budget switches or cost amounts. Review subsequent sync results.',
  history: 'Plan changes (latest 10 versions)',
  enabled: 'Periodic sync enabled',
  paused: 'Periodic sync paused',
  states: {
    not_configured: 'Periodic sync has not been enabled',
    paused: 'Plan paused',
    scope_changed: 'Cost configuration changed; confirm the plan again',
    attention: 'Automatic sync needs attention; review the error',
    retry_wait: 'Sync failed; waiting for a delayed retry',
    due: 'Plan is due; awaiting scheduler check',
    scheduled: 'Next sync check scheduled',
    running: 'Sync in progress',
    recovering: 'Previous sync did not finish; awaiting recovery check',
  },
}
