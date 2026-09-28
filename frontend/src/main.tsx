import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import 'maplibre-gl/dist/maplibre-gl.css'
import './index.css'
import App from './App.tsx'
import Login from './components/Login.tsx'
import { useStore } from './store'

// Only signed-in users see the platform; everyone else is sent to the (fake) login page
function RequireLogin({ children }: { children: React.ReactNode }) {
  const user = useStore((s) => s.user)
  return user ? children : <Navigate to="/login" replace />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<RequireLogin><App /></RequireLogin>} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
