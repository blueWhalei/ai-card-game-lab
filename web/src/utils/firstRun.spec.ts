import { describe, expect, it } from 'vitest'
import { firstIncompleteStep, firstRunSteps } from './firstRun'

describe('firstRunSteps', () => {
  it('requires a provider, enough players, then an experiment', () => {
    expect(
      firstRunSteps({
        hasConfiguredProvider: false,
        playerCount: 0,
        requiredPlayers: 3,
        experimentCount: 0,
      }).map((s) => s.done),
    ).toEqual([false, false, false])

    expect(
      firstRunSteps({
        hasConfiguredProvider: true,
        playerCount: 3,
        requiredPlayers: 3,
        experimentCount: 0,
      }).map((s) => s.done),
    ).toEqual([true, true, false])
  })

  it('points at the first incomplete step', () => {
    const steps = firstRunSteps({
      hasConfiguredProvider: true,
      playerCount: 1,
      requiredPlayers: 3,
      experimentCount: 0,
    })
    expect(firstIncompleteStep(steps)).toBe('players')
  })
})
