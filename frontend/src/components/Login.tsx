import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../api'
import { useStore } from '../store'
import type { Person } from '../types'

// Demo sign-in accounts shown for one-click login (the story's main people)
const DEMO = ['E1007', 'E1002', 'E1001', 'E1013', 'E1003']

// Fake login page: any password works; the email picks the staff member from the HR directory.
// Production would use SGW single sign-on (e.g. Microsoft Entra ID).
export default function Login() {
  const { login } = useStore()
  const navigate = useNavigate()
  const [people, setPeople] = useState<Person[]>([])
  const [email, setEmail] = useState('hcole@sgw.example')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { api.people().then(setPeople).catch(() => setError('Cannot reach the backend on port 8000.')) }, [])

  const signIn = (person?: Person) => {
    const who = person ?? people.find((p) => p.email.toLowerCase() === email.trim().toLowerCase())
    if (!who) { setError('No SGW account with that email.'); return }
    login(who)
    navigate('/', { replace: true })
  }
  const demo = DEMO.map((id) => people.find((p) => p.employee_id === id)).filter(Boolean) as Person[]

  return (
    <div className="flex h-full bg-slate-50">
      <div className="hidden w-1/2 flex-col justify-between bg-navy p-12 text-white lg:flex">
        <div className="text-lg font-semibold tracking-wide">Southeastern Grid &amp; Water</div>
        <div>
          <div className="text-4xl font-semibold leading-tight">SGW Resilience Platform</div>
          <p className="mt-4 max-w-md text-white/70">
            One live picture of power and water assets in a storm: risk scores, alerts to the right people,
            and an AI-assisted incident room.
          </p>
        </div>
        <div className="text-xs text-white/50">Internal use only · Demo with mocked company data and real Hurricane Ian (2022) advisories</div>
      </div>

      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-sm space-y-6">
          <div>
            <div className="text-2xl font-semibold text-navy">Sign in</div>
            <div className="text-sm text-slate-500">Use your SGW account</div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); signIn() }} className="space-y-3">
            <label className="block text-sm">
              <span className="text-slate-600">Work email</span>
              <input value={email} onChange={(e) => { setEmail(e.target.value); setError('') }}
                     className="mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal" />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600">Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="any password (demo)"
                     className="mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal" />
            </label>
            {error && <div className="text-sm text-tier-critical">{error}</div>}
            <button className="w-full rounded bg-navy py-2 font-semibold text-white hover:bg-navy/90">Sign in</button>
            <button type="button" onClick={() => signIn()}
                    className="w-full rounded border border-slate-300 bg-white py-2 text-sm text-slate-700 hover:bg-slate-50">
              Sign in with SGW single sign-on
            </button>
          </form>

          {demo.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Demo accounts</div>
              <div className="space-y-1">
                {demo.map((p) => (
                  <button key={p.employee_id} onClick={() => signIn(p)}
                          className="flex w-full items-center gap-3 rounded border border-slate-200 bg-white px-3 py-2 text-left hover:border-teal">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal text-xs font-semibold text-white">
                      {p.name.split(' ').map((w) => w[0]).join('')}
                    </span>
                    <span>
                      <span className="block text-sm font-medium text-navy">{p.name}</span>
                      <span className="block text-xs text-slate-500">{p.title} · {p.team}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="text-[11px] text-slate-400">Demo only: no real authentication. Production uses SGW single sign-on.</div>
        </div>
      </div>
    </div>
  )
}
