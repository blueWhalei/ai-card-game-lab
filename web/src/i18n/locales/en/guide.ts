export default {
  guide: {
    button: 'Guide',
    title: 'Usage guide',
    tocTitle: 'Contents',
    lookupTitle: 'Look up',
    intro:
      'CardLab follows a research loop: form a hypothesis, run games, review decisions, compare results and record conclusions. Training is an optional improvement tool.',
    hero: {
      goExperiments: 'Open experiments',
    },
    groups: {
      pages: 'Experiments and pages',
      analyze: 'Analyze',
      metrics: 'How metrics are computed',
      setup: 'Settings and environment',
    },
    diagrams: {
      loop: {
        caption: 'Recommended research loop',
        nodes: [
          { label: 'Players', icon: 'lucide:flask-conical' },
          { label: 'Start experiment', icon: 'lucide:play', tone: 'primary' },
          { label: 'Review decisions', icon: 'lucide:eye' },
          { label: 'Compare results', icon: 'lucide:git-compare' },
          { label: 'Record conclusion', icon: 'lucide:notebook-pen' },
        ],
      },
      detail: {
        caption: 'Run detail follows the current task',
        nodes: [
          { label: 'Not started', icon: 'lucide:circle-dashed', tone: 'muted' },
          { label: 'Running', icon: 'lucide:play' },
          { label: 'Results ready', icon: 'lucide:git-compare', tone: 'primary' },
        ],
        items: [
          'Before running: review the question and plan, then confirm batch size and usage after clicking Start.',
          'While running: see progress or watch a game. Pause and resume from Games and run details.',
          'After running: review decisions or compare results. Insufficient evidence remains explicitly uncertain.',
        ],
      },
      pipeline: {
        caption: 'Five tools under Analyze',
        hub: 'Sidebar Analyze, or the experiment ⋯ menu',
        nodes: [
          { label: 'Data', icon: 'lucide:database' },
          { label: 'Decisions', icon: 'lucide:crosshair' },
          { label: 'Training', icon: 'lucide:brain' },
          { label: 'Traces', icon: 'lucide:activity' },
          { label: 'Puzzles', icon: 'lucide:puzzle' },
        ],
        items: [
          'Scale, quality, per-model performance',
          'Filter trainable samples, annotate, register a dataset',
          'Create a fine-tune, or register as a player',
          'Each model call and response time',
          'Extract positions with differing payoff estimates; evaluate offline policies and action agreement under input perturbations',
        ],
      },
    },
    sections: {
      quickStart: {
        title: 'Recommended loop',
        steps: [
          'In Create experiment, choose “Try one offline game”, save, then confirm Start on the run page. CardLab prepares three local seats.',
          'Create research on Home, record a question, then design a run. A quick experiment creates research automatically.',
          'Record a hypothesis, run games and review decisions. Create a control or compare existing experiments, then record a conclusion. Training is optional under Analyze.',
        ],
      },
      experiments: {
        title: 'Experiment list',
        body: 'Home organizes questions, runs and comparisons by research. Design Prompt A/B selects a fixed-deal baseline, changes one phase’s prompt and reviews shared conditions. Save the design, start A and B separately, then compare, save a snapshot and review conclusions. All runs provides creation, import and demo entry points.',
        bullets: [
          'Fixed deals help control game conditions. Players, prompts and other settings still need review; fixed deals alone do not establish a valid comparison.',
          'Tasks and recorded usage switches between game and training tasks. Filter active tasks or abnormal records. Training tasks follow explicitly saved run ownership, with pagination, exact task links and return navigation. Unlinked tasks remain on the training page.',
          'Training progress is the last saved execution value. Completion does not demonstrate model improvement; independent held-out data and predefined controls are still required.',
          'Usage sums valid recorded token counts separately for each field and reports missing and invalid records. Missing values are not zero. These records are not a complete bill, remaining budget or valid research sample.',
          'Budget and expenses: enter costs from statements, receipts or allocation records in one fixed currency. Budget versions and void reasons are retained. Enabled limits reject new research game tasks and linked training creation once registered costs reach the limit. In-flight tasks continue; omissions and delayed entries can still cause overspending. This is not a hard cap on actual spending.',
          'Supplier costs: after separate Admin credentials are configured, manually sync OpenAI costs for a chosen organization, project and UTC interval, with source lines and sync history. Supplier and manual limits are checked independently; their amounts are not added. Enabled supplier limits also reject new tasks when snapshots are missing, failed or stale. Shared projects, reporting delays and excluded charges prevent these records from representing complete research costs or a final invoice. Periodic sync requires explicit enablement and runs only while the service runs. Pausing a plan does not disable budget checks. Distinguish scheduled times, query ends and cost coverage; automatic success does not establish completeness. Reconciliation records user-transcribed supplier evidence and compares amounts only for the same organization, project, currency and completed UTC period. Invoice totals and payments are not directly comparable to project costs. Inputs are not independently verified; numerical agreement does not establish complete costs. An optional review hold blocks new tasks for unresolved records. Disposition retains original amounts and history and does not waive other budget checks.',
        ],
      },
      experimentDetail: {
        title: 'Experiment detail',
        body: 'The main area shows the current phase and next action. Conditions, notes, game details and player results open on demand.',
        bullets: [
          'View conditions for frozen settings, Prompt A/B design, source and manifest export. Edit experiment notes for hypotheses, observations and the working summary.',
          'Games and run details provides watch, pause, resume and replay. Player results and benchmark reports open separately.',
          'Scenario records filters current decisions by documented, mutually exclusive rules, then opens a game and decision. The full decision page returns to the source scenario, page and record. Decision counts are not independent sample sizes; unevaluated records are not zero gaps, and post hoc action groups do not establish policy superiority.',
          'The more menu provides control creation, cloning, decisions, data, training and traces.',
        ],
      },
      playerConfigs: {
        title: 'Player configs',
        body: 'Decision procedure, model, and sampling. Pick them when you create an experiment (engine seat count applies).',
        bullets: [
          'Policy kind: LLM (single-shot), tool loop (ReAct tools), search-augmented (candidates + rollout), or heuristic / random / first-action baselines (zero API).',
          'Prompts are edited on the Prompts page, not here.',
          'A finished training run can be registered as a new player for a control experiment.',
        ],
      },
      games: {
        title: 'Trial games',
        body: 'Start a quick match that is not tied to any experiment—good for trying configs or demos.',
        bullets: [
          'To record data in an experiment, click Start experiment on the detail page.',
          'After a game ends, 3–5 highlight moves can jump to replay or a decision point.',
        ],
      },
      pipeline: {
        title: 'Analyze',
        body: 'Analyze provides data, decisions, training, invocation records and position tests. Run-scoped links retain a return entry. Decisions support training-format filters and good, bad or doubt annotations. Latency plots show the latest 200 records within the selected window; statistics cover every matching record in that window. List statistics have no time limit. Latency uses valid nonnegative values, and parse rates use explicit success or failure statuses; missing means neither zero nor failure. These are runtime diagnostics and do not establish policy ability. Invocation details can select an eligible frozen comparison for explicit review and citation, up to five records per revision. Publication checks the content hash and saves a copy. Changed sources require fresh review and an explicit citation update. Reports and HTML/JSON exports retain the content and its limitations; invocation counts do not add independent game samples.',
      },
      compare: {
        title: 'Compare experiments',
        body: 'Select 2–5 runs. A pair first shows its difference, sample size and interval. Multiple runs are not ranked by significance.',
        bullets: [
          'Review protocol and exclusions under Comparability and sample review. Changing runs or allowed fields requires recomparison before showing current results. All metrics remains accessible in small windows.',
          'Saving recomputes and freezes statistics and sample coverage. Two Dou Dizhu runs can locate scenarios within jointly valid deals, keep the complete recorded timeline, jump to matching steps or the first action divergence, and cite the visible pair. Either side matching retains the pair; divergence or gaps end same-path certainty. The full decision page returns to the original scenario, deal and step. Other comparisons use individual decision review.',
          'Shared steps synchronize both pre-action boards and recorded choices. Boards are rebuilt with the current matching engine version, frozen seed and continuous records; gaps stop reconstruction. The default view shows acting-player information. Other hands in researcher view were not visible to the actor. Citations preserve decision fields, not this reconstructed display.',
          'Cite in a comparison draft lists only comparisons whose frozen cohort and cutoff include the source. Review it, then explicitly add it. The comparison page supports one side or both; duplicates do not add entries, and exceeding 30 rejects the whole addition.',
          'Observation drafts save automatically; publishing a conclusion requires explicitly saving a version. Published conclusions can be read, revised and exported. A comparison snapshot is not a complete evidence package.',
          'Read report beside a published conclusion opens that revision’s hypotheses, conditions, valid pair count, intervals, author interpretation and frozen citations. Open the current decision or comparison position and return to the same citation; changed or deleted sources are marked explicitly.',
          'Reports export as offline HTML and data JSON. HTML includes a table of contents and supports browser printing to PDF. Neither format contains complete game archives, models or a runnable environment.',
          'Design a follow-up variant in a report checks the selected baseline against its frozen conditions before opening Prompt A/B. Enter a new hypothesis and primary outcome; the new run retains that exact conclusion revision as its source. Reusing development deals remains exploratory. Saving a design does not collect games; reserve holdout runs separately after freezing the design.',
        ],
      },
      metrics: {
        title: 'How metrics are computed',
        body: 'The “?” next to a cell is a one-line explanation. This section is the same glossary.',
        bullets: [
          'Usable for training: count of decision points with train_usable = true. Not “this move was good”.',
          'Landlord win rate: landlord-seat wins / decisive games (games with a winner). Draws excluded from n.',
          'Win-rate range: Wilson 95% interval: 95% describes long-run coverage under repeated sampling using this method. Decisive n < 20 or width > 0.3 triggers an exploratory evidence warning, not a power calculation or a promised sample size.',
          'Parse success: parser_ok = true / decisions with a parse record. Failures fall back to rules.',
          'Typical / slow response: P50 and P95 of decision response times.',
          'Tokens per game: sum of tokens / finished games.',
          'Landlord WR difference: this run − control (or previous run), in percentage points (pp).',
          'Same-deal WR difference: only pairs that share a deal seed.',
          'Decision details can create a position test: enter a question, freeze the record’s existing action-value estimates and evaluation settings, and retain a link to the source. At least two legal actions and verifiable continuous history are required. Offline baselines and input-order perturbations remain exploratory diagnostics of a case selected after observation. Unevaluated actions are not errors, and repeated perturbations do not add independent positions.',
          'The position-test page provides paginated baseline and perturbation history. Refreshing or returning from a source decision preserves the selected test. Export the same record as HTML or JSON. Source checks compare the current pack with its saved content fingerprint; older records without source snapshots are labelled explicitly and do not borrow the current question. These records are not published comparison conclusions.',
          'Cite in a comparison draft on a test result uses the same comparison selector as decision review. Every source must belong to the frozen jointly valid cohort. Review first, then explicitly add. Changed test content requires returning to reload the source. Opening a link does not modify the draft; duplicate citations preserve existing notes, with up to five tests per revision.',
          'A conclusion draft can explicitly cite up to five verifiable decision or batch tests, with up to 200 positions per test. Preview and publication check every source, frozen cohort membership and saved content; any ineligible position rejects the entire citation. Batch extraction selects by estimated payoff range and saves candidates, thresholds and caps. Payoffs are simulated again at extraction and are distinct from original decision estimates. Older records without provenance remain standalone. Published content is retained with current source status shown separately. Selection bias and within-game dependence limit interpretation; citations do not add valid games or establish general superiority.',
          'Paired difference = (B-only wins − A-only wins) / valid pairs. Exact McNemar uses the discordant counts.',
          'Scenario diagnostics use whole-run records: training-format usability divides by decision records, while parse success divides by decisions with traces. Mutually exclusive priority is bidding, bomb/rocket, endgame, then other play. Endgame uses a stored label or an own hand of 1–8 cards, a project definition. Navigation within the jointly valid cohort has a different scope and counts can change with source records; it does not establish policy ability.',
          'Each decision carries its seat’s final team outcome. Estimated payoff gaps assess moves. Training-format usability and parse success describe the run.',
          'Benchmark coverage: finished deals among the deal_seeds written at create time. Failed games still count as coverage. Collecting stops when those seeds are used.',
        ],
      },
      tune: {
        title: 'Settings and prompts',
        bullets: [
          'Settings: read-only runtime, paths, default thinking budget, EV opponent / self-play proxy, memory scope, and API key readiness (edit the configuration file shown in Settings).',
          'Restart after editing the configuration file; thinking budget, EV opponent, and memory only affect newly created experiments (in-flight protocols stay frozen).',
          'DPO preference export and teacher/student distill pairs are API-only (no UI); SFT still uses Decisions “register as training dataset”.',
          'Prompts: open from Settings to manage template versions. Compare effects through a single-stage Prompt A/B design from a frozen baseline in a study, not all-history version means across runs.',
        ],
      },
      prerequisites: {
        title: 'Environment',
        bullets: [
          'For model players, choose players in Create experiment and review Start conditions. Check model connection reads the catalog without generating a response.',
          'Optional: THINKING_BUDGET_*, EV_LOSS_OPPONENT_KIND, EV_LOSS_SELF_PROXY, MEMORY_SCOPE (none | per_experiment); Settings shows the current values.',
          'Set the indicated key or service address in the configuration file shown and restart the service. For Ollama, install the selected model tag.',
          'Training needs cd server && poetry install --with training.',
          'Push to Ollama requires LLAMA_CPP_DIR in .env.',
          'After startup, visit /api/v1/system/preflight for run-ready checks; Settings shows them too.',
        ],
      },
    },
  },
  metricHint: {
    aria: 'How this number is computed',
    moreInGuide: 'Open the usage guide: How metrics are computed',
    usable: {
      plain: 'Decision points you can fine-tune on — not “this move was good”.',
      formula: 'Count of points with train_usable = true. Filters live on the Decisions page.',
    },
    landlord: {
      plain: 'How often the landlord seat won, among games with a winner.',
      formula: 'Landlord wins / decisive games. n is decisive games. Draws are excluded.',
    },
    parser: {
      plain: 'How often the model reply parsed into a legal move instead of the rule fallback.',
      formula: 'parser_ok = true / decisions that have a parse record.',
    },
    latency: {
      plain: 'How long one model move takes: the typical case, and the slow tail.',
      formula: 'P50 / P95 of decision response times.',
    },
    tokens: {
      plain:
        'Recorded tokens normalized by finished games, describing logged consumption rather than monetary cost or complete usage.',
      formula: 'Sum of prompt+completion tokens / finished games.',
    },
    overallDelta: {
      plain: 'Compare the selected win outcome on valid shared deals.',
      formula:
        'Δ = this win rate − peer win rate on the same valid deals, in percentage points (pp). The detail page uses the current experiment as “this”. Directional support also requires valid pairs, a difference interval excluding zero, McNemar p < 0.05, and protocol review. This exploratory rule establishes neither equivalence nor general superiority.',
    },
    pairedDelta: {
      plain: 'Only games that were dealt the same cards — a fairer comparison.',
      formula: 'Selected win-rate difference on valid shared deal_seed pairs. n is the pair count.',
    },
    pairedStats: {
      plain: 'The paired test and difference interval use valid shared deals.',
      formula:
        'McNemar: exact two-sided binomial p on discordant outcomes for the selected metric. The conservative 95% difference interval combines two 97.5% Clopper–Pearson intervals for the discordant outcome probabilities using Bonferroni.',
    },
    ci: {
      plain:
        'The interval describes sampling uncertainty in the win-rate estimate, subject to sampling and independence assumptions.',
      formula:
        'Wilson 95% interval: 95% describes long-run coverage under repeated sampling using this method. Decisive n < 20 or width > 0.3 triggers an exploratory evidence warning, not a power calculation or a promised sample size.',
    },
    scenario: {
      plain:
        'Trainable share and parse rate split by bidding / playing / endgame / bomb. Δ is not good/bad.',
      formula: 'Endgame: any hand ≤ 8 cards. BOMB/ROCKET outranks endgame.',
    },
    benchmarkCoverage: {
      plain: 'How many of the declared fixed deals have been run.',
      formula:
        'The denominator is deal_seeds written at create time. Failed games count as coverage; no extra random seeds are added.',
    },
    evLoss: {
      plain:
        'Gap from the highest simulated mean among evaluated candidates. Zero means tied for this estimate, including when only one action was evaluated. Blank means not evaluated.',
      formula:
        'Estimated payoff gap = highest simulated candidate mean minus the chosen action mean. Candidates share sampled hidden hands and a specified continuation policy. Dou Dizhu pays 1 for a team win and 0 for a loss, without score multipliers. Candidate truncation, sampling error and continuation policy limit interpretation; zero does not establish global optimality.',
    },
  },
}
