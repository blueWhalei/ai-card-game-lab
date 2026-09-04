export type FirstRunStepId = 'provider' | 'players' | 'experiment'

export interface FirstRunStep {
  id: FirstRunStepId
  done: boolean
}

export function firstRunSteps(input: {
  hasConfiguredProvider: boolean
  playerCount: number
  requiredPlayers: number
  experimentCount: number
}): FirstRunStep[] {
  const required = Math.max(1, input.requiredPlayers)
  return [
    { id: 'provider', done: input.hasConfiguredProvider },
    { id: 'players', done: input.playerCount >= required },
    { id: 'experiment', done: input.experimentCount > 0 },
  ]
}

export function firstIncompleteStep(steps: FirstRunStep[]): FirstRunStepId | null {
  return steps.find((step) => !step.done)?.id ?? null
}
