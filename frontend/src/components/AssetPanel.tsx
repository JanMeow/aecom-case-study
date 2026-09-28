import { useCurrent, useStore } from '../store'
import type { RiskResult } from '../types'
import DependencyGraph from './DependencyGraph'
import TierBadge from './TierBadge'

const label = (s: string) => s.replace(/_/g, ' ')

// Right-hand panel for the selected asset: rules and ML scores side by side, why, owner, dependencies, history
export default function AssetPanel() {
  const { selectedId, select, details } = useStore()
  const { risk } = useCurrent()
  if (!selectedId) return null
  const d = details[selectedId]
  const r = risk?.results.find((x) => x.asset_id === selectedId)

  return (
    <aside className="flex w-[28rem] shrink-0 flex-col overflow-y-auto border-l border-slate-200 bg-white">
      <div className="flex items-start justify-between border-b border-slate-200 p-4">
        <div>
          <div className="text-xs text-slate-500">{selectedId} · {d ? label(d.type) : ''} · {d?.region}</div>
          <div className="text-lg font-semibold text-navy">{d?.name ?? '…'}</div>
        </div>
        <button onClick={() => select(null)} className="text-slate-400 hover:text-slate-700">✕</button>
      </div>

      {r && (
        <section className="space-y-3 border-b border-slate-200 p-4">
          <div className="grid grid-cols-2 gap-3">
            <ScoreColumn title="Rules score" note="drives alerts" result={r.standard} />
            <ScoreColumn title="ML score" note="Phase 2 preview" result={r.ml} />
          </div>
          {r.field_status && (
            <div className="rounded bg-slate-100 px-2 py-1 text-xs">Field report: <b>{label(r.field_status)}</b></div>
          )}
        </section>
      )}

      {d && (
        <>
          <section className="space-y-1 border-b border-slate-200 p-4 text-xs text-slate-700">
            <Row k="Owner" v={d.owner ? `${d.owner.name}, ${d.owner.title}` : '—'} />
            <Row k="Contact" v={d.owner ? `${d.owner.phone} · ${d.owner.email}` : '—'} />
            <Row k="Condition" v={d.condition_rating ? `${d.condition_rating}/5` : '—'} />
            <Row k="Installed" v={String(d.install_year)} />
            <Row k="Elevation / flood zone" v={`${d.elevation_m} m / ${d.flood_zone}`} />
            <Row k="Backup power" v={d.has_backup_power ? `Yes, ${d.backup_hours} h fuel` : 'No'} />
            <Row k="Customers served" v={d.customers_served.toLocaleString()} />
            <Row k="Data from" v={d.sources.join(', ')} />
          </section>

          <section className="space-y-2 border-b border-slate-200 p-4 text-xs">
            <DependencyGraph assetId={selectedId} />
            {d.critical_facilities.length > 0 && (
              <div>
                <div className="mb-1 font-semibold text-slate-500">Critical facilities</div>
                {d.critical_facilities.map((f) => (
                  <div key={f.facility_id + f.via}>{f.name} <span className="text-slate-400">({f.kind}, {f.via})</span></div>
                ))}
              </div>
            )}
          </section>

          {d.history.length > 0 && (
            <section className="p-4 text-xs">
              <div className="mb-1 font-semibold text-slate-500">Maintenance & storm history</div>
              {d.history.slice(0, 5).map((h) => (
                <div key={h.wo_no} className="border-b border-slate-100 py-1">
                  <span className="text-slate-400">{h.date} · {h.type}</span> {h.summary}
                </div>
              ))}
            </section>
          )}
        </>
      )}
    </aside>
  )
}

function ScoreColumn({ title, note, result }: { title: string; note: string; result: RiskResult }) {
  return (
    <div className="space-y-2 rounded border border-slate-200 p-2">
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-semibold text-navy">{title}</span>
        <span className="text-[10px] text-slate-400">{note}</span>
      </div>
      <TierBadge tier={result.tier} score={result.score} />
      <div className="space-y-1">
        <Stat name="Own chance" value={result.own_chance} />
        <Stat name="Likelihood" value={result.likelihood} />
        <Stat name="Consequence" value={result.consequence} />
      </div>
      <ul className="list-disc space-y-1 pl-4 text-[11px] leading-snug text-slate-700">
        {result.reasons.map((reason) => <li key={reason}>{reason}</li>)}
      </ul>
    </div>
  )
}

function Stat({ name, value }: { name: string; value: number }) {
  return (
    <div className="flex justify-between rounded bg-slate-50 px-2 py-0.5 text-[11px]">
      <span className="text-slate-500">{name}</span>
      <span className="font-semibold text-navy">{Math.round(value * 100)}%</span>
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex justify-between gap-3"><span className="text-slate-500">{k}</span><span className="text-right">{v}</span></div>
}
