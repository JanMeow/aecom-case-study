import { useState } from 'react'
import { formatTime, useCurrent, useStore } from '../store'
import TierBadge from './TierBadge'

// Opens automatically when the first asset reaches Critical. System messages come from the alert rules;
// people can post messages. The AI briefing will appear here once the AI service is connected.
export default function IncidentRoom() {
  const { user, chat, sendChat, select, setView } = useStore()
  const { alerts } = useCurrent()
  const [text, setText] = useState('')
  const room = alerts?.room

  if (!room) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-50 text-center text-sm text-slate-500">
        <div>
          <div className="mb-1 text-base font-semibold text-navy">No incident room yet</div>
          It opens automatically when an asset reaches Critical.<br />Move the replay forward to see it open.
        </div>
      </div>
    )
  }

  const system = (alerts?.alerts ?? []).filter((a) => a.tier === 'Critical')
  const isMember = room.members.some((m) => m.employee_id === user?.employee_id)
  const feed = [
    ...system.map((a) => ({ kind: 'system' as const, at: a.issued_at, a })),
    ...chat.map((c) => ({ kind: 'chat' as const, at: c.at, c })),
  ].sort((x, y) => x.at.localeCompare(y.at))

  return (
    <div className="flex h-full bg-slate-50">
      <div className="flex flex-1 flex-col">
        <div className="border-b border-slate-200 bg-white px-5 py-3">
          <div className="font-semibold text-navy">Hurricane Ian incident room</div>
          <div className="text-xs text-slate-500">
            Opened {formatTime(room.opened_at)} by advisory {room.opened_by_advisory} · trigger {room.trigger_asset}
            {!isMember && ' · you are viewing, not a member'}
          </div>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          {feed.map((item) => item.kind === 'system' ? (
            <div key={`s-${item.a.asset_id}`} className="rounded border border-red-200 bg-red-50 p-3 text-sm">
              <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
                <span className="font-semibold text-tier-critical">Alert rules</span>{formatTime(item.at)}
              </div>
              <div className="flex items-center gap-2">
                <TierBadge tier="Critical" />
                <button onClick={() => { select(item.a.asset_id); setView('map') }} className="font-semibold text-navy hover:underline">
                  {item.a.asset_name} ({item.a.asset_id})
                </button>
              </div>
              <div className="mt-1 text-slate-700">{item.a.message}</div>
              <div className="mt-1 text-xs text-slate-500">Added: {item.a.recipients.map((r) => r.name).join(', ')}</div>
            </div>
          ) : (
            <div key={item.c.id} className={`flex ${item.c.author.employee_id === user?.employee_id ? 'justify-end' : ''}`}>
              <div className="max-w-lg rounded-lg bg-white p-3 text-sm shadow-sm">
                <div className="mb-1 text-xs text-slate-500"><b className="text-navy">{item.c.author.name}</b> · {formatTime(item.at)}</div>
                {item.c.text}
              </div>
            </div>
          ))}
          <div className="rounded border border-dashed border-teal/50 bg-white p-3 text-xs text-slate-500">
            <b className="text-teal">AI assistant</b> · a cited briefing and draft incident report will be posted here
            (not connected yet).
          </div>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); sendChat(text); setText('') }}
              className="flex gap-2 border-t border-slate-200 bg-white p-3">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message as ${user?.name ?? ''}…`}
                 className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal" />
          <button className="rounded bg-navy px-4 text-sm font-semibold text-white">Send</button>
        </form>
      </div>

      <aside className="w-72 shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-4 text-sm">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Critical assets</div>
        <div className="mb-4 flex flex-wrap gap-1">
          {room.critical_assets.map((id) => (
            <button key={id} onClick={() => { select(id); setView('map') }}
                    className="rounded bg-red-50 px-1.5 py-0.5 text-xs text-tier-critical hover:bg-red-100">{id}</button>
          ))}
        </div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Members ({room.members.length})</div>
        {room.members.map((m) => (
          <div key={m.employee_id} className="mb-2">
            <div className="font-medium text-navy">{m.name}{m.employee_id === user?.employee_id && ' (you)'}</div>
            <div className="text-xs text-slate-500">{m.title} · {m.phone}</div>
          </div>
        ))}
      </aside>
    </div>
  )
}
