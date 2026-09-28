// Incident room slash commands: typing "/" in the message box lists these.
// Plain text is a normal message to the people in the room: only commands call the AI.

export interface Command {
  name: string          // what the user types, e.g. "/generate_report"
  usage: string         // shown in the menu
  description: string
}

export const COMMANDS: Command[] = [
  { name: '/ask', usage: '/ask question',
    description: 'Ask the AI about the current situation (storm, assets at risk, any asset you name)' },
  { name: '/generate_report', usage: '/generate_report [asset]',
    description: 'Situation briefing (PB-04 §4) for an asset; defaults to the one that opened the room' },
  { name: '/playbook', usage: '/playbook [asset] question',
    description: 'What the playbooks say for an asset' },
]

export type Parsed =
  | { kind: 'chat' }                                 // plain message: people only, no AI
  | { kind: 'ask'; question: string }
  | { kind: 'report'; assetId?: string }
  | { kind: 'playbook'; assetId?: string; question: string }

const ASSET_ID = /^[A-Z]{2,4}-\d{3}$/i

// "/playbook PS-007 what now?" -> { kind: 'playbook', assetId: 'PS-007', question: 'what now?' }
export function parseCommand(text: string): Parsed {
  const [first, ...rest] = text.trim().split(/\s+/)
  const assetId = rest[0] && ASSET_ID.test(rest[0]) ? rest[0].toUpperCase() : undefined
  const after = (assetId ? rest.slice(1) : rest).join(' ')
  if (first === '/ask') return { kind: 'ask', question: rest.join(' ') || 'Summarise the situation now.' }
  if (first === '/generate_report') return { kind: 'report', assetId }
  if (first === '/playbook') return { kind: 'playbook', assetId, question: after || 'What should we do for this asset now?' }
  return { kind: 'chat' }
}
