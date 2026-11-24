export default {
  traceCitation: {
    title: 'Invocation citations',
    citation: 'Invocation citation {n}',
    identity: 'Invocation ID',
    origin: 'Source run / game / deal seed',
    position: 'Recorded player / original round field',
    model: 'Recorded model / prompt version',
    created: 'Invocation timestamp',
    cutoff: 'Comparison cutoff',
    latency: 'Response latency (ms)',
    parser: 'Parse status',
    input: 'Saved input',
    output: 'Saved output',
    metrics: 'Saved metric fields',
    spans: 'Saved child operations',
    hash: 'Normalized JSON content fingerprint:',
    readAt: 'Evidence read at: {at}',
    scope:
      'These are saved invocation records and may omit parts of the provider request or response. Model output is recorded text, not proof of internal reasoning or decision quality. Child operations are not independent invocation samples. Calls from one game are not independent games and do not increase the comparison’s effective sample size.',
    targetScope:
      'Only comparisons whose frozen jointly valid cohort contains this game with matching player/deal identity and a cutoff covering the record are listed. Review the content next; only explicit inclusion changes the draft.',
    noTargets:
      'No comparisons match this source. Save a valid comparison containing this game first; scope is not widened to the entire run.',
    review: 'Review invocation citation',
    previewScope:
      'This is the currently saved content. The cutoff constrains record timestamps, not when the content was frozen. Publication rechecks its fingerprint.',
    invalid: 'Invalid invocation position or preview identity. No other record was substituted.',
    changed:
      'The invocation changed after selection. Return to the current record, select a comparison and review again. The existing draft is retained.',
    limit:
      'Each revision accepts up to five distinct invocations, at most 2 MiB each and 8 MiB combined. Oversized content is rejected, not truncated.',
    current: 'Inspect current invocation',
    update: 'Use current content and update citation',
    include: 'Cite this invocation record',
    currentStatus: 'Current source status:',
    frozen:
      'The body and source identity below are copies checked at publication and remain unchanged. A fingerprint checks consistency, not authenticity or complete reproducibility.',
    reportScope:
      'Invocation citations support inspection of saved inputs, outputs and runtime diagnostics. These cases were selected after observation and cannot alone establish population effects or causality.',
    draftScope:
      'Invocation references retain the reviewed fingerprint. If a source changes, open its current record, select a comparison and explicitly update after review; the note is retained. Publication freezes the body without another model call.',
    savedCount:
      'This revision contains {n} frozen invocation citations. The readable report includes their content, source status and return links.',
    selectionFailed:
      'The requested invocation is missing, outside the current filters or unreadable. No other record was substituted. Retry or clear the selection.',
    clearSelection: 'Clear record selection',
    status: {
      available: 'Current content matches publication',
      changed: 'Current content changed; the report retains its published copy',
      missing: 'Current invocation is missing; the published copy remains',
      identity_mismatch: 'Current source identity has changed',
      invalid: 'Current content or game provenance cannot be verified',
      unknown: 'Current source has not been checked',
    },
  },
}
