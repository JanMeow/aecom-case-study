import type { Feature, FeatureCollection, LineString } from 'geojson'
import { type GeoJSONSource, Map as MapLibreMap, type MapLayerMouseEvent, NavigationControl } from 'maplibre-gl'
import { useEffect, useMemo, useRef, useState } from 'react'
import { TIER_COLOR, useCurrent, useStore } from '../store'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json' // free, no API key
const SERVICE_AREA: [[number, number], [number, number]] = [[-83.3, 26.1], [-81.3, 28.4]]
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }
const DOWN = ['out', 'major_damage'] // field statuses that mean the asset is down

// 2D map: storm (cone, track, wind zones) under the assets.
// Each asset: fill = rules tier; a coloured ring = ML tier, shown only where ML disagrees; a dark halo marks assets
// field crews have reported as down. Click an asset to open its panel.
export default function MapView() {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [ready, setReady] = useState(false)
  const { assets, selectedId, select } = useStore()
  const { advisory, risk, map: storm } = useCurrent()

  // create the map once
  useEffect(() => {
    const map = new MapLibreMap({ container: container.current!, style: BASEMAP, bounds: SERVICE_AREA,
                                  fitBoundsOptions: { padding: 40 },
                                  canvasContextAttributes: { preserveDrawingBuffer: true } }) // lets screenshots capture the map
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => {
      for (const id of ['storm', 'centre', 'deps', 'asset-points', 'asset-lines']) map.addSource(id, { type: 'geojson', data: EMPTY })

      // storm, drawn under the assets
      map.addLayer({ id: 'cone', type: 'fill', source: 'storm', filter: ['==', ['get', 'layer'], 'cone'],
                     paint: { 'fill-color': '#64748b', 'fill-opacity': 0.12 } })
      map.addLayer({ id: 'wind-now', type: 'fill', source: 'storm',
                     filter: ['all', ['==', ['get', 'layer'], 'wind_radii'], ['==', ['get', 'kind'], 'current']],
                     paint: { 'fill-color': ['match', ['get', 'threshold_kt'], 64, '#dc2626', 50, '#f97316', '#eab308'],
                              'fill-opacity': 0.18 } })
      map.addLayer({ id: 'wind-forecast', type: 'line', source: 'storm',
                     filter: ['all', ['==', ['get', 'layer'], 'wind_radii'], ['==', ['get', 'kind'], 'forecast'],
                              ['<=', ['get', 'tau_hours'], 36]],
                     paint: { 'line-color': ['match', ['get', 'threshold_kt'], 64, '#dc2626', 50, '#f97316', '#eab308'],
                              'line-width': 1, 'line-dasharray': [3, 3], 'line-opacity': 0.7 } })
      map.addLayer({ id: 'track', type: 'line', source: 'storm', filter: ['==', ['get', 'layer'], 'track'],
                     paint: { 'line-color': '#0f2b46', 'line-width': 2, 'line-dasharray': [2, 2] } })
      map.addLayer({ id: 'forecast-points', type: 'circle', source: 'storm',
                     filter: ['==', ['get', 'layer'], 'forecast_point'],
                     paint: { 'circle-radius': 3, 'circle-color': '#0f2b46' } })
      map.addLayer({ id: 'centre', type: 'circle', source: 'centre',
                     paint: { 'circle-radius': 9, 'circle-color': '#0f2b46', 'circle-stroke-color': '#fff',
                              'circle-stroke-width': 3 } })

      // dependencies of the selected asset (dotted), drawn under the assets
      map.addLayer({ id: 'deps', type: 'line', source: 'deps', layout: { 'line-cap': 'round' },
                     paint: { 'line-color': ['match', ['get', 'kind'], 'up', '#0f2b46', 'down', '#ea580c', '#ea580c'],
                              'line-width': ['match', ['get', 'kind'], 'indirect', 2, 3.5],
                              'line-opacity': ['match', ['get', 'kind'], 'indirect', 0.45, 0.95],
                              'line-dasharray': [0.5, 2] } })

      // assets
      map.addLayer({ id: 'asset-lines', type: 'line', source: 'asset-lines',
                     paint: { 'line-color': ['get', 'color'], 'line-width': ['case', ['get', 'selected'], 5, 2],
                              'line-opacity': 0.85 } })
      map.addLayer({ id: 'asset-selected', type: 'circle', source: 'asset-points', filter: ['get', 'selected'],
                     paint: { 'circle-radius': 16, 'circle-color': '#0f2b46', 'circle-opacity': 0.25 } })
      map.addLayer({ id: 'asset-down', type: 'circle', source: 'asset-points', filter: ['get', 'down'],
                     paint: { 'circle-radius': 13, 'circle-color': 'transparent', 'circle-stroke-color': '#111827',
                              'circle-stroke-width': 2.5 } })
      map.addLayer({ id: 'asset-points', type: 'circle', source: 'asset-points',
                     paint: { 'circle-radius': ['case', ['get', 'disagree'], 6, 5.5], 'circle-color': ['get', 'color'],
                              // white edge normally; ML tier colour as a ring only when ML disagrees with the rules
                              'circle-stroke-color': ['case', ['get', 'disagree'], ['get', 'mlColor'], '#ffffff'],
                              'circle-stroke-width': ['case', ['get', 'disagree'], 3, 1.5] } })
      map.addLayer({ id: 'asset-labels', type: 'symbol', source: 'asset-points', minzoom: 8.5,
                     layout: { 'text-field': ['get', 'asset_id'], 'text-size': 10, 'text-offset': [0, 1.4] },
                     paint: { 'text-color': '#334155', 'text-halo-color': '#fff', 'text-halo-width': 1 } })

      for (const layer of ['asset-points', 'asset-lines']) {
        map.on('click', layer, (e: MapLayerMouseEvent) => select(String(e.features?.[0]?.properties?.asset_id)))
        map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = '' })
      }
      setReady(true)
    })
    mapRef.current = map
    return () => map.remove()
  }, [select])

  // asset features: fill = rules tier, ring = ML tier
  const assetData = useMemo(() => {
    const byId = Object.fromEntries((risk?.results ?? []).map((r) => [r.asset_id, r]))
    const features = assets.map((a): Feature => {
      const r = byId[a.asset_id]
      const properties = { asset_id: a.asset_id, color: TIER_COLOR[r?.standard.tier ?? 'Low'],
                           mlColor: TIER_COLOR[r?.ml.tier ?? 'Low'], disagree: !!r && r.ml.tier !== r.standard.tier,
                           selected: a.asset_id === selectedId,
                           down: DOWN.includes(r?.field_status ?? '') }
      return a.path
        ? { type: 'Feature', properties, geometry: { type: 'LineString', coordinates: a.path } }
        : { type: 'Feature', properties, geometry: { type: 'Point', coordinates: [a.location.lon, a.location.lat] } }
    })
    return {
      points: { type: 'FeatureCollection', features: features.filter((f) => f.geometry.type === 'Point') },
      lines: { type: 'FeatureCollection', features: features.filter((f) => f.geometry.type === 'LineString') },
    } as const
  }, [assets, risk, selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    ;(map.getSource('asset-points') as GeoJSONSource).setData(assetData.points as FeatureCollection)
    ;(map.getSource('asset-lines') as GeoJSONSource).setData(assetData.lines as FeatureCollection)
  }, [ready, assetData])

  // dotted dependency lines for the selected asset: what it depends on (up), what it supplies (down),
  // and everything further down the chain (indirect) - i.e. what goes down with it
  const depData = useMemo((): FeatureCollection => {
    const byId = Object.fromEntries(assets.map((a) => [a.asset_id, a]))
    const sel = selectedId ? byId[selectedId] : undefined
    if (!sel) return EMPTY
    const at = (id: string) => [byId[id].location.lon, byId[id].location.lat]
    const edge = (from: string, to: string, kind: string): Feature =>
      ({ type: 'Feature', properties: { kind }, geometry: { type: 'LineString', coordinates: [at(from), at(to)] } })
    const features = [
      ...sel.upstream.map((u) => edge(u, sel.asset_id, 'up')),
      ...sel.downstream.map((d) => edge(sel.asset_id, d, 'down')),
    ]
    const seen = new Set([sel.asset_id, ...sel.downstream])
    const todo = [...sel.downstream]
    while (todo.length) {
      const parent = todo.pop()!
      for (const child of byId[parent].downstream) {
        features.push(edge(parent, child, 'indirect'))
        if (!seen.has(child)) { seen.add(child); todo.push(child) }
      }
    }
    return { type: 'FeatureCollection', features }
  }, [assets, selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    ;(map.getSource('deps') as GeoJSONSource).setData(depData)
    // zoom to the selected asset and its dependency network
    const coords = depData.features.flatMap((f) => (f.geometry as LineString).coordinates)
    if (coords.length) {
      const lons = coords.map((c) => c[0]), lats = coords.map((c) => c[1])
      map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
                    { padding: 120, maxZoom: 10.5, duration: 800 })
    }
  }, [ready, depData])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !storm || !advisory) return
    ;(map.getSource('storm') as GeoJSONSource).setData(storm as unknown as FeatureCollection)
    ;(map.getSource('centre') as GeoJSONSource).setData({ type: 'Point', coordinates: [advisory.center.lon, advisory.center.lat] })
  }, [ready, storm, advisory])

  return (
    <div className="relative h-full w-full">
      <div ref={container} className="h-full w-full" />
      <Legend />
      {advisory && (
        <div className="absolute left-3 top-3 rounded bg-white/95 px-3 py-2 text-xs shadow">
          <div className="font-semibold text-navy">Storm centre</div>
          {advisory.center.lat.toFixed(1)}°N {Math.abs(advisory.center.lon).toFixed(1)}°W · {advisory.max_wind_kt} kt
        </div>
      )}
    </div>
  )
}

function Legend() {
  return (
    <div className="absolute bottom-6 left-3 space-y-1.5 rounded bg-white/95 px-3 py-2 text-[11px] text-slate-600 shadow">
      <div className="font-semibold text-navy">Risk tier</div>
      <div className="flex items-center gap-2">
        <span className="h-3.5 w-3.5 rounded-full border-[3px] border-tier-critical bg-tier-high" />Ring = ML disagrees
      </div>
      {(['Critical', 'High', 'Medium', 'Low'] as const).map((t) => (
        <div key={t} className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full" style={{ background: TIER_COLOR[t] }} />{t}
        </div>
      ))}
      <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-slate-900" />Reported down</div>
      <div className="pt-1 font-semibold text-navy">Selected asset</div>
      <div className="flex items-center gap-2"><span className="h-0 w-5 border-t-2 border-dotted border-navy" />Depends on</div>
      <div className="flex items-center gap-2"><span className="h-0 w-5 border-t-2 border-dotted border-orange-600" />Supplies</div>
      <div className="flex items-center gap-2"><span className="h-0 w-5 border-t-2 border-dotted border-orange-600/40" />Knock-on (further down)</div>
      <div className="pt-1 font-semibold text-navy">Wind zone</div>
      <div className="flex items-center gap-2"><span className="h-3 w-5 bg-red-600/30" />Now (34 / 50 / 64 kt)</div>
      <div className="flex items-center gap-2"><span className="h-0 w-5 border-t-2 border-dashed border-red-600" />Forecast ≤ 36 h</div>
    </div>
  )
}
