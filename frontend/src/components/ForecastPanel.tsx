import { useEffect, useState } from 'react'
import { api } from '../api'
import { useStore } from '../store'
import type { ForecastResult, ForecastScope } from '../types'
import TierBadge from './TierBadge'

const ZONES = [
  { kt: 34, label: '34 kt · tropical storm' },
  { kt: 50, label: '50 kt · strong tropical storm' },
  { kt: 64, label: '64 kt · hurricane force' },
]

// What-if scenario forecast (ML): "if a storm with this wind hit, how likely is this asset to fail?"
// Scope matters because of dependencies: with its region hit, the asset's suppliers are hit too.
export default function ForecastPanel({ assetId }: { assetId: string }) {
  const region = useStore((s) => s.assets.find((a) => a.asset_id === assetId)?.region)
  const [zone, setZone] = useState(64)
  const [scope, setScope] = useState<ForecastScope>('region')
  const [data, setData] = useState<ForecastResult | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {   // the ML model is fast, so re-run whenever a choice changes
    setError('')
    api.forecast(assetId, zone, scope).then(setData).catch((e) => setError((e as Error).message))
  }, [assetId, zone, scope])

  const scopes: { id: ForecastScope; label: string }[] = [
    { id: 'asset', label: 'Only this asset' },
    { id: 'region', label: `Its region (${region ?? '…'})` },
    { id: 'all', label: 'Whole service area' },
  ]
  const r = data?.result

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <select value={zone} onChange={(e) => setZone(Number(e.target.value))}
                className="rounded border border-slate-300 bg-white px-2 py-1 text-xs">
          {ZONES.map((z) => <option key={z.kt} value={z.kt}>{z.label}</option>)}
        </select>
        <select value={scope} onChange={(e) => setScope(e.target.value as ForecastScope)}
                className="rounded border border-slate-300 bg-white px-2 py-1 text-xs">
          {scopes.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
      </div>

      {error && <div className="text-tier-critical">{error}</div>}
      {r && data && (
        <div className="rounded border border-slate-200 p-2">
          <div className="flex items-center gap-2">
            <TierBadge tier={r.tier} score={r.score} />
            <span className="text-slate-500">ML score if hit by {data.wind_zone} kt</span>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-center">
            <Stat label="Own chance" value={r.own_chance} />
            <Stat label="Likelihood" value={r.likelihood} note={r.depends_on ? `via ${r.depends_on}` : 'own'} />
            <Stat label="Consequence" value={r.consequence} />
          </div>
          <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] text-slate-600">
            {r.reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
          <div className="mt-2 text-[10px] text-slate-400">
            Scenario hits {data.assets_hit} asset{data.assets_hit === 1 ? '' : 's'}: {data.tiers.Critical} Critical,
            {' '}{data.tiers.High} High. Planning estimate from synthetic training data.
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="rounded bg-slate-50 py-1">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-navy">{Math.round(value * 100)}%</div>
      {note && <div className="text-[9px] text-slate-400">{note}</div>}
    </div>
  )
}
