import { useMemo, useState } from 'react'
import { useCurrent, useStore } from '../store'
import type { Tier } from '../types'
import TierBadge from './TierBadge'

const TIER_ORDER: Tier[] = ['Critical', 'High', 'Medium', 'Low']

// Asset status query: search by ID or name, filter by tier / type / region, rules and ML scores side by side
export default function AssetTable() {
  const { assets, selectedId, select } = useStore()
  const { risk } = useCurrent()
  const [query, setQuery] = useState('')
  const [tier, setTier] = useState<Tier | ''>('')
  const [type, setType] = useState('')
  const [region, setRegion] = useState('')

  const rows = useMemo(() => {
    const byId = Object.fromEntries((risk?.results ?? []).map((r) => [r.asset_id, r]))
    const q = query.toLowerCase()
    return assets
      .map((a) => ({ a, r: byId[a.asset_id] }))
      .filter(({ a, r }) => (!q || a.asset_id.toLowerCase().includes(q) || a.name.toLowerCase().includes(q))
        && (!tier || r?.standard.tier === tier || r?.ml.tier === tier)
        && (!type || a.type === type) && (!region || a.region === region))
      .sort((x, y) => (y.r?.standard.score ?? 0) - (x.r?.standard.score ?? 0))
  }, [assets, risk, query, tier, type, region])

  const types = [...new Set(assets.map((a) => a.type))].sort()
  const regions = [...new Set(assets.map((a) => a.region))].sort()

  return (
    <div className="flex h-full flex-col bg-slate-50 p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search asset ID or name…"
               className="w-64 rounded border border-slate-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-teal" />
        <Select value={tier} onChange={(v) => setTier(v as Tier | '')} all="All tiers" options={TIER_ORDER} />
        <Select value={type} onChange={setType} all="All types" options={types} />
        <Select value={region} onChange={setRegion} all="All regions" options={regions} />
        <span className="ml-auto text-xs text-slate-500">{rows.length} of {assets.length} assets</span>
      </div>

      <div className="flex-1 overflow-auto rounded border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-100 text-left text-xs text-slate-500">
            <tr>{['Asset', 'Name', 'Type', 'Region', 'Rules', 'ML', 'ML − rules', 'Consequence', 'Field report', 'Top reason']
                  .map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map(({ a, r }) => (
              <tr key={a.asset_id} onClick={() => select(a.asset_id)}
                  className={`cursor-pointer border-t border-slate-100 hover:bg-slate-50 ${selectedId === a.asset_id ? 'bg-teal/10' : ''}`}>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{a.asset_id}</td>
                <td className="px-3 py-2">{a.name}</td>
                <td className="px-3 py-2 text-xs text-slate-500">{a.type.replace(/_/g, ' ')}</td>
                <td className="px-3 py-2 text-xs text-slate-500">{a.region}</td>
                <td className="px-3 py-2">{r && <TierBadge tier={r.standard.tier} score={r.standard.score} />}</td>
                <td className="px-3 py-2">{r && <TierBadge tier={r.ml.tier} score={r.ml.score} />}</td>
                <td className="px-3 py-2 text-xs">{r && <Diff value={r.ml.score - r.standard.score} />}</td>
                <td className="px-3 py-2 text-xs">{r ? `${Math.round(r.standard.consequence * 100)}%` : ''}</td>
                <td className="px-3 py-2 text-xs">{r?.field_status?.replace(/_/g, ' ') ?? '—'}</td>
                <td className="max-w-xs truncate px-3 py-2 text-xs text-slate-500">{r?.standard.reasons[0] ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// How much higher (red) or lower (green) the ML scores this asset than the rules
function Diff({ value }: { value: number }) {
  if (Math.abs(value) < 0.05) return <span className="text-slate-400">≈</span>
  return <span className={value > 0 ? 'font-semibold text-tier-critical' : 'text-green-700'}>
    {value > 0 ? '+' : ''}{value.toFixed(2)}</span>
}

function Select({ value, onChange, all, options }: { value: string; onChange: (v: string) => void; all: string; options: string[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
            className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm outline-none">
      <option value="">{all}</option>
      {options.map((o) => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
    </select>
  )
}
