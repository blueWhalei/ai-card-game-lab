export default {
  pairedBoard: {
    title: 'Reconstructed board',
    before: 'Before the action at this step; the recorded action appears below.',
    basis:
      'Rebuilt from the frozen deal seed and continuous actions with current engine version {version}. Record cutoff {cutoff}; read at {read}.',
    showAll: 'Show reconstructed hands for the researcher',
    actorScope: 'Acting-player view: own hand, other seats’ remaining counts and public cards.',
    allScope:
      'Researcher view includes other seats’ reconstructed hands. These were not visible to the acting player.',
    limits:
      'Reconstruction depends on the current engine and retained records; it is not an original board snapshot or the complete model input. Citations preserve decision fields, not this reconstructed display. Equal step numbers after divergence do not support direct attribution or add independent games.',
    unsupported:
      'The current engine version differs from the frozen conditions. No board was reconstructed; retained decision records remain available below.',
    unverified:
      'This step or an earlier record is missing, inconsistent or unverifiable. No board was reconstructed, and later records do not fill the gap.',
  },
  evidenceEntry: {
    open: 'Cite in a comparison draft',
    title: 'Choose a comparison for this citation',
    scope:
      'Only saved comparisons whose frozen jointly valid cohort contains this source game and whose cutoff includes this decision are listed. Review the source before explicitly adding it to the draft.',
    empty:
      'No eligible saved comparison was found. Create and save a comparison for this run first; the source must belong to its jointly valid cohort.',
    more: 'Find more comparisons',
    review: 'Review the decision to cite',
    previewScope:
      'This decision passed the comparison scope check. Opening this page does not add a citation; explicitly add it and write a note. Publication saves decision fields as they are then; this preview does not guarantee that the source will remain unchanged.',
  },
  paired: {
    formatDiagnostics:
      'Training-format usable {train} ({usable}/{n} records) · Parse success {parser} ({ok}/{parser_n} records with traces)',
    scenarioFilter: 'Locate scenarios within the jointly valid cohort',
    scenarioScope:
      'Reads currently retained decisions within frozen deal membership and the record cutoff. Navigation counts can change with source records. This is not a record-level archive or the denominator of the whole-run format diagnostics.',
    scopeTime: 'Frozen jointly valid deals: {n} · Record cutoff {cutoff} · Read at {time}',
    scenarioCounts:
      'A: decisions {left_n}, games {left_game_n}; B: decisions {right_n}, games {right_game_n}. Paired deals with records on either side: {pair_n}.',
    scenarioLimits:
      'Decisions within a game are correlated, not independent samples. Games can appear in multiple scenarios; group game counts cannot be added. Either side matching retains the pair; a nonmatching side does not imply weaker play. Duplicate or incomplete records may not be locatable, so record counts are not verified-step counts.',
    dealCounts: 'Decisions in the selected scope: A {left_n}, B {right_n}.',
    emptyScenario:
      'No records match this scenario in the frozen jointly valid cohort. This does not establish performance.',
    previousMatch: 'Previous matching step',
    nextMatch: 'Next matching step',
    matches: 'Locatable steps: {n}; the full timeline retains context.',
    matchesFilter: 'Matches scenario filter',
    contextOnly: 'Context only; does not match the selected scenario',
    positionMissing:
      'The selected scenario, deal or step is unavailable, or the address is invalid. No substitute record was selected. Please select again.',
    resetSelection: 'Select a game again',
    matrixScope:
      'This table preserves whole-run format diagnostics, not strategy ability or scenario win rates. Navigation below is limited to the frozen jointly valid cohort and uses different denominators.',
    inspectScenario: 'Inspect this scenario in the jointly valid cohort',
    title: 'Follow one deal as decisions diverge',
    deal: 'Paired game',
    dealN: 'Deal {n} of {total}',
    firstDifference: 'First action divergence',
    previous: 'Previous step',
    next: 'Next step',
    step: 'Step {n} / {total}',
    timeline: 'Shared decision timeline',
    empty: 'This snapshot has no jointly valid games to inspect yet.',
    ended: 'This side’s game has ended.',
    missing: 'This step has missing, duplicate or incomplete records and cannot be displayed.',
    scope:
      'This compares recorded contexts. After paths diverge, equal step numbers do not mean equal positions.',
    cite: 'Cite this pair',
    basis: 'Review alignment basis',
    method:
      'Checks frozen membership, seats, recorded phase, hand, opponent counts, previous action, presented menu and prior actions. Gaps prevent rejoining the verified path. This does not establish identical model inputs or better play.',
    seed: 'Frozen deal seed: {seed}',
    actionId: 'Recorded action ID',
    bidPoints: 'Bid {n}',
    citationLimit:
      'These decisions would exceed 30 citations. Remove some draft references first. No new references were added.',
    status: {
      same: 'Prior path and current records match',
      divergence: 'Prior records match; choices diverge here',
      different_path: 'Actions already diverged; these are different paths',
      different_context:
        'Recorded contexts differ; action choice alone cannot explain the difference',
      unverified: 'Insufficient records to confirm a shared path',
    },
    reason: {
      missing: 'At least one side has no record for this step or has ended.',
      duplicate: 'Multiple records exist for this step; none was chosen automatically.',
      invalid_context:
        'Context, menu or choice records cannot be confirmed; parsing fallback may be involved.',
    },
  },
}
