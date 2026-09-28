import { useEffect } from 'react'
import { palette, tierColor } from '../colors'
import { useStore } from '../store'

const STEP_MS = 1500 // how long each advisory stays on screen while playing

// Vertical replay slider: one tick per advisory, bars show how many assets are High / Critical,
// markers for the first alerts, the incident room opening and the peak. Click a tick or press play.
export default function Timeline() {
  const { advisories, risks, index, setIndex, playing, togglePlay, step } = useStore()

  useEffect(() => {
    if (!playing) return
    const t = setInterval(step, STEP_MS)
    return () => clearInterval(t)
  }, [playing, step])

  if (!advisories.length) return null
  const counts = advisories.map((a) => risks[a.advisory]?.tiers.standard ?? { Critical: 0, High: 0, Medium: 0, Low: 0 })
  const load = counts.map((c) => c.Critical * 2 + c.High)
  const maxLoad = Math.max(1, ...load)
  const peak = load.indexOf(Math.max(...load))
  const firstAlert = counts.findIndex((c) => c.High + c.Critical > 0)
  const roomOpens = counts.findIndex((c) => c.Critical > 0)
  const pct = (i: number) => `${(i / (advisories.length - 1)) * 100}%`

  const markers = [
    { i: firstAlert, label: 'First alerts', color: tierColor('High') },
    { i: roomOpens, label: 'Room opens', color: tierColor('Critical') },
    { i: peak, label: 'Peak', color: palette().navy },
  ].filter((m) => m.i >= 0)

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Replay</span>
        <button onClick={togglePlay}
                className="rounded bg-navy px-2.5 py-1 text-xs font-semibold text-white hover:bg-navy/90">
          {playing ? '❚❚ Pause' : '▶ Play'}
        </button>
      </div>

      <div className="relative mx-3 my-5 flex-1">
        {/* track */}
        <div className="absolute bottom-0 left-[116px] top-0 w-1 rounded bg-slate-200" />
        <div className="absolute left-[116px] top-0 w-1 rounded bg-teal transition-all duration-500"
             style={{ height: pct(index) }} />

        {advisories.map((a, i) => (
          <button key={a.advisory} onClick={() => setIndex(i)} title={a.issued_label}
                  className="group absolute left-0 flex w-full -translate-y-1/2 items-center"
                  style={{ top: pct(i) }}>
            <span className={`w-[110px] whitespace-nowrap pr-3 text-right text-[10px] ${i === index ? 'text-teal' : 'text-slate-400'}`}>
              {tickLabel(a.issued_at, advisories[i - 1]?.issued_at)}
            </span>
            <span className={`ml-[3px] h-2 w-2 rounded-full border ${i <= index ? 'border-teal bg-teal' : 'border-slate-300 bg-white'}`} />
            {/* how many assets are at risk at this advisory */}
            <span className="ml-2 h-1.5 rounded-r" style={{
              width: `${(load[i] / maxLoad) * 40}px`,
              background: counts[i].Critical ? tierColor('Critical') : tierColor('High'),
              opacity: load[i] ? 0.8 : 0 }} />
          </button>
        ))}

        {/* current position */}
        <div className="pointer-events-none absolute left-[108px] h-5 w-5 -translate-y-1/2 rounded-full border-4 border-white bg-teal shadow transition-all duration-500"
             style={{ top: pct(index) }} />

        {markers.map((m) => (
          <div key={m.label} className="pointer-events-none absolute right-0 -translate-y-1/2 rounded px-1 text-[9px] font-semibold text-white"
               style={{ top: pct(m.i), background: m.color }}>
            {m.label}
          </div>
        ))}
      </div>

      <div className="border-t border-slate-200 px-3 py-2 text-[10px] leading-snug text-slate-500">
        Advisory {advisories[index].advisory} of {advisories[0].advisory}–{advisories[advisories.length - 1].advisory}
        <br />NHC issues a new advisory every 6 h; re-scoring runs on each one.
      </div>
    </aside>
  )
}

// First tick of each day: "27 Sept 2022"; later ticks that day: "21:00" (UTC)
function tickLabel(iso: string, prevIso?: string) {
  const d = new Date(iso)
  const time = `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`
  if (prevIso && new Date(prevIso).getUTCDate() === d.getUTCDate()) return time
  const month = d.toLocaleString('en-GB', { month: 'short', timeZone: 'UTC' })
  return `${d.getUTCDate()} ${month} ${d.getUTCFullYear()} · ${time}`
}
