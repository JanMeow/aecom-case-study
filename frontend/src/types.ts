// TypeScript versions of the backend models (backend/src/backend/ETL/model.py and api/model.py)
import type { Feature } from 'geojson'

export type Tier = 'Low' | 'Medium' | 'High' | 'Critical'
export type Mode = 'standard' | 'ml'
export type View = 'map' | 'assets' | 'inbox' | 'room'

export interface Location { lat: number; lon: number }

export interface Person {
  employee_id: string
  name: string
  title: string
  team: string
  email: string
  phone: string
}

export interface AssetSummary {
  asset_id: string
  name: string
  type: string
  region: string
  location: Location
  path: [number, number][] | null   // (lon, lat) route, transmission lines only
  upstream: string[]                 // asset IDs it depends on
  downstream: string[]               // asset IDs that depend on it
}

export interface CriticalFacility { facility_id: string; name: string; kind: string; via: string }
export interface HistoryItem { date: string; wo_no: string; type: string; summary: string; storm_event: string; cost_usd: number }

export interface AssetDetail extends Omit<AssetSummary, 'upstream' | 'downstream'> {
  elevation_m: number
  flood_zone: string
  install_year: number
  customers_served: number
  condition_rating: number | null
  has_backup_power: boolean
  backup_hours: number
  owner: Person | null
  upstream: { asset_id: string; type: string }[]
  downstream: string[]
  critical_facilities: CriticalFacility[]
  history: HistoryItem[]
  sources: string[]
}

export interface RiskResult {
  asset_id: string
  mode: 'rules' | 'ml'
  score: number
  tier: Tier
  wind_zone_kt: number
  forecast: boolean
  own_chance: number
  depends_on: string | null
  likelihood: number
  customers_affected: number
  critical_facilities: string[]
  consequence: number
  reasons: string[]
}

export interface AssetRisk {
  asset_id: string
  standard: RiskResult
  ml: RiskResult
  field_status: string | null
}

export interface RiskResponse {
  advisory: number
  issued_at: string
  tiers: Record<Mode, Record<Tier, number>>
  results: AssetRisk[]
}

export interface AdvisorySummary {
  advisory: number
  issued_at: string
  issued_label: string
  center: Location
  max_wind_kt: number
  category: number
  storm_type: string
}

export interface AdvisoryMap {
  type: 'FeatureCollection'
  properties: AdvisorySummary
  features: Feature[]
}

export interface Alert {
  advisory: number
  issued_at: string
  asset_id: string
  asset_name: string
  tier: Tier
  action: 'notify_owner' | 'open_room' | 'join_room'
  recipients: Person[]
  message: string
  reasons: string[]
}

export interface IncidentRoom {
  opened_at: string
  opened_by_advisory: number
  trigger_asset: string
  critical_assets: string[]
  members: Person[]
}

export interface AlertsResponse {
  advisory: number
  mode: Mode
  alerts: Alert[]
  room: IncidentRoom | null
}

export interface Citation {
  playbook_id: string
  section: string
  label: string        // "[PB-02 §7]"
  cited_text: string   // exact passage from the playbook (returned by the API)
}

export interface CitedAnswer {
  text: string         // markdown, with [PB-xx §n] labels after cited parts
  citations: Citation[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'ai' | 'system'   // system: room events such as an invite
  author: Person | null          // null for the AI
  text: string
  at: string                     // replay time the message was sent at
  kind?: 'answer' | 'report' | 'playbook'   // AI messages: which command produced it
  citations?: Citation[]
  pending?: boolean              // AI is still working on it
  error?: boolean
  approved?: { by: string; at: string }     // reports: approved by a person
}

// Tree canopy around an asset from satellite imagery (POST /cv/tree_canopy_pct)
export interface CanopyResult {
  asset_id: string
  gis_tree_canopy_pct: number | null   // what the GIS record says
  green_pct: number                    // measured from pixel colours; includes grass
  threshold: number
  ai: { tree_canopy_pct: number; confidence: 'low' | 'medium' | 'high'; notes: string }
  image: string                        // data URL
  mask: string                         // data URL, counted green pixels highlighted
  size_m: number
  attribution: string
}
