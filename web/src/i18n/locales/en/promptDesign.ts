export default {
  promptDesign: {
    phases: { playing: 'Playing', bidding: 'Bidding' },
    title: 'Design Prompt A/B',
    followup: 'Design a follow-up variant',
    followupContinue: 'Check baseline and continue',
    followupScope:
      'This design starts from a saved conclusion. Reusing development deals is exploratory, not preregistration or independent validation. Define a new hypothesis and primary outcome. After saving the design, reserve a holdout pair from its run conditions.',
    followupFailed:
      'Could not check the baseline or source conclusion. The run or report may no longer exist. Select another baseline or retry.',
    sourceConclusion: 'Source conclusion report',
    sourceText: 'Read source observations, interpretation and limitations',
    sourceBaseline:
      'This baseline comes from the selected report. Return to that report to choose another; current conditions must match its frozen record.',
    intro:
      'Keep the conditions fixed, change one phase’s prompt, and examine how decisions change.',
    steps: 'Design steps',
    step1: 'Choose baseline',
    step2: 'Define change',
    step3: 'Review conditions',
    baseline: 'Which run is A?',
    choose: 'Select an option',
    baselineHint:
      'Choose a fixed-deal run with a model player in this research. A does not need to have started; B inherits its frozen conditions.',
    newBaseline: 'Design a baseline first (benchmark mode and model players)',
    hypothesis: 'What effect do you expect from this change?',
    name: 'Name for B',
    phase: 'Phase to change',
    version: 'Prompt version for B',
    affected: 'Seats using the changed phase prompt: {seats}',
    observe: 'Which win rate answers the research question?',
    tableMetric: 'Table landlord win rate',
    seatMetric: 'Team win rate for {seat}',
    sharedChange:
      'Several seats change prompts together. The selected player’s team outcome is measured under that shared change.',
    contrast: 'B − A on valid shared deals',
    managePrompts: 'Manage prompt versions',
    review: 'The design you are about to test',
    change: 'Only change',
    plan: 'Shared deal plan',
    planValue: 'Development deals · {n} games per run, with identical seeds and seat order',
    metric: 'Primary observation',
    fixed: 'Held constant',
    fixedValue:
      'Models and parameters, seats, other prompts, reasoning budget, evaluator, and no cross-game memory.',
    protocol: 'Inspect frozen conditions',
    readiness: 'Before you start',
    preflightHint:
      'These checks inspect local configuration. Passing does not verify remote connectivity, balance, or model responses. Checks run again at start.',
    settings: 'Open settings',
    noCall:
      'Creating B only saves the design. Start A and B separately from their run pages; model calls may incur costs.',
    limitations:
      'A may already have results, so this is not preregistration. Matching deals do not make models deterministic. Conclusions still require valid pairs, intervals, and evidence.',
    previous: 'Back',
    next: 'Next',
    create: 'Save design and create B',
    savedDesign: 'Frozen Prompt A/B design',
    openA: 'Open baseline A',
    compare: 'Compare A and B',
    loadFailed:
      'Design data could not be loaded or has changed. Review it again; your hypothesis is still on this page.',
    createFailed: 'Could not create B. Review the baseline and prompt again.',
    leave: 'This design has not been saved. Leave and discard the input on this page?',
    openHoldout: 'Open holdout pair',
    holdoutHint:
      'First use reserves the same fresh deals for frozen A and B. Reopening uses that pair. Start collection for each run separately.',
    origin: 'View development design',
    cloneDeals: 'The copy uses the public development deal plan.',
    holdoutFailed: 'Could not open holdout pair',
    issues: {
      source_run_not_member:
        'This run is not a member of the source report and cannot be used for this follow-up design.',
      source_conditions_changed:
        'Current baseline conditions differ from the source report. Recompare and save a new conclusion before continuing; changed conditions cannot represent the original report.',
      holdout_locked: 'Holdout deals are locked. Use a development run to design a new variant.',
      study_required: 'Add the baseline to research first.',
      doudizhu_required: 'This workflow currently supports paired win-rate analysis for Dou Dizhu.',
      fixed_plan_required:
        'A complete fixed deal plan without duplicate seeds is required. Create a benchmark run.',
      runtime_protocol_required: 'Create a baseline with the current engine’s decision protocol.',
      complete_protocol_required:
        'Frozen conditions are incomplete. Create a new baseline to isolate the change.',
      independent_games_required:
        'Cross-game memory creates dependent samples. Use a baseline without it.',
      model_player_required:
        'Offline policies do not use prompts. Prompt A/B needs at least one model player.',
      frozen_prompts_required:
        'Frozen prompt bodies or hashes are incomplete. Create a new baseline.',
    },
  },
}
