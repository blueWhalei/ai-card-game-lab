import { expect, it } from 'vitest'
import { recordedProgress, trainingError } from './trainingRecords'
it('does not replace unknown progress with zero or coerce invalid values', () => {
  for (const value of [null, undefined, '0', false, -1, 1.1, NaN, Infinity])
    expect(recordedProgress(value)).toBeNull()
  expect(recordedProgress(0)).toBe(0)
  expect(recordedProgress(1)).toBe(100)
  expect(recordedProgress(0.25)).toBe(25)
  expect(trainingError({ error: 'saved failure' })).toBe('saved failure')
  for (const value of ['broken', [], { error: 123 }, { error: ' ' }])
    expect(trainingError(value)).toBeNull()
})
