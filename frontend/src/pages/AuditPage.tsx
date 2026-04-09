import { useEffect, useState } from 'react'
import { Shield, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react'
import api from '../utils/api'

interface AuditEvent {
  id: string; sequence_num: number; category: string; event_type: string
  action: string; outcome: string; actor_email: string; target_email: string
  resource_type: string; resource_id: string; event_hash: string; created_at: string
}

interface IntegrityResult {
  total_events_checked: number; chain_valid: boolean
  broken_links: any[]; integrity_status: string; checked_at: string
}

const CAT_COLORS: Record<string, string> = {
  identity_lifecycle: 'text-brand-400',
  access_change:      'text-yellow-400',
  authentication:     'text-green-400',
  authorization:      'text-blue-400',
  sod_event:          'text-red-400',
  review_action:      'text-purple-400',
  admin_action:       'text-orange-400',
}

export default function AuditPage() {
  const [events, setEvents]       = useState<AuditEvent[]>([])
  const [integrity, setIntegrity] = useState<IntegrityResult | null>(null)
  const [loading, setLoading]     = useState(true)
  const [checking, setChecking]   = useState(false)
  const [category, setCategory]   = useState('')

  const fetchEvents = async () => {
    setLoading(true)
    const params: any = { limit: 100 }
    if (category) params.category = category
    const res = await api.get('/audit/events', { params })
    setEvents(res.data)
    setLoading(false)
  }

  const checkIntegrity = async () => {
    setChecking(true)
    const res = await api.get('/audit/integrity', { params: { limit: 500 } })
    setIntegrity(res.data)
    setChecking(false)
  }

  useEffect(() => { fetchEvents() }, [category])

  return (
    <div className="space-y-5 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Tamper-Evident Audit Log</h1>
          <p className="text-sm text-slate-400 mt-0.5">SHA-256 hash-chained immutable event record</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchEvents} className="btn-ghost px-2.5 py-2">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={checkIntegrity} disabled={checking} className="btn-primary">
            <Shield size={14} /> {checking ? 'Verifying…' : 'Verify Integrity'}
          </button>
        </div>
      </div>

      {/* Integrity status */}
      {integrity && (
        <div className={`card p-4 flex items-start gap-3 border
          ${integrity.chain_valid ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
          {integrity.chain_valid
            ? <CheckCircle size={18} className="text-green-400 mt-0.5 flex-shrink-0" />
            : <AlertCircle size={18} className="text-red-400 mt-0.5 flex-shrink-0" />
          }
          <div>
            <div className={`text-sm font-medium ${integrity.chain_valid ? 'text-green-300' : 'text-red-300'}`}>
              Chain Integrity: {integrity.integrity_status}
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              Verified {integrity.total_events_checked} events ·{' '}
              {integrity.broken_links.length === 0
                ? 'No tampering detected'
                : `${integrity.broken_links.length} broken link(s) detected!`}
            </div>
          </div>
        </div>
      )}

      {/* Category filter */}
      <div className="flex gap-2 flex-wrap">
        {['', 'identity_lifecycle', 'access_change', 'authentication', 'sod_event', 'review_action', 'admin_action'].map(c => (
          <button
            key={c || 'all'}
            onClick={() => setCategory(c)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all
              ${category === c
                ? 'bg-brand-600/30 text-brand-400 border border-brand-500/40'
                : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-slate-700/40'}`}
          >
            {c ? c.replace(/_/g, ' ') : 'All events'}
          </button>
        ))}
      </div>

      {/* Events table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800/60">
              {['#', 'Category', 'Event', 'Action', 'Outcome', 'Actor', 'Target', 'Hash', 'Time'].map(h => (
                <th key={h} className="px-3 py-3 text-left text-[10px] font-medium text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-slate-500 text-sm">Loading audit events…</td></tr>
            ) : events.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-slate-500 text-sm">No audit events</td></tr>
            ) : events.map(e => (
              <tr key={e.id} className="table-row">
                <td className="px-3 py-2.5 text-[11px] text-slate-600 tabular-nums">{e.sequence_num}</td>
                <td className="px-3 py-2.5">
                  <span className={`text-[10px] font-medium ${CAT_COLORS[e.category] ?? 'text-slate-400'}`}>
                    {e.category?.replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-[11px] font-mono text-slate-400">{e.event_type}</td>
                <td className="px-3 py-2.5 text-[11px] text-slate-300">{e.action}</td>
                <td className="px-3 py-2.5">
                  <span className={`text-[10px] font-medium ${e.outcome === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                    {e.outcome}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-[11px] text-slate-500 max-w-[100px] truncate">{e.actor_email || '—'}</td>
                <td className="px-3 py-2.5 text-[11px] text-slate-500 max-w-[100px] truncate">{e.target_email || '—'}</td>
                <td className="px-3 py-2.5">
                  <code className="text-[10px] text-slate-600 font-mono">{e.event_hash}</code>
                </td>
                <td className="px-3 py-2.5 text-[11px] text-slate-500 whitespace-nowrap">
                  {new Date(e.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
