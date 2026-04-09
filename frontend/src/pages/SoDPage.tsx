import { useEffect, useState } from 'react'
import { AlertTriangle, ShieldCheck, RefreshCw } from 'lucide-react'
import api from '../utils/api'

interface Violation {
  id: string; user_id: string; sod_rule_id: string
  severity: string; status: string; detected_at: string; remediated_at: string | null
}

interface Summary { total_open: number; by_severity: Record<string, number>; requires_immediate_action: number }

const SEV_BADGE: Record<string, string> = {
  critical: 'badge-critical', high: 'badge-high', medium: 'badge-medium', low: 'badge-low'
}
const STATUS_BADGE: Record<string, string> = {
  open: 'badge-critical', mitigated: 'badge-medium',
  accepted: 'badge-high', remediated: 'badge-low', false_positive: 'badge-info'
}

export default function SoDPage() {
  const [violations, setViolations] = useState<Violation[]>([])
  const [summary, setSummary]       = useState<Summary | null>(null)
  const [loading, setLoading]       = useState(true)
  const [filter, setFilter]         = useState<string>('')

  const fetch = async () => {
    setLoading(true)
    const [v, s] = await Promise.all([
      api.get('/sod/violations', { params: filter ? { status: filter } : {} }),
      api.get('/sod/violations/summary'),
    ])
    setViolations(v.data)
    setSummary(s.data)
    setLoading(false)
  }

  const remediate = async (id: string, action: string) => {
    const reason = prompt(`${action} reason:`) ?? 'Admin action'
    await api.post(`/sod/violations/${id}/remediate`, { action, reason })
    fetch()
  }

  useEffect(() => { fetch() }, [filter])

  return (
    <div className="space-y-5 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">SoD Violations</h1>
          <p className="text-sm text-slate-400 mt-0.5">Segregation of Duties conflict detection</p>
        </div>
        <button onClick={fetch} className="btn-ghost px-2.5 py-2">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Open Violations', value: summary.total_open, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
            { label: 'Critical', value: summary.by_severity.critical ?? 0, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
            { label: 'High', value: summary.by_severity.high ?? 0, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20' },
            { label: 'Needs Action', value: summary.requires_immediate_action, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20' },
          ].map(({ label, value, color, bg }) => (
            <div key={label} className={`card p-4 border ${bg}`}>
              <div className={`text-2xl font-semibold ${color} tabular-nums`}>{value}</div>
              <div className="text-xs text-slate-400 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {['', 'open', 'mitigated', 'accepted', 'remediated'].map(s => (
          <button
            key={s || 'all'}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all
              ${filter === s ? 'bg-brand-600/30 text-brand-400 border border-brand-500/40'
                             : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-slate-700/40'}`}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800/60">
              {['User', 'Rule', 'Severity', 'Status', 'Detected', 'Actions'].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[11px] font-medium text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-500 text-sm">Loading...</td></tr>
            ) : violations.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center">
                  <ShieldCheck size={32} className="text-green-500/40 mx-auto mb-2" />
                  <p className="text-slate-400 text-sm">No violations found</p>
                </td>
              </tr>
            ) : violations.map(v => (
              <tr key={v.id} className="table-row">
                <td className="px-4 py-3 text-xs font-mono text-slate-400">{v.user_id.slice(0, 8)}…</td>
                <td className="px-4 py-3 text-xs font-mono text-slate-400">{v.sod_rule_id.slice(0, 8)}…</td>
                <td className="px-4 py-3"><span className={SEV_BADGE[v.severity] ?? 'badge-info'}>{v.severity}</span></td>
                <td className="px-4 py-3"><span className={STATUS_BADGE[v.status] ?? 'badge-info'}>{v.status}</span></td>
                <td className="px-4 py-3 text-xs text-slate-500">{new Date(v.detected_at).toLocaleDateString()}</td>
                <td className="px-4 py-3">
                  {v.status === 'open' && (
                    <div className="flex gap-1.5">
                      <button onClick={() => remediate(v.id, 'remediate')} className="btn-primary px-2 py-1 text-[11px]">Remediate</button>
                      <button onClick={() => remediate(v.id, 'accept')} className="btn-ghost px-2 py-1 text-[11px]">Accept</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
