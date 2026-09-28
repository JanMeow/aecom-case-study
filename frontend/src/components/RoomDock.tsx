import { useEffect, useRef } from 'react'
import { formatTime, useCurrent, useRoomMembers, useStore } from '../store'
import ChatInput from './ChatInput'
import ChatMessageView from './ChatMessageView'

// Docked incident room (bottom right, like an email compose window). Shown on every page except the full
// incident room once the room is open. Click the title bar to collapse / expand. Same chat and AI commands.
export default function RoomDock() {
  const { view, setView, dockOpen, setDockOpen, chat } = useStore()
  const { alerts } = useCurrent()
  const room = alerts?.room
  const members = useRoomMembers()
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [chat, dockOpen])
  if (!room || view === 'room') return null

  const system = (alerts?.alerts ?? []).filter((a) => a.tier === 'Critical')
  const feed = [
    ...system.map((a) => ({ kind: 'system' as const, at: a.issued_at, a })),
    ...chat.map((c) => ({ kind: 'chat' as const, at: c.at, c })),
  ].sort((x, y) => x.at.localeCompare(y.at)).slice(-8)

  return (
    <div className="fixed bottom-0 right-6 z-40 w-[26rem] overflow-hidden rounded-t-xl border border-slate-300 bg-white shadow-2xl">
      <div onClick={() => setDockOpen(!dockOpen)}
           className="flex cursor-pointer items-center gap-2 bg-navy px-3 py-2 text-sm text-white">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-tier-critical" />
        <span className="font-semibold">Incident room</span>
        <span className="truncate text-xs text-white/70">
          {room.critical_assets.length} critical · {members.all.length} members
        </span>
        <span className="ml-auto flex items-center gap-1">
          <button onClick={(e) => { e.stopPropagation(); setView('room') }} title="Open full room"
                  className="rounded px-1.5 hover:bg-white/15">⤢</button>
          <span className="px-1">{dockOpen ? '▾' : '▴'}</span>
        </span>
      </div>

      {dockOpen && (
        <>
          <div className="max-h-96 space-y-2 overflow-y-auto bg-slate-50 p-3">
            {feed.map((item) => item.kind === 'system' ? (
              <div key={`s-${item.a.asset_id}`} className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs">
                <div className="mb-0.5 text-[10px] text-slate-500">
                  <b className="text-tier-critical">Alert rules</b> · {formatTime(item.at)}
                </div>
                {item.a.message}
              </div>
            ) : (
              <ChatMessageView key={item.c.id} msg={item.c} compact />
            ))}
            {chat.length === 0 && (
              <div className="rounded-lg border border-dashed border-teal/50 bg-white p-2 text-[11px] text-slate-500">
                <b className="text-teal">AI assistant</b> · type /ask to ask a question, or / for all commands
              </div>
            )}
            <div ref={bottom} />
          </div>
          <ChatInput compact />
        </>
      )}
    </div>
  )
}
