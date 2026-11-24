export default {
  puzzleBatch: {
    title: 'Basis for batch position selection',
    heuristic: 'heuristic policy',
    publishedChecks:
      'Sources checked at extraction: {checked}/{selected}. Every source and its frozen cohort membership were checked at publication. See this citation’s status section for current source status.',
    evaluation:
      'Sampled hidden states: {worlds}; simulations per action per state: {repeats}; up to {candidates} evaluated actions per position and {steps} continuation steps; seed {seed}; effective continuation: {policy}.',
    counts:
      'Completed games in scope: {games}; candidates with estimates: {candidates}, meeting the threshold: {eligible}; selected positions: {selected}, source games: {selectedGames}.',
    rule: 'Estimated payoff range threshold ≥ {threshold}, selected in descending order; ties retain candidate order. Up to {perGame} per game and {total} in total.',
    estimates:
      'Payoffs were simulated again during batch extraction and may differ from the original decision estimates. These are the evaluation conditions saved for this extraction.',
    checks:
      'Sources checked at extraction: {checked}/{selected}. Formal citation also checks current sources and the frozen jointly valid cohort; any ineligible position rejects the entire citation.',
    limits:
      'The range is the highest minus lowest estimated payoff among evaluated actions, not a difficulty or ability score. Candidate counts cover positions with successfully generated estimates, not all decisions. Missing records, evaluation failures, thresholds and caps can introduce selection bias. This is not random sampling. Multiple positions from one game and repeated perturbations are not independent games and do not establish population performance.',
    sourceStates: 'Current source decision status ({n} records)',
  },
  puzzleCitation: {
    targetScope:
      'Only comparisons containing every test source in the frozen jointly valid cohort, with every source decision at or before the cutoff, are listed. The test and current sources have been checked; select a comparison, review the preview, then explicitly add the citation.',
    noTargets:
      'No eligible comparisons on this page; continue if more pages are available. If none qualify, create and save a comparison for the source runs first.',
    review: 'Review the position test to cite',
    reviewScope:
      'Opening this preview does not add a citation. Review the test conditions, selection basis and results before adding it to the draft. Neither adding nor publishing reruns the test.',
    changedPreview:
      'The test content differs from the version you just reviewed. Return to the result and reload it before citing.',
    backToResult: 'Return to the source test result',
    limit:
      'A revision can cite up to five position tests. Remove a citation from the draft first; nothing was added.',
    title: 'Cited position tests',
    choose: 'Select a saved test',
    refresh: 'Refresh tests',
    pack: 'Select a related test pack',
    noPacks:
      'No test packs with recorded source checks from these runs. Create a decision test or extract a new batch first.',
    invalid: 'The returned test identity does not match the selection.',
    scope:
      'Cite only tests whose every source is verifiable within the frozen jointly valid cohort. Up to 200 positions per test and five tests per revision. Historical records lacking selection or source provenance remain independently readable. Adding a reference does not publish or execute a test.',
    verified:
      'Source scope and saved content checked. Publication checks again; changes reject publication and preserve the draft.',
    add: 'Add test citation',
    preview: 'Read test conditions and results',
    savedCount:
      'This revision cites {n} position tests. Read their complete content in the report.',
    citation: 'Position-test citation {n}',
    reportScope:
      'These tests describe behavior in selected positions and are exploratory diagnostics chosen after observation. They do not add valid games or pairs to this comparison, replace independent validation, or establish general superiority.',
    currentRecord: 'Current test-file status',
    currentPack: 'Pack referenced by the current file',
    current: 'Read the current test file',
    frozen:
      'The following content was frozen at publication. Later file or source changes do not overwrite this citation.',
    verifiedAt:
      'Source checked for publication at: {at}. Pack content, source decision and frozen comparison scope matched then. See above for current status.',
    sources: 'Source decision fields saved at publication',
    testLimits:
      'This citation retains the test record and describes only the selected positions, baseline, seed and saved evaluation conditions. The highest estimated-value action is not ground truth; unscored choices are not errors. Repeated perturbations do not add independent games or establish general strategy superiority or model robustness. Exports contain results and source summaries, not the complete historical runtime.',
    status: {
      available: 'Matches the published content',
      changed: 'Changed; published content retained below',
      missing: 'File missing; published content retained',
      invalid: 'Invalid or unreadable file; published content retained',
      unsupported: 'Current metric version unsupported; published content retained',
      unknown: 'Not checked',
    },
  },
  report: {
    title: 'Research report',
    open: 'Read report',
    html: 'Export readable HTML',
    json: 'Export data JSON',
    back: 'Return to report evidence',
    failed: 'Could not load this conclusion revision.',
    basis:
      'This report reads a saved comparison and a published conclusion revision. It excludes unpublished drafts and games added later.',
    version: 'Conclusion revision',
    cutoff: 'Statistics cutoff',
    published: 'Conclusion saved at',
    checked: 'Source status checked at',
    metricVersion: 'Metric calculation version',
    missing: 'Not recorded',
    question: 'Question and hypothesis',
    noQuestion:
      'No hypothesis was saved in this snapshot. The report does not fill it from current study or run notes.',
    questionScope:
      'Run hypotheses are shown as saved with the comparison. This record alone does not establish that they preceded observation of the results.',
    conditions: 'Run conditions',
    run: 'Run',
    engine: 'Game and engine version',
    player: 'Seat and player',
    policy: 'Policy and model',
    sampling: 'Model sampling settings',
    prompts: 'Frozen prompts',
    protocol: 'Frozen conditions and differences',
    controlledScope:
      'Condition review checks recorded protocols and declared changes. It does not establish randomized assignment or causal identification.',
    sample: 'Sample and statistical results',
    unit: 'The paired analysis unit is one valid game pair sharing a deal seed across the two runs. Each pair counts once; decisions and teammates within a game are not additional independent samples.',
    pairedN: 'Valid game pairs',
    planned: 'Planned shared deals',
    excluded: 'Excluded game pairs',
    purpose: 'Deal purpose',
    metric: 'Comparison metric',
    direction: 'Difference direction',
    difference: 'Paired win-rate difference (percentage points)',
    interval: 'Conservative 95% confidence interval (percentage points)',
    pValue: 'Two-sided exact McNemar p-value',
    method:
      'The four paired outcome counts use the same jointly valid sample. The difference interval uses Clopper–Pearson with Bonferroni adjustment. A p-value is not the probability that the null hypothesis is true.',
    ciScope:
      'An interval crossing zero permits differences in either direction; it does not establish equivalence. Coverage depends on sampling design and assumptions; it is not a 95% probability assigned to the parameter for this particular interval.',
    methodTitle: 'Statistical methods and assumptions',
    methodDetail:
      'Difference = (B-only wins − A-only wins) / valid pairs. Assuming independent, identically distributed pairs, construct 97.5% Clopper–Pearson intervals for the B-only and A-only probabilities, each using all valid pairs as the denominator. Combine them as [B lower − A upper, B upper − A lower]. The Bonferroni inequality gives at least 95% coverage for this conservative difference interval. The two-sided exact McNemar test uses only discordant pairs; the test and interval are not inverses. Selected deals or dependence across games limit this sampling interpretation.',
    noPairs:
      'No valid two-run paired estimate is available. Missing values do not imply a zero difference or no effect.',
    unsupported:
      'This snapshot lacks the current metric version or a supported method identifier. Author records and evidence are retained, but values are not interpreted under current definitions; raw fields remain available in JSON.',
    exclusionDetail: 'Sample inclusion and exclusion details',
    seed: 'Deal seed',
    reason: 'Exclusion reason',
    notShared: 'Valid but outside the shared cohort',
    missingSeed: 'Games without a valid seed',
    unplanned: 'Unplanned games',
    membership: 'Jointly valid deals and games',
    author: 'Author record',
    authorScope:
      'The observations, interpretation and limitations below are saved author statements. This report does not automatically validate causal or generalization claims in them.',
    evidence: 'Cited evidence',
    evidenceScope:
      '{n} decision records are cited in this revision. They illustrate selected records, are not a random sample, and do not replace cohort statistics. Uncited matched games remain part of the cohort.',
    citation: 'Evidence {n}',
    source: 'Data provenance',
    turn: 'Recorded turn (zero-based)',
    note: 'Author citation note',
    state: 'Decision context at publication',
    hand: 'Own hand',
    opponents: 'Opponent card counts',
    lastAction: 'Previous action',
    action: 'Chosen action',
    legal: 'Recorded legal-action menu',
    outcome: 'Final team outcome for this seat',
    gap: 'Estimated expected payoff gap',
    evaluation: 'Payoff estimation conditions',
    evalScope:
      'The gap subtracts the selected action’s simulated mean payoff from the largest evaluated candidate mean. Zero includes ties and single-candidate cases; missing means unevaluated. Dou Dizhu uses team win/loss payoffs of 0/1, excluding scoring multipliers. This does not establish the truly optimal action.',
    candidates: 'Evaluated candidates',
    legalCount: 'Legal actions',
    worlds: 'Sampled hidden deals',
    rollouts: 'Rollouts per deal and action',
    opponent: 'Effective opponent continuation policy',
    selfProxy: 'Own continuation proxy',
    steps: 'Simulation step limit',
    randomSeed: 'Evaluation random seed',
    stateScope:
      'This is the saved decision record, not the full hidden state or complete model input. It does not directly explain the model’s internal reasoning.',
    current: 'Inspect current source decision',
    comparison: 'Inspect this position in the comparison',
    currentScope:
      'Navigation opens the current source record. The content below always retains this revision’s frozen evidence.',
    unknownStatus: 'Source status is unknown; frozen evidence remains readable.',
    limits: 'Interpretation and reproduction limits',
    exploration:
      'Development deals and mixed-purpose analyses are exploratory. Repeated inspection, selective examples or prompt tuning on the same data do not replace independent validation.',
    holdout:
      'A holdout label records the reserved purpose; it does not alone prove the data were never used for tuning. Excluding incomplete or abnormal games may introduce selection bias and must be interpreted with the exclusion details.',
    multiplicity:
      'This report does not adjust the overall error rate for repeated looks, multiple run comparisons or post hoc selection. Sample-size warnings are not estimates of statistical power.',
    reproduction:
      'HTML and JSON contain the saved comparison, conclusion and selected evidence. They exclude complete game archives, model weights, runtime dependencies and provider services, so they cannot guarantee stepwise reproduction. HTML section links work offline; source-record navigation requires the same local workspace.',
    printHint: 'Open the HTML offline in a browser to read, print or save it as PDF.',
  },
}
