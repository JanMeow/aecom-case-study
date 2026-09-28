import { useState } from 'react'
import { formatTime, useCurrent, useStore } from '../store'

// Docked incident room (bottom right, like an email compose window). Shown on every page except the full
// incident room once the room is open. Click the title bar to collapse / expand.
export default function RoomDock() {
  const { view, setView, dockOpen, setDockOpen, user, chat, sendChat } = useStore()
  const { alerts } = useCurrent()
  const [text, setText] = useState('')
  const room = alerts?.room
  if (!room || view === 'room') return null

  const feed = [
    ...(alerts?.alerts ?? []).filter((a) => a.tier === 'Critical')
      .map((a) => ({ id: `s-${a.asset_id}`, at: a.issued_at, who: 'Alert rules', text: a.message, system: true })),
    ...chat.map((c) => ({ id: c.id, at: c.at, who: c.author.name, text: c.text, system: false })),
  ].sort((x, y) => x.at.localeCompare(y.at)).slice(-6)

  return (
    <div className="fixed bottom-0 right-6 z-40 w-96 overflow-hidden rounded-t-xl border border-slate-300 bg-white shadow-2xl">
      <div onClick={() => setDockOpen(!dockOpen)}
           className="flex cursor-pointer items-center gap-2 bg-navy px-3 py-2 text-sm text-white">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-tier-critical" />
        <span className="font-semibold">Incident room</span>
        <span className="truncate text-xs text-white/70">
          {room.critical_assets.length} critical · {room.members.length} members
        </span>
        <span className="ml-auto flex items-center gap-1">
          <button onClick={(e) => { e.stopPropagation(); setView('room') }} title="Open full room"
                  className="rounded px-1.5 hover:bg-white/15">⤢</button>
          <span className="px-1">{dockOpen ? '▾' : '▴'}</span>
        </span>
      </div>

      {dockOpen && (
        <>
          <div className="max-h-72 space-y-2 overflow-y-auto bg-slate-50 p-3">
            {feed.map((m) => (
              <div key={m.id} className={`rounded-lg p-2 text-xs ${m.system ? 'border border-red-200 bg-red-50' : 'bg-white shadow-sm'}`}>
                <div className="mb-0.5 text-[10px] text-slate-500">
                  <b className={m.system ? 'text-tier-critical' : 'text-navy'}>{m.who}</b> · {formatTime(m.at)}
                </div>
                {m.text}
              </div>
            ))}
            <div className="rounded-lg border border-dashed border-teal/50 bg-white p-2 text-[11px] text-slate-500">
              <b className="text-teal">AI assistant</b> · briefing will appear here (not connected yet)
            </div>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); sendChat(text); setText('') }}
                className="flex gap-2 border-t border-slate-200 p-2">
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message as ${user?.name ?? ''}…`}
                   className="flex-1 rounded border border-slate-300 px-2 py-1.5 text-xs outline-none focus:border-teal" />
            <button className="rounded bg-navy px-3 text-xs font-semibold text-white">Send</button>
          </form>
        </>
      )}
    </div>
  )
}
