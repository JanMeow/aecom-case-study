import { useEffect, useRef, useState } from 'react'
import { alertKey, useCurrent, useStore } from '../store'
import type { Alert } from '../types'

const SHOW_MS = 7000   // how long a banner stays up
const MAX_BANNERS = 4

interface Banner { key: string; alert: Alert; kind: 'message' | 'room' }

// macOS-style notification banners (top right, over every page). When the replay moves FORWARD and the
// alert rules send something to the logged-in user, a banner slides in. Moving backwards shows nothing.
export default function Notifications() {
  const { user, showAlert, setView, setDockOpen } = useStore()
  const { advisory, alerts } = useCurrent()
  const [banners, setBanners] = useState<Banner[]>([])
  const seenUpTo = useRef<number | null>(null)   // last advisory we raised banners for

  useEffect(() => {
    if (!advisory || !alerts || alerts.advisory !== advisory.advisory || !user) return
    const last = seenUpTo.current
    seenUpTo.current = advisory.advisory
    if (last === null || advisory.advisory <= last) return   // first load or moving backwards: stay quiet

    const fresh = alerts.alerts.filter((a) => a.advisory > last && a.recipients.some((r) => r.employee_id === user.employee_id))
    if (!fresh.length) return
    if (fresh.some((a) => a.action === 'open_room')) setDockOpen(true)
    const added: Banner[] = fresh.map((a) => ({ key: alertKey(a), alert: a, kind: a.tier === 'Critical' ? 'room' : 'message' }))
    setBanners((b) => [...added.reverse(), ...b].slice(0, MAX_BANNERS))
    const keys = added.map((b) => b.key)
    setTimeout(() => setBanners((b) => b.filter((x) => !keys.includes(x.key))), SHOW_MS)
  }, [advisory, alerts, user, setDockOpen])

  const click = (b: Banner) => {
    setBanners((all) => all.filter((x) => x.key !== b.key))
    if (b.kind === 'room') setView('room')
    else showAlert(b.key)
  }

  return (
    <div className="pointer-events-none fixed right-4 top-16 z-50 flex w-96 flex-col gap-2">
      {banners.map((b) => (
        <button key={b.key} onClick={() => click(b)}
                className="pointer-events-auto flex animate-[slidein_0.35s_ease-out] items-start gap-3 rounded-2xl border border-white/60 bg-white/80 p-3 text-left shadow-2xl backdrop-blur-xl hover:bg-white/90">
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-lg text-white ${
            b.kind === 'room' ? 'bg-tier-critical' : 'bg-tier-high'}`}>{b.kind === 'room' ? '💬' : '✉'}</span>
          <span className="min-w-0 flex-1">
            <span className="flex items-baseline justify-between gap-2">
              <span className="truncate text-[13px] font-semibold text-slate-900">
                {b.kind === 'room'
                  ? (b.alert.action === 'open_room' ? 'Incident room opened' : 'Incident room updated')
                  : `High risk: ${b.alert.asset_name}`}
              </span>
              <span className="shrink-0 text-[11px] text-slate-500">now</span>
            </span>
            <span className="block text-[11px] font-medium text-slate-500">SGW Resilience Platform</span>
            <span className="mt-0.5 line-clamp-2 block text-[12px] leading-snug text-slate-700">{b.alert.message}</span>
          </span>
          <span onClick={(e) => { e.stopPropagation(); setBanners((all) => all.filter((x) => x.key !== b.key)) }}
                className="-mr-1 -mt-1 rounded-full px-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700">✕</span>
        </button>
      ))}
    </div>
  )
}
