// Calls to the FastAPI backend. Vite forwards /api/* to http://localhost:8000 (vite.config.ts).
import type {
  AdvisoryMap, AdvisorySummary, AlertsResponse, AssetDetail, AssetSummary, CitedAnswer, Mode, Person, RiskResponse,
} from './types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? `${res.status} ${path}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  assets: () => get<AssetSummary[]>('/assets'),
  asset: (id: string) => get<AssetDetail>(`/assets/${id}`),
  people: () => get<Person[]>('/people'),
  advisories: () => get<AdvisorySummary[]>('/advisories'),
  advisoryMap: (n: number) => get<AdvisoryMap>(`/advisories/${n}/map`),
  risks: (n: number) => get<RiskResponse>(`/risks?advisory=${n}`),
  alerts: (n: number, mode: Mode) => get<AlertsResponse>(`/alerts?advisory=${n}&mode=${mode}`),
  // AI (incident room commands)
  ask: (advisory: number, question: string) => post<CitedAnswer>('/llm/ask', { advisory, question }),
  report: (advisory: number, asset_id?: string) => post<CitedAnswer>('/llm/report', { advisory, asset_id }),
  playbook: (asset_id: string, question: string) => post<CitedAnswer>('/llm/playbook', { asset_id, question }),
}
