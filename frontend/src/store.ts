// The one state file. Every component reads from here with useStore(...) and calls its actions.
// Server data is fetched once and cached by advisory; UI state (view, selection, timeline) lives next to it.
import { create } from 'zustand'
import { api } from './api'
import { parseCommand } from './commands'
import type {
  AdvisoryMap, AdvisorySummary, AlertsResponse, AssetDetail, AssetSummary, ChatMessage, Person,
  RiskResponse, Tier, View,
} from './types'

// The signed-in user is remembered in this browser (fake login: no real authentication)
const USER_KEY = 'sgw.user'
const savedUser = (): Person | null => {
  try { return JSON.parse(localStorage.getItem(USER_KEY) ?? 'null') } catch { return null }
}
const saveUser = (user: Person | null) => {
  try { user ? localStorage.setItem(USER_KEY, JSON.stringify(user)) : localStorage.removeItem(USER_KEY) } catch { /* storage blocked */ }
}

interface State {
  // --- data from the backend
  loading: boolean
  error: string | null
  people: Person[]
  assets: AssetSummary[]
  advisories: AdvisorySummary[]
  risks: Record<number, RiskResponse>          // advisory -> scores (all prefetched)
  maps: Record<number, AdvisoryMap>            // advisory -> storm GeoJSON (fetched when needed)
  alerts: Record<number, AlertsResponse>       // advisory -> alerts so far (driven by the rules score)
  details: Record<string, AssetDetail>         // asset_id -> full record (fetched when selected)

  // --- UI state
  user: Person | null
  view: View
  index: number                                // position on the timeline (index into advisories)
  playing: boolean
  selectedId: string | null
  read: Record<string, true>                   // alert keys the user has opened
  chat: ChatMessage[]                          // incident room conversation: people and the AI
  invited: Person[]                            // people added to the incident room by hand (on top of the alert rules)
  dockOpen: boolean                            // docked incident room tab (bottom right) expanded?
  openAlert: string | null                     // alert key to show in the inbox (e.g. clicked from a notification)

  // --- actions
  init: () => Promise<void>
  setView: (view: View) => void
  setUser: (employeeId: string) => void
  login: (user: Person) => void
  logout: () => void
  setIndex: (index: number) => void
  step: () => void
  togglePlay: () => void
  select: (assetId: string | null) => void
  markRead: (key: string) => void
  sendChat: (text: string) => Promise<void>
  approveReport: (messageId: string) => void
  invite: (person: Person) => void
  setDockOpen: (open: boolean) => void
  showAlert: (key: string) => void
}

export const alertKey = (a: { advisory: number; asset_id: string; tier: Tier }) => `${a.advisory}-${a.asset_id}-${a.tier}`

export const useStore = create<State>((set, get) => {
  // fetch storm shapes and alerts for the current timeline position, if not cached yet
  const loadCurrent = async () => {
    const { advisories, index, maps, alerts } = get()
    const n = advisories[index]?.advisory
    if (n === undefined) return
    const [map, al] = await Promise.all([
      maps[n] ? Promise.resolve(maps[n]) : api.advisoryMap(n),
      alerts[n] ? Promise.resolve(alerts[n]) : api.alerts(n, 'standard'),  // alerts follow the rules score
    ])
    set((s) => ({ maps: { ...s.maps, [n]: map }, alerts: { ...s.alerts, [n]: al } }))
  }

  return {
    loading: true, error: null, people: [], assets: [], advisories: [], risks: {}, maps: {}, alerts: {}, details: {},
    user: savedUser(), view: 'map', index: 0, playing: false, selectedId: null, read: {}, chat: [], invited: [], dockOpen: false, openAlert: null,

    init: async () => {
      try {
        const [people, assets, advisories] = await Promise.all([api.people(), api.assets(), api.advisories()])
        const all = await Promise.all(advisories.map((a) => api.risks(a.advisory)))
        const risks = Object.fromEntries(all.map((r) => [r.advisory, r]))
        set({ people, assets, advisories, risks, loading: false })
        await loadCurrent()
      } catch (e) {
        set({ loading: false, error: `Could not reach the backend (${(e as Error).message}). Is it running on port 8000?` })
      }
    },

    setView: (view) => set({ view }),
    setUser: (employeeId) => {
      const user = get().people.find((p) => p.employee_id === employeeId) ?? get().user
      saveUser(user)
      set({ user })
    },
    login: (user) => { saveUser(user); set({ user }) },
    logout: () => { saveUser(null); set({ user: null, view: 'map', selectedId: null }) },
    setIndex: (index) => { set({ index: Math.max(0, Math.min(index, get().advisories.length - 1)) }); loadCurrent() },
    step: () => {
      const { index, advisories } = get()
      if (index >= advisories.length - 1) set({ playing: false })
      else get().setIndex(index + 1)
    },
    togglePlay: () => {
      const { playing, index, advisories } = get()
      if (!playing && index >= advisories.length - 1) get().setIndex(0) // restart from the beginning
      set({ playing: !playing })
    },
    select: (assetId) => {
      set({ selectedId: assetId })
      if (assetId && !get().details[assetId]) {
        api.asset(assetId).then((d) => set((s) => ({ details: { ...s.details, [assetId]: d } })))
      }
    },
    markRead: (key) => set((s) => ({ read: { ...s.read, [key]: true } })),
    setDockOpen: (dockOpen) => set({ dockOpen }),
    showAlert: (key) => set((s) => ({ view: 'inbox', openAlert: key, read: { ...s.read, [key]: true } })),
    // Post a message to the incident room. Plain text is for people only; slash commands also get an AI reply
    sendChat: async (text) => {
      const { user, advisories, index, selectedId, alerts } = get()
      if (!user || !text.trim()) return
      const advisory = advisories[index]
      const at = advisory.issued_at
      const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', author: user, text: text.trim(), at }
      const cmd = parseCommand(text)
      if (cmd.kind === 'chat') { set((s) => ({ chat: [...s.chat, userMsg] })); return }   // no AI call
      const kind = cmd.kind === 'ask' ? 'answer' : cmd.kind
      const aiId = crypto.randomUUID()
      const pending: ChatMessage = { id: aiId, role: 'ai', author: null, text: '', at, kind, pending: true }
      set((s) => ({ chat: [...s.chat, userMsg, pending] }))

      const update = (patch: Partial<ChatMessage>) =>
        set((s) => ({ chat: s.chat.map((m) => (m.id === aiId ? { ...m, ...patch, pending: false } : m)) }))
      try {
        let answer
        if (cmd.kind === 'report') answer = await api.report(advisory.advisory, cmd.assetId)
        else if (cmd.kind === 'playbook') {
          const assetId = cmd.assetId ?? selectedId ?? alerts[advisory.advisory]?.room?.trigger_asset
          if (!assetId) throw new Error('Name an asset, e.g. /playbook PS-007 what now?')
          answer = await api.playbook(assetId, cmd.question)
        } else answer = await api.ask(advisory.advisory, cmd.question)
        update({ text: answer.text, citations: answer.citations })
      } catch (e) {
        update({ text: (e as Error).message, error: true })
      }
    },
    invite: (person) => {
      const { user, advisories, index, invited } = get()
      if (!user || invited.some((p) => p.employee_id === person.employee_id)) return
      const note: ChatMessage = { id: crypto.randomUUID(), role: 'system', author: user,
                                  text: `${user.name} invited ${person.name} (${person.title})`, at: advisories[index].issued_at }
      set((s) => ({ invited: [...s.invited, person], chat: [...s.chat, note] }))
    },
    approveReport: (messageId) => {
      const { user, advisories, index } = get()
      if (!user) return
      const approved = { by: user.name, at: advisories[index].issued_at }
      set((s) => ({ chat: s.chat.map((m) => (m.id === messageId ? { ...m, approved } : m)) }))
    },
  }
})

// --- derived values (plain hooks, so components stay small)
export const useCurrent = () => {
  const { advisories, index, risks, maps, alerts } = useStore()
  const advisory = advisories[index]
  const n = advisory?.advisory
  return {
    advisory,
    risk: n !== undefined ? risks[n] : undefined,
    map: n !== undefined ? maps[n] : undefined,
    alerts: n !== undefined ? alerts[n] : undefined,
  }
}

export const formatTime = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit',
                                          minute: '2-digit', timeZone: 'UTC' }) + ' UTC'   // "26 Sept 2022, 03:00 UTC"

// Everyone in the incident room now: added by the alert rules, plus anyone invited by hand
export const useRoomMembers = () => {
  const invited = useStore((s) => s.invited)
  const { alerts } = useCurrent()
  const fromRules = alerts?.room?.members ?? []
  const extra = invited.filter((p) => !fromRules.some((m) => m.employee_id === p.employee_id))
  return { fromRules, invited: extra, all: [...fromRules, ...extra] }
}
