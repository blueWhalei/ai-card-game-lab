export const PIPELINE_SECTIONS = ['data', 'decisions', 'training', 'traces'] as const

export type PipelineSection = (typeof PIPELINE_SECTIONS)[number]

export function isPipelineSection(value: string): value is PipelineSection {
  return (PIPELINE_SECTIONS as readonly string[]).includes(value)
}

export function pipelinePath(section: PipelineSection): string {
  return `/pipeline/${section}`
}

/** Current or legacy tool URL → section. `/pipeline` itself is not a section. */
export function pipelineSectionOf(path: string): PipelineSection | null {
  const pipeline = /^\/pipeline\/([^/]+)/.exec(path)?.[1]
  if (pipeline && isPipelineSection(pipeline)) return pipeline
  const legacy = /^\/(data|decisions|training|traces)(?:\/|$)/.exec(path)?.[1]
  if (legacy && isPipelineSection(legacy)) return legacy
  return null
}

function firstString(value: unknown): string | undefined {
  if (typeof value === 'string' && value) return value
  if (Array.isArray(value) && typeof value[0] === 'string' && value[0]) return value[0]
  return undefined
}

/** Only the experiment scope hops between Analyze tabs. Tool-local query stays behind. */
export function pipelineScopeQuery(
  query: Record<string, unknown>,
): { experiment_id?: string } {
  const experimentId = firstString(query.experiment_id)
  return experimentId ? { experiment_id: experimentId } : {}
}
