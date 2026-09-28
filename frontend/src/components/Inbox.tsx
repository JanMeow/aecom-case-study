import { useEffect, useState } from 'react'
import { alertKey, formatTime, useCurrent, useStore } from '../store'
import type { Alert } from '../types'
import TierBadge from './TierBadge'

// Messages the alert rules have sent up to the current replay time. "Mine" = sent to the logged-in user.
export default function Inbox() {
  const { user, read, markRead, select, setView, openAlert: requested } = useStore()
  const { alerts } = useCurrent()
  const [scope, setScope] = useState<'mine' | 'all'>('mine')
  const [openKey, setOpenKey] = useState<string | null>(requested)   // e.g. clicked from a notification
  useEffect(() => { if (requested) setOpenKey(requested) }, [requested])

  const all = [...(alerts?.alerts ?? [])].reverse() // newest first
  const list = scope === 'mine' ? all.filter((a) => a.recipients.some((r) => r.employee_id === user?.employee_id)) : all
  const open = list.find((a) => alertKey(a) === openKey) ?? null

  const openAlert = (a: Alert) => { setOpenKey(alertKey(a)); markRead(alertKey(a)) }

  return (
    <div className="flex h-full bg-slate-50">
      <div className="flex w-[26rem] shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-200 p-3">
          <span className="font-semibold text-navy">Inbox</span>
          <div className="ml-auto flex overflow-hidden rounded border border-slate-300 text-xs">
            {(['mine', 'all'] as const).map((s) => (
              <button key={s} onClick={() => setScope(s)}
                      className={`px-2.5 py-1 ${scope === s ? 'bg-navy text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
                {s === 'mine' ? 'Sent to me' : 'All alerts'}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {list.length === 0 && <div className="p-6 text-sm text-slate-500">No messages yet at this point in the replay.</div>}
          {list.map((a) => {
            const key = alertKey(a)
            return (
              <button key={key} onClick={() => openAlert(a)}
                      className={`block w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${openKey === key ? 'bg-teal/10' : ''}`}>
                <div className="flex items-center gap-2">
                  {!read[key] && <span className="h-2 w-2 rounded-full bg-teal" />}
                  <TierBadge tier={a.tier} />
                  <span className={`text-sm ${read[key] ? 'text-slate-600' : 'font-semibold text-navy'}`}>{a.asset_name}</span>
                  <span className="ml-auto text-[11px] text-slate-400">{formatTime(a.issued_at)}</span>
                </div>
                <div className="mt-1 truncate text-xs text-slate-500">{a.message}</div>
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!open && <div className="text-sm text-slate-500">Select a message.</div>}
        {open && (
          <div className="max-w-2xl space-y-4 rounded border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-2">
              <TierBadge tier={open.tier} />
              <span className="text-lg font-semibold text-navy">{open.asset_name} ({open.asset_id})</span>
            </div>
            <div className="text-xs text-slate-500">
              From: SGW alert rules (automatic) · {formatTime(open.issued_at)} · advisory {open.advisory}
              <br />To: {open.recipients.map((r) => `${r.name} (${r.title})`).join(', ')}
            </div>
            <p className="text-sm">{open.message}</p>
            <div>
              <div className="mb-1 text-xs font-semibold text-slate-500">Why</div>
              <ul className="list-disc space-y-1 pl-4 text-sm text-slate-700">
                {open.reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
            <div className="flex gap-2">
              <button onClick={() => { select(open.asset_id); setView('map') }}
                      className="rounded bg-navy px-3 py-1.5 text-sm text-white">Show on map</button>
              {open.tier === 'Critical' && (
                <button onClick={() => setView('room')} className="rounded bg-tier-critical px-3 py-1.5 text-sm text-white">
                  Go to incident room
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
