import { TIER_COLOR, useCurrent, useStore } from '../store'
import type { AssetSummary, Tier } from '../types'

// Schematic dependency diagram for the asset panel, left to right:
//   Depends on  ->  this asset  ->  Supplies  ->  Knock-on (everything further down, linked from the branch it comes through)
// Node colour = rules tier now. Click a node to select that asset.

const COL_X = [0, 114, 228, 342]
const NODE_W = 82
const NODE_H = 36
const ROW_H = 44
const MAX_KNOCK_ON = 8

const TYPE_LABEL: Record<string, string> = {
  substation: 'substation', transmission_line: 'line', generation: 'power plant', pumping_station: 'pump station',
  water_treatment: 'water plant', wastewater_treatment: 'wastewater',
}

interface Node { id: string; col: number; row: number }

export default function DependencyGraph({ assetId }: { assetId: string }) {
  const { assets, select } = useStore()
  const { risk } = useCurrent()
  const byId: Record<string, AssetSummary> = Object.fromEntries(assets.map((a) => [a.asset_id, a]))
  const tierOf: Record<string, Tier> = Object.fromEntries((risk?.results ?? []).map((r) => [r.asset_id, r.standard.tier]))
  const sel = byId[assetId]
  if (!sel) return null

  // knock-on: every asset further downstream, remembered with the direct branch it is reached through
  const via: Record<string, string> = {}
  for (const branch of sel.downstream) {
    const todo = [...(byId[branch]?.downstream ?? [])]
    while (todo.length) {
      const id = todo.shift()!
      if (id === assetId || sel.downstream.includes(id) || via[id]) continue
      via[id] = branch
      todo.push(...(byId[id]?.downstream ?? []))
    }
  }
  const knockOn = Object.keys(via)
  const shown = knockOn.slice(0, MAX_KNOCK_ON)
  const hidden = knockOn.length - shown.length

  const columns = [sel.upstream, [assetId], sel.downstream, shown]
  const rows = Math.max(1, ...columns.map((c) => c.length)) + (hidden > 0 ? 1 : 0)
  const height = rows * ROW_H
  const nodes: Node[] = columns.flatMap((ids, col) => {
    const offset = (rows - ids.length - (col === 3 && hidden > 0 ? 1 : 0)) / 2
    return ids.map((id, i) => ({ id, col, row: offset + i }))
  })
  const pos = Object.fromEntries(nodes.map((n) => [`${n.col}:${n.id}`, n]))
  const y = (n: Node) => n.row * ROW_H + (ROW_H - NODE_H) / 2

  const edges: { from: Node; to: Node; kind: 'up' | 'down' | 'indirect' }[] = [
    ...sel.upstream.map((u) => ({ from: pos[`0:${u}`], to: pos[`1:${assetId}`], kind: 'up' as const })),
    ...sel.downstream.map((d) => ({ from: pos[`1:${assetId}`], to: pos[`2:${d}`], kind: 'down' as const })),
    ...shown.map((k) => ({ from: pos[`2:${via[k]}`], to: pos[`3:${k}`], kind: 'indirect' as const })),
  ].filter((e) => e.from && e.to)

  const headers = ['Depends on', 'This asset', 'Supplies', 'Knock-on']

  return (
    <div>
      <div className="mb-1 grid grid-cols-4 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {headers.map((h) => <span key={h}>{h}</span>)}
      </div>
      <svg viewBox={`0 0 ${COL_X[3] + NODE_W} ${height}`} className="w-full" style={{ height }}>
        {edges.map((e, i) => {
          const x1 = COL_X[e.from.col] + NODE_W, y1 = y(e.from) + NODE_H / 2
          const x2 = COL_X[e.to.col], y2 = y(e.to) + NODE_H / 2
          const mid = (x1 + x2) / 2
          return (
            <path key={i} d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2 - 4},${y2}`} fill="none"
                  stroke={e.kind === 'up' ? '#0f2b46' : '#ea580c'} strokeOpacity={e.kind === 'indirect' ? 0.45 : 0.9}
                  strokeWidth={e.kind === 'indirect' ? 1.5 : 2} strokeDasharray="2 3" strokeLinecap="round"
                  markerEnd={`url(#arrow-${e.kind === 'up' ? 'up' : 'down'})`} />
          )
        })}
        <defs>
          {[['up', '#0f2b46'], ['down', '#ea580c']].map(([id, color]) => (
            <marker key={id} id={`arrow-${id}`} viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L6,3 L0,6 z" fill={color} />
            </marker>
          ))}
        </defs>

        {nodes.map((n) => {
          const a = byId[n.id]
          const isSel = n.id === assetId
          const color = TIER_COLOR[tierOf[n.id] ?? 'Low']
          return (
            <g key={`${n.col}:${n.id}`} transform={`translate(${COL_X[n.col]},${y(n)})`}
               onClick={() => !isSel && select(n.id)} className={isSel ? '' : 'cursor-pointer'}>
              <title>{`${n.id} · ${a?.name} (${tierOf[n.id] ?? 'Low'})`}</title>
              <rect width={NODE_W} height={NODE_H} rx="6" fill={isSel ? '#0f2b46' : '#ffffff'}
                    stroke={isSel ? '#0f2b46' : '#cbd5e1'} />
              <rect width="5" height={NODE_H} rx="2" fill={color} />
              <text x="11" y="15" fontSize="10.5" fontWeight="700" fill={isSel ? '#ffffff' : '#0f2b46'}>{n.id}</text>
              <text x="11" y="28" fontSize="9" fill={isSel ? '#cbd5e1' : '#64748b'}>
                {short(a?.name ?? '', a?.type)}
              </text>
            </g>
          )
        })}
        {hidden > 0 && (
          <text x={COL_X[3] + 4} y={height - 14} fontSize="10" fill="#64748b">+{hidden} more</text>
        )}
      </svg>
    </div>
  )
}

// Short second line: the name if it fits, otherwise the asset type
function short(name: string, type?: string) {
  const clean = name.replace(/ \d+ kV$/, '')
  return clean.length <= 13 ? clean : TYPE_LABEL[type ?? ''] ?? clean.slice(0, 12) + '…'
}
