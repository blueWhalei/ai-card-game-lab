import { describe, expect, it } from 'vitest'
import {
  isPipelineSection,
  pipelinePath,
  pipelineScopeQuery,
  pipelineSectionOf,
} from './pipeline'

describe('pipeline', () => {
  it('maps sections to hub paths', () => {
    expect(pipelinePath('data')).toBe('/pipeline/data')
    expect(isPipelineSection('data')).toBe(true)
    expect(isPipelineSection('prompt')).toBe(false)
  })

  it('reads the section from hub and legacy tool URLs', () => {
    expect(pipelineSectionOf('/pipeline/decisions')).toBe('decisions')
    expect(pipelineSectionOf('/training')).toBe('training')
    expect(pipelineSectionOf('/traces/extra')).toBe('traces')
    expect(pipelineSectionOf('/pipeline')).toBeNull()
    expect(pipelineSectionOf('/settings')).toBeNull()
  })

  it('keeps only experiment_id when switching tools', () => {
    expect(
      pipelineScopeQuery({
        experiment_id: 'exp-1',
        tab: 'models',
        game_id: 'g-1',
      }),
    ).toEqual({ experiment_id: 'exp-1' })
    expect(pipelineScopeQuery({ tab: 'storage' })).toEqual({})
  })
})
