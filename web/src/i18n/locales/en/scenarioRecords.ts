export default {
  scenarioRecords: {
    title: 'Scenario records',
    scope:
      'Browse currently saved decisions in this run, including unfinished games. These are not the jointly valid pairs of a frozen comparison. No scenario win rates or policy rankings are computed here.',
    refresh: 'Refresh current records',
    reset: 'Choose a scenario again',
    failed:
      'Could not read the selected scope. Records may have been deleted, positions may have changed, or the filter URL is invalid. Refresh or select a scenario again.',
    readAt: 'Records read at: {time}',
    definitions: 'Classification rules and limitations',
    rules:
      'Mutually exclusive groups, in order: bidding phase or bid/pass-bid action; bomb/rocket action; stored endgame phase or own hand of 1–{n} cards; all remaining records as general play. A stored endgame label may be triggered when any player has 1–{n} cards. This is a project operational definition, not a universal endgame standard.',
    limits:
      'Groups locate records rather than measure abilities. Bomb groups select actions actually taken and are post hoc subsets; they do not identify a prompt’s causal effect. Estimates with different evaluation settings are not pooled here, and a single decision estimate does not replace game outcomes.',
    denominators:
      'Decision records are not independent samples; records within a game are related. A game can occur in multiple groups, so group game counts cannot be added. Evaluated means an estimated expected-return gap was saved, not that evaluation is complete or correct.',
    group: 'Record group',
    decisions: 'Decision records',
    games: 'Distinct games',
    evaluated: 'Evaluated / records',
    names: {
      all: 'All records',
      bidding: 'Bidding decisions',
      playing: 'General play decisions',
      endgame: 'Endgame decisions',
      bomb: 'Bomb / rocket actions',
    },
    unrecorded: '{n} additional games have no decision records and are not listed below.',
    selectedGroup: 'Selected group: {name}',
    empty: 'No decision records in this group. This does not establish performance.',
    gameCounts: '{n} decisions · {evaluated} evaluated',
    selectedGame: 'Selected game',
    sequence:
      'Only records in the selected scenario are shown, ordered by stored decision round. This is not a complete game timeline. Rounds start at 0.',
    emptyPage: 'No records on this page. Return to the previous page or change the selection.',
    turn: 'Round {n}',
    unevaluated:
      'No estimated expected-return gap is saved for this record; it is not interpreted as zero.',
    openDecision: 'Read the full decision and evaluation basis',
    back: 'Return to the source run’s scenario records',
  },
}
