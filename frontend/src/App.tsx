import { useEffect } from 'react'
import AssetPanel from './components/AssetPanel'
import AssetTable from './components/AssetTable'
import Header from './components/Header'
import IncidentRoom from './components/IncidentRoom'
import Inbox from './components/Inbox'
import MapView from './components/MapView'
import Notifications from './components/Notifications'
import RoomDock from './components/RoomDock'
import Sidebar from './components/Sidebar'
import Timeline from './components/Timeline'
import { useStore } from './store'

// App shell: header, navigation, replay timeline, the current view, the asset panel when an asset is selected,
// plus notification banners (top right) and the docked incident room (bottom right) on every page
export default function App() {
  const { init, loading, error, view } = useStore()
  useEffect(() => { init() }, [init])

  if (error) return <div className="p-8 text-sm text-red-700">{error}</div>
  if (loading) return <div className="p-8 text-sm text-slate-500">Loading assets, advisories and risk scores…</div>

  return (
    <div className="flex h-full flex-col text-slate-800">
      <Header />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <Timeline />
        <main className="min-w-0 flex-1">
          {view === 'map' && <MapView />}
          {view === 'assets' && <AssetTable />}
          {view === 'inbox' && <Inbox />}
          {view === 'room' && <IncidentRoom />}
        </main>
        {(view === 'map' || view === 'assets') && <AssetPanel />}
      </div>
      <Notifications />
      <RoomDock />
    </div>
  )
}
