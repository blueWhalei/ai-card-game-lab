import { describe, expect, it } from 'vitest'
import { mergeUniqueIds } from './filterFacets'

describe('mergeUniqueIds', () => {
  it('keeps first-seen order and drops blanks', () => {
    expect(mergeUniqueIds(['b', 'a'], ['a', 'c'], [''], [undefined, 'b'])).toEqual([
      'b',
      'a',
      'c',
    ])
  })

  it('can replace a shrinking filtered page with the union', () => {
    const seen = mergeUniqueIds(['tiger', 'fox', 'panda'])
    const afterFilter = mergeUniqueIds(seen, ['fox'])
    expect(afterFilter).toEqual(['tiger', 'fox', 'panda'])
  })
})
