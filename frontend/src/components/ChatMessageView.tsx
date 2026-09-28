import type { ReactNode } from 'react'
import { formatTime, useStore } from '../store'
import type { ChatMessage } from '../types'
import AiMessage from './AiMessage'

// One message in the incident room: a room event (e.g. an invite), a person's message (right if it's you,
// with @mentions highlighted), or an AI reply
export default function ChatMessageView({ msg, compact = false }: { msg: ChatMessage; compact?: boolean }) {
  const { user, people } = useStore()
  if (msg.role === 'ai') return <AiMessage msg={msg} compact={compact} />
  if (msg.role === 'system') {
    return <div className="text-center text-[11px] text-slate-500">{msg.text} · {formatTime(msg.at)}</div>
  }

  const mine = msg.author?.employee_id === user?.employee_id
  const mentionsMe = !!user && msg.text.includes(`@${user.name}`) && !mine
  return (
    <div className={`flex ${mine ? 'justify-end' : ''}`}>
      <div className={`max-w-lg rounded-lg shadow-sm ${mentionsMe ? 'border border-teal bg-teal/5' : 'bg-white'} ${compact ? 'p-2 text-xs' : 'p-3 text-sm'}`}>
        <div className="mb-1 text-[10px] text-slate-500">
          <b className="text-navy">{msg.author?.name}</b> · {formatTime(msg.at)}
          {mentionsMe && <span className="ml-1 font-semibold text-teal">· mentioned you</span>}
        </div>
        <span className={msg.text.startsWith('/') ? 'font-mono text-teal' : ''}>
          {highlightMentions(msg.text, people.map((p) => p.name))}
        </span>
      </div>
    </div>
  )
}

// "@Mei Chen can you check PS-007" -> [<b>@Mei Chen</b>, " can you check PS-007"]
function highlightMentions(text: string, names: string[]): ReactNode[] {
  if (!names.length) return [text]
  const pattern = new RegExp(`(@(?:${names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')}))`, 'g')
  return text.split(pattern).map((part, i) =>
    part.startsWith('@') && names.includes(part.slice(1))
      ? <span key={i} className="rounded bg-teal/15 px-1 font-semibold text-teal">{part}</span>
      : part)
}
