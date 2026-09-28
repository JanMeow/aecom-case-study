// Calls to the FastAPI backend. Vite forwards /api/* to http://localhost:8000 (vite.config.ts).
import type {
  AdvisoryMap, AdvisorySummary, AlertsResponse, AssetDetail, AssetSummary, Mode, Person, RiskResponse,
} from './types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
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
}
