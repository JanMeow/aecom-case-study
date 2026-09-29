import { useState } from 'react'
import { COMMANDS } from '../commands'
import { useRoomMembers, useStore } from '../store'

interface Item { key: string; label: string; sub: string; mono?: boolean }

// Message box for the incident room, with one pop-up menu:
//   "/" at the start  -> AI commands (like Claude's slash commands)
//   "@" in a word     -> room members, to tag someone
//   "/model "         -> the AI models to switch to
// Arrows to move, Tab / Enter to pick, Esc to close. Plain text goes to the people in the room only.
export default function ChatInput({ compact = false }: { compact?: boolean }) {
  const { user, sendChat, models, model: current } = useStore()
  const { all: members } = useRoomMembers()
  const [text, setText] = useState('')
  const [active, setActive] = useState(0)
  const [menuClosed, setMenuClosed] = useState(false)

  // what the menu should show for the text typed so far
  const command = text.startsWith('/') && !text.includes(' ')
  const modelPick = text.match(/^\/model\s+(\S*)$/)
  const mention = !command && !modelPick ? text.match(/(?:^|\s)@(\w*)$/) : null
  const items: Item[] = modelPick
    ? models.some((m) => m.id === modelPick[1]) ? []            // already a full model name: Enter sends it
    : models.filter((m) => m.id.includes(modelPick[1].toLowerCase()))
        .map((m) => ({ key: m.id, label: m.id, sub: m.label + (m.id === current ? ' · current' : ''), mono: true }))
    : command
    ? COMMANDS.filter((c) => c.name.startsWith(text.toLowerCase()))
        .map((c) => ({ key: c.name, label: c.usage, sub: c.description, mono: true }))
    : mention
      ? members.filter((m) => m.employee_id !== user?.employee_id)
          .filter((m) => m.name.toLowerCase().split(' ').some((w) => w.startsWith(mention[1].toLowerCase())))
          .map((m) => ({ key: m.name, label: `@${m.name}`, sub: `${m.title} · ${m.team}` }))
      : []
  const showMenu = items.length > 0 && !menuClosed

  const pick = (item: Item) => {
    setText(modelPick ? `/model ${item.key}` : command ? `${item.key} ` : text.replace(/@(\w*)$/, `@${item.key} `))
    setMenuClosed(false)
  }
  const send = () => { if (text.trim()) { sendChat(text); setText('') } }

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showMenu) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % items.length) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i - 1 + items.length) % items.length) }
    else if (e.key === 'Tab' || e.key === 'Enter') { e.preventDefault(); pick(items[Math.min(active, items.length - 1)]) }
    else if (e.key === 'Escape') setMenuClosed(true)
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); send() }} className={`relative flex gap-2 border-t border-slate-200 bg-white ${compact ? 'p-2' : 'p-3'}`}>
      {showMenu && (
        <div className="absolute bottom-full left-2 right-2 mb-1 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-100 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            {modelPick ? 'AI models' : command ? 'AI commands' : 'Tag a member'}
          </div>
          {items.map((item, i) => (
            <button type="button" key={item.key} onMouseEnter={() => setActive(i)} onClick={() => pick(item)}
                    className={`block w-full px-3 py-2 text-left ${i === active ? 'bg-teal/10' : ''}`}>
              <div className={`text-xs font-semibold text-navy ${item.mono ? 'font-mono' : ''}`}>{item.label}</div>
              <div className="text-[11px] text-slate-500">{item.sub}</div>
            </button>
          ))}
        </div>
      )}
      <input value={text} onKeyDown={onKey}
             onChange={(e) => { setText(e.target.value); setActive(0); setMenuClosed(false) }}
             placeholder={`Message as ${user?.name ?? ''}… (/ for AI, @ to tag)`}
             className={`flex-1 rounded border border-slate-300 outline-none focus:border-teal ${compact ? 'px-2 py-1.5 text-xs' : 'px-3 py-2 text-sm'}`} />
      <button className={`rounded bg-navy font-semibold text-white ${compact ? 'px-3 text-xs' : 'px-4 text-sm'}`}>Send</button>
    </form>
  )
}
