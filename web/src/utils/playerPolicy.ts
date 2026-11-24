import type { PlayerPolicyKind } from '@/api/experimentConfigApi'

export const policyLabels: Record<PlayerPolicyKind, string> = {
  llm: 'config.policyKindLlm',
  tool_loop: 'config.policyKindToolLoop',
  search: 'config.policyKindSearch',
  heuristic: 'config.policyKindHeuristic',
  random: 'config.policyKindRandom',
  first: 'config.policyKindFirst',
}

export function isBaselineKind(kind: PlayerPolicyKind | undefined): boolean {
  return kind === 'heuristic' || kind === 'random' || kind === 'first'
}
