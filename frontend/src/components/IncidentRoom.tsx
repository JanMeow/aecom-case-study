import { useEffect, useRef, useState } from 'react'
import { formatTime, useCurrent, useRoomMembers, useStore } from '../store'
import ChatInput from './ChatInput'
import ChatMessageView from './ChatMessageView'
import TierBadge from './TierBadge'

// Opens automatically when the first asset reaches Critical. System messages come from the alert rules;
// people post messages, and the AI answers questions and slash commands (/generate_report, /playbook).
export default function IncidentRoom() {
  const { user, chat, select, setView } = useStore()
  const { alerts } = useCurrent()
  const room = alerts?.room
  const members = useRoomMembers()
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [chat])

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
  const isMember = members.all.some((m) => m.employee_id === user?.employee_id)
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
            <ChatMessageView key={item.c.id} msg={item.c} />
          ))}
          {chat.length === 0 && (
            <div className="rounded border border-dashed border-teal/50 bg-white p-3 text-xs text-slate-500">
              <b className="text-teal">AI assistant</b> · type <code className="text-teal">/ask</code> to ask a question, <code className="text-teal">/generate_report</code> for
              a cited situation briefing (PB-04 §4) or <code className="text-teal">/playbook</code> for playbook guidance.
            </div>
          )}
          <div ref={bottom} />
        </div>

        <ChatInput />
      </div>

      <aside className="w-72 shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-4 text-sm">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Critical assets</div>
        <div className="mb-4 flex flex-wrap gap-1">
          {room.critical_assets.map((id) => (
            <button key={id} onClick={() => { select(id); setView('map') }}
                    className="rounded bg-red-50 px-1.5 py-0.5 text-xs text-tier-critical hover:bg-red-100">{id}</button>
          ))}
        </div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Members ({members.all.length})</span>
          <InviteButton />
        </div>
        {members.all.map((m) => (
          <div key={m.employee_id} className="mb-2">
            <div className="font-medium text-navy">
              {m.name}{m.employee_id === user?.employee_id && ' (you)'}
              {members.invited.includes(m) && <span className="ml-1 rounded bg-slate-100 px-1 text-[10px] font-normal text-slate-500">invited</span>}
            </div>
            <div className="text-xs text-slate-500">{m.title} · {m.phone}</div>
          </div>
        ))}
        <div className="mt-3 text-[11px] text-slate-400">Added automatically by the alert rules; tag anyone with @.</div>
      </aside>
    </div>
  )
}

// Invite someone who isn't in the room yet: searchable list of staff
function InviteButton() {
  const { people, invite } = useStore()
  const { all } = useRoomMembers()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const q = query.toLowerCase()
  const candidates = people
    .filter((p) => !all.some((m) => m.employee_id === p.employee_id))
    .filter((p) => !q || `${p.name} ${p.title} ${p.team}`.toLowerCase().includes(q))

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="rounded bg-navy px-2 py-0.5 text-xs font-semibold text-white">+ Invite</button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 w-72 rounded-lg border border-slate-200 bg-white shadow-xl">
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, role or team…"
                 className="w-full border-b border-slate-100 px-3 py-2 text-sm outline-none" />
          <div className="max-h-72 overflow-y-auto">
            {candidates.length === 0 && <div className="px-3 py-2 text-xs text-slate-400">Everyone matching is already in the room.</div>}
            {candidates.map((p) => (
              <button key={p.employee_id} onClick={() => { invite(p); setOpen(false); setQuery('') }}
                      className="block w-full px-3 py-2 text-left hover:bg-teal/10">
                <div className="text-sm font-medium text-navy">{p.name}</div>
                <div className="text-[11px] text-slate-500">{p.title} · {p.team}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
