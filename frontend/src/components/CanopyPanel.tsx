import { useState } from 'react'
import { useStore } from '../store'

// Tree canopy around an asset from satellite imagery, on request (it calls Esri and Claude, a few seconds):
// the GIS record vs green cover measured from pixel colours vs the AI's tree canopy estimate and notes.
export default function CanopyPanel({ assetId }: { assetId: string }) {
  const { canopy, analyseCanopy } = useStore()
  const [showMask, setShowMask] = useState(false)
  const state = canopy[assetId]

  if (!state) {
    return (
      <button onClick={() => analyseCanopy(assetId)}
              className="w-full rounded border border-teal/50 py-2 text-xs font-semibold text-teal hover:bg-teal/5">
        Analyse satellite imagery for tree canopy
      </button>
    )
  }
  if (state === 'loading') {
    return (
      <div className="flex items-center gap-2 py-2 text-xs text-slate-500">
        <span className="h-2 w-2 animate-ping rounded-full bg-teal" />Fetching imagery and analysing canopy…
      </div>
    )
  }
  if ('error' in state) return <div className="text-xs text-tier-critical">Could not analyse imagery: {state.error}</div>

  return (
    <div className="space-y-2">
      <div className="relative">
        <img src={showMask ? state.mask : state.image} alt={`Satellite image around ${assetId}`}
             className="w-full rounded border border-slate-200" />
        <div className="absolute right-2 top-2 flex overflow-hidden rounded border border-white/60 text-[10px] shadow">
          {(['Photo', 'Green mask'] as const).map((label, i) => (
            <button key={label} onClick={() => setShowMask(i === 1)}
                    className={`px-2 py-0.5 ${showMask === (i === 1) ? 'bg-navy text-white' : 'bg-white/90 text-slate-700'}`}>
              {label}
            </button>
          ))}
        </div>
        <span className="absolute bottom-1 left-1 rounded bg-black/50 px-1 text-[9px] text-white">{state.size_m} m across</span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <Figure label="GIS record" value={state.gis_tree_canopy_pct} note="tree canopy" />
        <Figure label="Measured" value={state.green_pct} note="all green (incl. grass)" />
        <Figure label="AI estimate" value={state.ai.tree_canopy_pct} note={`trees · ${state.ai.confidence} confidence`} highlight />
      </div>
      <p className="rounded bg-slate-50 p-2 text-[11px] leading-snug text-slate-700"><b className="text-teal">AI: </b>{state.ai.notes}</p>
      <div className="text-[10px] text-slate-400">Imagery: {state.attribution}. Measured = Excess Green index, threshold {state.threshold} (Otsu).</div>
    </div>
  )
}

function Figure({ label, value, note, highlight = false }: { label: string; value: number | null; note: string; highlight?: boolean }) {
  return (
    <div className={`rounded px-1 py-1.5 ${highlight ? 'bg-teal/10' : 'bg-slate-50'}`}>
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={`text-base font-semibold ${highlight ? 'text-teal' : 'text-navy'}`}>{value === null ? '—' : `${Math.round(value)}%`}</div>
      <div className="text-[9px] leading-tight text-slate-400">{note}</div>
    </div>
  )
}
