import type { EvidenceCandidate, ResearchReport } from '@/api/researchApi'
import reportCss from '@/styles/research-report.css?inline'

/** Resolve provenance only from frozen membership, never the current game table. */
export function evidenceOrigin(report: ResearchReport, decision: EvidenceCandidate) {
  const matches = (report.comparison.result.coverage?.members ?? []).flatMap((member) =>
    Object.entries(member.game_ids)
      .filter(([, gameId]) => gameId === decision.game_id)
      .map(([experimentId]) => ({ experimentId, seed: member.seed })),
  )
  return matches.length === 1 ? matches[0] : null
}

export function reportDecisionLink(report: ResearchReport, decision: EvidenceCandidate) {
  const origin = evidenceOrigin(report, decision)
  return {
    path: '/pipeline/decisions',
    query: {
      game_id: decision.game_id,
      decision_id: decision.id,
      report_id: report.record.id,
      evidence: decision.id,
      comparison_id: report.record.comparison_id,
      ...(origin
        ? { compare_seed: String(origin.seed), compare_turn: String(decision.round_number) }
        : {}),
    },
  }
}

export function reportComparisonLink(
  report: ResearchReport,
  decision?: EvidenceCandidate,
  traceId?: string,
) {
  const origin = decision && evidenceOrigin(report, decision)
  return {
    path: '/experiments/compare',
    query: {
      snapshot: report.record.comparison_id,
      report_id: report.record.id,
      ...(traceId && report.record.trace_evidence?.some((item) => item.trace.id === traceId)
        ? { trace_evidence: traceId }
        : {}),
      ...(decision ? { evidence: decision.id } : {}),
      ...(origin && decision
        ? { seed: String(origin.seed), turn: String(decision.round_number) }
        : {}),
    },
  }
}

/** Serialize the same Vue-rendered document, with no app routes or active content. */
export function reportHtml(element: HTMLElement, title: string, locale: string): string {
  const copy = element.cloneNode(true) as HTMLElement
  copy
    .querySelectorAll('[data-report-local],script,iframe,object,embed,link,style')
    .forEach((el) => el.remove())
  copy.querySelectorAll('*').forEach((el) => {
    for (const name of el.getAttributeNames()) {
      if (/^on/i.test(name) || ['src', 'srcset', 'style'].includes(name)) el.removeAttribute(name)
    }
  })
  copy.querySelectorAll('a').forEach((a) => {
    if (!/^#report-[a-z0-9-]+$/.test(a.getAttribute('href') ?? '')) a.removeAttribute('href')
  })
  copy.querySelectorAll('details').forEach((details) => details.setAttribute('open', ''))
  const escapedTitle = title.replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`)
  const language = locale === 'zh-CN' ? 'zh-CN' : 'en'
  return `<!doctype html>
<html lang="${language}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>${escapedTitle}</title><style>${reportCss}</style></head>
<body>${copy.outerHTML}</body></html>`
}
