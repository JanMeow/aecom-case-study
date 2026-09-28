import { alertKey, useCurrent, useStore } from '../store'
import type { View } from '../types'

const ITEMS: { view: View; label: string; icon: string }[] = [
  { view: 'map', label: 'Map', icon: '🗺' },
  { view: 'assets', label: 'Assets', icon: '▦' },
  { view: 'inbox', label: 'Inbox', icon: '✉' },
  { view: 'room', label: 'Incident room', icon: '💬' },
]

// Left navigation, with unread count on Inbox and a dot when the incident room is open
export default function Sidebar() {
  const { view, setView, user, read } = useStore()
  const { alerts } = useCurrent()
  const mine = (alerts?.alerts ?? []).filter((a) => a.recipients.some((r) => r.employee_id === user?.employee_id))
  const unread = mine.filter((a) => !read[alertKey(a)]).length
  const roomOpen = !!alerts?.room

  return (
    <nav className="flex w-20 shrink-0 flex-col items-center gap-1 border-r border-slate-200 bg-white py-3">
      {ITEMS.map((item) => (
        <button key={item.view} onClick={() => setView(item.view)}
                className={`relative flex w-16 flex-col items-center gap-1 rounded-lg py-2 text-[11px] ${
                  view === item.view ? 'bg-slate-100 font-semibold text-navy' : 'text-slate-500 hover:bg-slate-50'}`}>
          <span className="text-lg leading-none">{item.icon}</span>
          {item.label}
          {item.view === 'inbox' && unread > 0 && (
            <span className="absolute right-1 top-1 rounded-full bg-tier-critical px-1.5 text-[10px] font-semibold text-white">
              {unread}
            </span>
          )}
          {item.view === 'room' && roomOpen && (
            <span className="absolute right-3 top-2 h-2.5 w-2.5 animate-pulse rounded-full bg-tier-critical" />
          )}
        </button>
      ))}
    </nav>
  )
}
