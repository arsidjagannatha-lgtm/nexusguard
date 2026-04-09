import { useEffect, useState } from 'react'
import { Search, Plus, UserX, ChevronDown, RefreshCw } from 'lucide-react'
import api from '../utils/api'

interface User {
  id: string; email: string; first_name: string; last_name: string
  identity_class: string; organization: string; status: string
  risk_tier: string; current_risk_score: number; last_login: string | null
  contract_expires_at: string | null; created_at: string
}

const RISK_BADGE: Record<string, string> = {
  critical: 'badge-critical', high: 'badge-high',
  medium:   'badge-medium',  low:  'badge-low', minimal: 'badge-low'
}

const STATUS_BADGE: Record<string, string> = {
  active: 'badge-low', pending: 'badge-info',
  suspended: 'badge-high', deprovisioned: 'badge-critical', expired: 'badge-medium'
}

function RiskBar({ score }: { score: number }) {
  const color = score >= 85 ? '#ef4444' : score >= 70 ? '#f97316' : score >= 45 ? '#eab308' : '#22c55e'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div style={{ width: `${score}%`, background: color }} className="h-full rounded-full transition-all" />
      </div>
      <span className="text-xs tabular-nums text-slate-300">{Math.round(score)}</span>
    </div>
  )
}

export default function UsersPage() {
  const [users, setUsers]     = useState<User[]>([])
  const [search, setSearch]   = useState('')
  const [filter, setFilter]   = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const params: any = { limit: 100 }
      if (search.length >= 2) params.search = search
      if (filter) params.risk_tier = filter
      const res = await api.get('/users/', { params })
      setUsers(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUsers() }, [search, filter])

  const deprovision = async (userId: string, email: string) => {
    if (!confirm(`Deprovision ${email}? This will revoke all access immediately.`)) return
    await api.delete(`/users/${userId}/deprovision?reason=Manual+admin+action`)
    fetchUsers()
  }

  return (
    <div className="space-y-5 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">External Identities</h1>
          <p className="text-sm text-slate-400 mt-0.5">{users.length} identities found</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchUsers} className="btn-ghost px-2.5 py-2">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowAdd(true)} className="btn-primary">
            <Plus size={14} /> Add Identity
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            className="input-field pl-9 py-2"
            placeholder="Search identities..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="relative">
          <select
            className="input-field pr-8 py-2 appearance-none cursor-pointer"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          >
            <option value="">All Risk Tiers</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800/60">
              {['Identity', 'Class', 'Organization', 'Risk Score', 'Status', 'Contract Expiry', 'Actions'].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[11px] font-medium text-slate-500 uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-4 h-4 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
                    Loading...
                  </div>
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-500">No identities found</td>
              </tr>
            ) : users.map(user => (
              <tr key={user.id} className="table-row">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-full bg-brand-600/20 border border-brand-500/20 flex items-center justify-center text-[11px] font-semibold text-brand-400">
                      {user.first_name[0]}{user.last_name[0]}
                    </div>
                    <div>
                      <div className="text-slate-200 font-medium text-[13px]">{user.first_name} {user.last_name}</div>
                      <div className="text-slate-500 text-[11px] font-mono">{user.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="badge-info text-[10px]">{user.identity_class}</span>
                </td>
                <td className="px-4 py-3 text-slate-400 text-[13px]">{user.organization}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-col gap-1">
                    <span className={RISK_BADGE[user.risk_tier] ?? 'badge-info'}>{user.risk_tier}</span>
                    <RiskBar score={user.current_risk_score} />
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={STATUS_BADGE[user.status] ?? 'badge-info'}>{user.status}</span>
                </td>
                <td className="px-4 py-3 text-[12px] text-slate-400">
                  {user.contract_expires_at
                    ? new Date(user.contract_expires_at).toLocaleDateString()
                    : <span className="text-slate-600">—</span>
                  }
                </td>
                <td className="px-4 py-3">
                  {user.status === 'active' && (
                    <button
                      onClick={() => deprovision(user.id, user.email)}
                      className="btn-danger px-2.5 py-1.5 text-[11px]"
                    >
                      <UserX size={12} /> Deprovision
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add User Modal */}
      {showAdd && <AddUserModal onClose={() => setShowAdd(false)} onSuccess={fetchUsers} />}
    </div>
  )
}

function AddUserModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({
    email: '', first_name: '', last_name: '',
    identity_class: 'vendor', organization: '', business_justification: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    setLoading(true); setError('')
    try {
      await api.post('/users/', form)
      onSuccess(); onClose()
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Failed to create user')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-md p-6 space-y-4 animate-slide-up">
        <h2 className="text-base font-semibold text-white">Onboard External Identity</h2>
        {error && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">{error}</div>}
        {[
          { label: 'Email', key: 'email', type: 'email' },
          { label: 'First Name', key: 'first_name', type: 'text' },
          { label: 'Last Name', key: 'last_name', type: 'text' },
          { label: 'Organization', key: 'organization', type: 'text' },
        ].map(({ label, key, type }) => (
          <div key={key}>
            <label className="text-xs text-slate-400 mb-1 block">{label}</label>
            <input className="input-field" type={type} value={(form as any)[key]}
              onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
          </div>
        ))}
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Identity Class</label>
          <select className="input-field" value={form.identity_class}
            onChange={e => setForm(f => ({ ...f, identity_class: e.target.value }))}>
            {['vendor', 'partner', 'contractor', 'customer', 'b2b_admin', 'auditor'].map(c =>
              <option key={c} value={c}>{c}</option>
            )}
          </select>
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="btn-ghost flex-1 justify-center">Cancel</button>
          <button onClick={submit} disabled={loading} className="btn-primary flex-1 justify-center">
            {loading ? 'Creating...' : 'Onboard Identity'}
          </button>
        </div>
      </div>
    </div>
  )
}
