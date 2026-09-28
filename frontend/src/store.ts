// The one state file. Every component reads from here with useStore(...) and calls its actions.
// Server data is fetched once and cached by advisory; UI state (view, selection, timeline) lives next to it.
import { create } from 'zustand'
import { api } from './api'
import type {
  AdvisoryMap, AdvisorySummary, AlertsResponse, AssetDetail, AssetSummary, ChatMessage, Person,
  RiskResponse, Tier, View,
} from './types'

const DEFAULT_USER = 'E1007' // Hannah Cole, T&D Ops South supervisor: owner of SUB-014

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
  chat: ChatMessage[]                          // messages typed in the incident room (local for now)
  dockOpen: boolean                            // docked incident room tab (bottom right) expanded?
  openAlert: string | null                     // alert key to show in the inbox (e.g. clicked from a notification)

  // --- actions
  init: () => Promise<void>
  setView: (view: View) => void
  setUser: (employeeId: string) => void
  setIndex: (index: number) => void
  step: () => void
  togglePlay: () => void
  select: (assetId: string | null) => void
  markRead: (key: string) => void
  sendChat: (text: string) => void
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
    user: null, view: 'map', index: 0, playing: false, selectedId: null, read: {}, chat: [], dockOpen: false, openAlert: null,

    init: async () => {
      try {
        const [people, assets, advisories] = await Promise.all([api.people(), api.assets(), api.advisories()])
        const all = await Promise.all(advisories.map((a) => api.risks(a.advisory)))
        const risks = Object.fromEntries(all.map((r) => [r.advisory, r]))
        set({ people, assets, advisories, risks, user: people.find((p) => p.employee_id === DEFAULT_USER) ?? people[0],
              loading: false })
        await loadCurrent()
      } catch (e) {
        set({ loading: false, error: `Could not reach the backend (${(e as Error).message}). Is it running on port 8000?` })
      }
    },

    setView: (view) => set({ view }),
    setUser: (employeeId) => set((s) => ({ user: s.people.find((p) => p.employee_id === employeeId) ?? s.user })),
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
    sendChat: (text) => {
      const { user, advisories, index } = get()
      if (!user || !text.trim()) return
      const msg = { id: crypto.randomUUID(), author: user, text: text.trim(), at: advisories[index].issued_at }
      set((s) => ({ chat: [...s.chat, msg] }))
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

export const TIER_COLOR: Record<Tier, string> = {
  Low: '#3a9d6e', Medium: '#eab308', High: '#f97316', Critical: '#dc2626',
}

export const formatTime = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit',
                                          minute: '2-digit', timeZone: 'UTC' }) + ' UTC'   // "26 Sept 2022, 03:00 UTC"
