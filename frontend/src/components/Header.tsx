import { formatTime, TIER_COLOR, useCurrent, useStore } from '../store'
import type { Tier } from '../types'

const TIERS: Tier[] = ['Critical', 'High', 'Medium', 'Low']

// Top bar: storm status at the current replay time, tier counts for both scores, logged-in user
export default function Header() {
  const { user, people, setUser } = useStore()
  const { advisory, risk } = useCurrent()

  return (
    <header className="flex h-14 shrink-0 items-center gap-6 bg-navy px-5 text-white">
      <div className="whitespace-nowrap font-semibold tracking-wide">SGW Resilience Platform</div>

      {advisory && (
        <div className="flex items-center gap-3 whitespace-nowrap text-sm">
          <span className="rounded bg-white/10 px-2 py-1">Hurricane Ian · Advisory {advisory.advisory}</span>
          <span className="text-white/70">{formatTime(advisory.issued_at)}</span>
          <span className="text-white/70">
            {advisory.category > 0 ? `Cat ${advisory.category}` : advisory.storm_type} · {advisory.max_wind_kt} kt
          </span>
        </div>
      )}

      {risk && (
        <div className="flex flex-col gap-0.5 whitespace-nowrap text-[11px]">
          {(['standard', 'ml'] as const).map((m) => (
            <div key={m} className="flex items-center gap-2">
              <span className="w-9 text-white/60">{m === 'standard' ? 'Rules' : 'ML'}</span>
              {TIERS.map((t) => (
                <span key={t} className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full" style={{ background: TIER_COLOR[t] }} />
                  {risk.tiers[m][t]} {t}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="ml-auto flex items-center gap-4 text-sm">
        {user && (
          <label className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal text-xs font-semibold">
              {user.name.split(' ').map((w) => w[0]).join('')}
            </span>
            <select value={user.employee_id} onChange={(e) => setUser(e.target.value)}
                    className="cursor-pointer bg-transparent text-sm outline-none" title="View as">
              {people.map((p) => (
                <option key={p.employee_id} value={p.employee_id} className="text-black">{p.name} · {p.title}</option>
              ))}
            </select>
          </label>
        )}
      </div>
    </header>
  )
}
