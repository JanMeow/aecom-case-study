import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatTime, useStore } from '../store'
import type { ChatMessage, Citation } from '../types'

const TITLES = { answer: 'AI assistant', report: 'Situation briefing · draft', playbook: 'Playbook guidance' }

// One AI message: markdown answer with citation chips. Hovering a chip shows the exact playbook passage
// the API returned for it. Reports carry an Approve button: the AI drafts, a person approves.
export default function AiMessage({ msg, compact = false }: { msg: ChatMessage; compact?: boolean }) {
  const approveReport = useStore((s) => s.approveReport)
  const models = useStore((s) => s.models)
  const modelLabel = models.find((m) => m.id === msg.model)?.label.split(' · ')[0] ?? msg.model
  const byLabel = Object.fromEntries((msg.citations ?? []).map((c) => [c.label, c]))
  // "[PB-02 §7]" -> a link the renderer turns into a chip
  const text = msg.text.replace(/\[(PB-\d{2} §\d+)\]/g, (_, label) => `[${label}](#cite)`)

  return (
    <div className={`rounded-lg border border-teal/40 bg-white shadow-sm ${compact ? 'p-2 text-xs' : 'p-4 text-sm'}`}>
      <div className="mb-1 flex items-center gap-2 text-[11px] text-slate-500">
        <span className="rounded bg-teal px-1.5 py-0.5 font-semibold text-white">AI</span>
        <b className="text-teal">{TITLES[msg.kind ?? 'answer']}</b> · {formatTime(msg.at)}
        {modelLabel && !msg.pending && <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 text-[10px]">{modelLabel}</span>}
      </div>

      {msg.pending ? (
        <div className="flex items-center gap-2 py-1 text-slate-500">
          <span className="h-2 w-2 animate-ping rounded-full bg-teal" />
          {msg.kind === 'report' ? 'Writing the briefing from the data and playbooks (about 30 s)…' : 'Thinking…'}
        </div>
      ) : msg.error ? (
        <div className="text-tier-critical">{msg.text}</div>
      ) : (
        <div className={`prose-sm max-w-none leading-relaxed text-slate-800 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:font-semibold
                         [&_h3]:mt-2 [&_h3]:font-semibold [&_li]:ml-4 [&_li]:list-disc [&_ol>li]:list-decimal [&_p]:my-1.5
                         [&_table]:my-2 [&_table]:text-xs [&_td]:border [&_td]:border-slate-200 [&_td]:px-2 [&_td]:py-1
                         [&_th]:border [&_th]:border-slate-200 [&_th]:bg-slate-50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left`}>
          <Markdown remarkPlugins={[remarkGfm]}
                    components={{ a: ({ children, href }) => href === '#cite'
                      ? <CitationChip label={String(children)} citation={byLabel[`[${String(children)}]`]} />
                      : <a href={href} className="text-teal underline">{children}</a> }}>
            {text}
          </Markdown>
        </div>
      )}

      {msg.kind === 'report' && !msg.pending && !msg.error && (
        <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-2 text-xs">
          {msg.approved ? (
            <span className="rounded bg-green-50 px-2 py-1 font-semibold text-green-800">
              ✓ Approved by {msg.approved.by} · {formatTime(msg.approved.at)}
            </span>
          ) : (
            <>
              <span className="text-slate-500">Draft, not sent. Review before it goes to leadership.</span>
              <button onClick={() => approveReport(msg.id)} className="ml-auto rounded bg-navy px-3 py-1 font-semibold text-white">
                Approve
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function CitationChip({ label, citation }: { label: string; citation?: Citation }) {
  return (
    <span className="group relative mx-0.5 inline-block cursor-help align-baseline">
      <span className="rounded bg-teal/10 px-1 py-0.5 text-[10px] font-semibold text-teal">{label}</span>
      {citation && (
        <span className="pointer-events-none absolute left-0 top-full z-50 mt-1 hidden w-80 whitespace-pre-line rounded-lg border border-slate-200 bg-white p-2 text-[11px] font-normal leading-snug text-slate-700 shadow-xl group-hover:block">
          <b className="text-navy">[{label}] quoted from the playbook</b>{'\n'}{citation.cited_text}
        </span>
      )}
    </span>
  )
}
