export default {
  guide: {
    button: 'Guide',
    title: 'Usage guide',
    tocTitle: 'Contents',
    lookupTitle: 'Look up',
    intro:
      'CardLab is built around experiments: watch decisions, collect games, fine-tune a small model, then validate with a control run.',
    hero: {
      goPlayers: 'Open player configs',
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
          { label: 'Watch', icon: 'lucide:eye' },
          { label: 'Training', icon: 'lucide:brain' },
          { label: 'Control', icon: 'lucide:git-branch' },
        ],
      },
      detail: {
        caption: 'Five phases of experiment detail',
        nodes: [
          { label: 'No games', icon: 'lucide:circle-dashed', tone: 'muted' },
          { label: 'Collecting', icon: 'lucide:play' },
          { label: 'Data ready', icon: 'lucide:database' },
          { label: 'Control experiment', icon: 'lucide:git-branch' },
          { label: 'Verdict', icon: 'lucide:git-compare', tone: 'primary' },
        ],
        items: [
          'Nothing has run yet: one sentence and Start experiment.',
          'In progress: a progress number; the button becomes Watch.',
          'After games finish: trainable decision count, and Start training.',
          'After training: replay the same deals, and Start control experiment.',
          'Control ready: a verdict plus Δ. Full matrix via “Full comparison table”.',
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
          'Extract high-spread spots; score baselines and probe perturbations offline',
        ],
      },
    },
    sections: {
      quickStart: {
        title: 'Recommended loop',
        steps: [
          'In Player configs, add one model per seat (Dou Dizhu needs 3). Creating an experiment does not start games.',
          'Back on Home, create an experiment and open its detail page.',
          'Detail offers one button at a time: Start experiment → Watch → Train → Control. Follow it.',
        ],
      },
      experiments: {
        title: 'Experiment list',
        body: 'Home is the experiment list: create a run, import a pack, or load a demo game (no API key).',
        bullets: [
          'Benchmark mode uses fixed deals so models can be compared fairly.',
          'Each row shows status and the next step.',
        ],
      },
      experimentDetail: {
        title: 'Experiment detail',
        body: 'One question and one button at a time. Follow the current button to walk the whole loop.',
        bullets: [
          'When a control is ready: a verdict plus Δ. If evidence is thin, the headline is “not enough to conclude” and Δ drops to a footnote.',
          'A benchmark run shows this experiment’s numbers under the phase; the control replays the same deals.',
          'The ⋯ menu: decisions, data, training, traces for this run, plus the record (hypothesis, protocol, export).',
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
        body: 'Analyze is five tools under one sidebar item (data / decisions / training / traces / puzzles). Linked from an experiment, the bar at the top returns you to detail. On Decisions you can filter trainable rows and label good / bad / doubt.',
      },
      compare: {
        title: 'Compare experiments',
        body: 'Home “Compare several experiments” lines up 2–5 runs. Detail only answers “vs this control, what changed?”',
        bullets: [
          'After paired control games, detail shows the verdict; this page is the full matrix.',
        ],
      },
      metrics: {
        title: 'How metrics are computed',
        body: 'The “?” next to a cell is a one-line explanation. This section is the same glossary.',
        bullets: [
          'Usable for training: count of decision points with train_usable = true. Not “this move was good”.',
          'Landlord win rate: landlord-seat wins / decisive games (games with a winner). Draws excluded from n.',
          'Win-rate range: Wilson 95% interval. Decisive n < 20 or width > 0.3 is marked underpowered.',
          'Parse success: parser_ok = true / decisions with a parse record. Failures fall back to rules.',
          'Typical / slow response: P50 and P95 of decision response times.',
          'Tokens per game: sum of tokens / finished games.',
          'Landlord WR difference: this run − control (or previous run), in percentage points (pp).',
          'Same-deal WR difference: only pairs that share a deal seed.',
          'Paired McNemar / bootstrap: exact p on landlord flips; percentile CI on per-seed Δ.',
          'Scenario subscores: bidding / playing / endgame (any hand ≤8) / bomb. Bomb outranks endgame. Trainable share and parse rate; Δ is not good/bad.',
          'Game result score: end-game outcome proxy (win 0.8 / loss 0.3 / draw 0.5), not move quality. SFT filtering uses train_usable.',
          'Benchmark coverage: finished deals among the deal_seeds written at create time. Failed games still count as coverage. Collecting stops when those seeds are used.',
        ],
      },
      tune: {
        title: 'Settings and prompts',
        bullets: [
          'Settings: read-only runtime, paths, default thinking budget, EV opponent / self-play proxy, memory scope, and API key readiness (all configured in project-root .env).',
          'Restart after editing .env; thinking budget, EV opponent, and memory only affect newly created experiments (in-flight protocols stay frozen).',
          'DPO preference export and teacher/student distill pairs are API-only (no UI); SFT still uses Decisions “register as training dataset”.',
          'Prompts: open from Settings to manage in-game templates; version and A/B test.',
        ],
      },
      prerequisites: {
        title: 'Environment',
        bullets: [
          'Copy .env.example → .env; set at least one cloud API key or local Ollama.',
          'Optional: THINKING_BUDGET_*, EV_LOSS_OPPONENT_KIND, EV_LOSS_SELF_PROXY, MEMORY_SCOPE (none | per_experiment); Settings shows the current values.',
          'Keys are checked before the experiment starts; missing keys are rejected.',
          'Training needs cd server && poetry install --with training.',
          'Push to Ollama requires LLAMA_CPP_DIR in .env.',
          'After startup, visit /api/v1/system/preflight for run-ready checks; Settings shows them too.',
        ],
      },
    },
  },
  firstRun: {
    title: 'From zero to first game',
    subtitle: 'Follow the checklist to start an experiment. No API key? Load a demo game first.',
    done: 'Done',
    goSettings: 'Open Settings',
    goPlayers: 'Go to player configs',
    step: {
      provider: 'Configure a model provider',
      players: 'Create players',
      experiment: 'Create an experiment',
    },
    hint: {
      provider: 'Set at least one API key in .env, or run local Ollama. Settings shows readiness.',
      players: 'This game needs at least {n} players (model and sampling).',
      experiment: 'Pick players and a target game count. Creating does not start games; click Start experiment on the detail page.',
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
      plain: 'Average tokens used per finished game (cost estimate).',
      formula: 'Sum of prompt+completion tokens / finished games.',
    },
    overallDelta: {
      plain: 'This run’s landlord win rate minus the control (or previous run). Sign is not good/bad.',
      formula: 'Δ = this landlord WR − peer landlord WR, in percentage points (pp). The detail page uses the current experiment as “this”.',
    },
    pairedDelta: {
      plain: 'Only games that were dealt the same cards — a fairer comparison.',
      formula: 'Landlord WR difference on shared deal_seed pairs. n is the pair count.',
    },
    pairedStats: {
      plain: 'Paired McNemar and bootstrap CI on same-deal landlord flips.',
      formula:
        'McNemar: exact two-sided binomial p on discordant landlord outcomes. Paired Δ 95% CI: percentile bootstrap over per-seed differences.',
    },
    ci: {
      plain: 'Where the true win rate likely sits given current n. Fewer games → wider band.',
      formula: 'Wilson 95% interval. Decisive n < 20 or width > 0.3 is marked underpowered.',
    },
    scenario: {
      plain: 'Trainable share and parse rate split by bidding / playing / endgame / bomb. Δ is not good/bad.',
      formula: 'Endgame: any hand ≤ 8 cards. BOMB/ROCKET outranks endgame.',
    },
    quality: {
      plain: 'An end-game outcome proxy, not whether this move was skillful.',
      formula: 'Win 0.8 / loss 0.3 / draw 0.5 for that seat. SFT filtering uses train_usable, not this score.',
    },
    benchmarkCoverage: {
      plain: 'How many of the declared fixed deals have been run.',
      formula: 'The denominator is deal_seeds written at create time. Failed games count as coverage; no extra random seeds are added.',
    },
    evLoss: {
      plain: 'How much value this move gave up versus the best simulated candidate. 0 means it was the best one; blank means it was never evaluated.',
      formula:
        'Loss = expected payoff of the best candidate − expected payoff of the move played. Payoffs come from sampling the hidden hands and playing each candidate out to the end, reusing the same sampled worlds across candidates. Evaluator settings are stored with each record: two numbers produced with different settings are not comparable.',
    },
  },
}
