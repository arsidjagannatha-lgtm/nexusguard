import { useEffect, useState } from 'react'
import { Plus, CheckCircle, XCircle, ArrowRight, RefreshCw } from 'lucide-react'
import api from '../utils/api'

interface Campaign {
  id: string; name: string; status: string; campaign_type: string
  due_date: string; total_items: number; certified_count: number
  revoked_count: number; completion_rate: number; compliance_standard: string
}

interface ReviewItem {
  id: string; user_id: string; role_id: string | null
  reviewer_id: string; decision: string; risk_score_at_review: number
  decision_at: string | null; justification: string | null
}

const STATUS_COLORS: Record<string, string> = {
  active: 'badge-low', draft: 'badge-info',
  completed: 'badge-medium', paused: 'badge-high', cancelled: 'badge-critical'
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{
          width: `${value}%`,
          background: value >= 80 ? '#22c55e' : value >= 50 ? '#eab308' : '#6366f1'
        }}
      />
    </div>
  )
}

export default function ReviewsPage() {
  const [campaigns, setCampaigns]       = useState<Campaign[]>([])
  const [selectedCampaign, setSelected] = useState<Campaign | null>(null)
  const [items, setItems]               = useState<ReviewItem[]>([])
  const [loading, setLoading]           = useState(true)
  const [itemsLoading, setItemsLoading] = useState(false)
  const [showCreate, setShowCreate]     = useState(false)

  const fetchCampaigns = async () => {
    setLoading(true)
    const res = await api.get('/reviews/campaigns')
    setCampaigns(res.data)
    setLoading(false)
  }

  const loadItems = async (campaign: Campaign) => {
    setSelected(campaign)
    setItemsLoading(true)
    const res = await api.get(`/reviews/campaigns/${campaign.id}/items`)
    setItems(res.data)
    setItemsLoading(false)
  }

  const decide = async (itemId: string, decision: 'certified' | 'revoked') => {
    const justification = decision === 'revoked'
      ? prompt('Revocation reason:') ?? 'Access revoked during UAR'
      : 'Access certified — access is appropriate'
    await api.post(`/reviews/items/${itemId}/decide`, { decision, justification })
    if (selectedCampaign) loadItems(selectedCampaign)
    fetchCampaigns()
  }

  useEffect(() => { fetchCampaigns() }, [])

  return (
    <div className="space-y-5 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Access Review Campaigns</h1>
          <p className="text-sm text-slate-400 mt-0.5">Manage UAR campaigns and certification decisions</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchCampaigns} className="btn-ghost px-2.5 py-2">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            <Plus size={14} /> New Campaign
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Campaign list */}
        <div className="space-y-3">
          {loading ? (
            <div className="card p-8 text-center text-slate-500 text-sm">Loading campaigns...</div>
          ) : campaigns.length === 0 ? (
            <div className="card p-8 text-center">
              <p className="text-slate-400 text-sm">No campaigns yet</p>
              <button onClick={() => setShowCreate(true)} className="btn-primary mt-4 mx-auto">
                <Plus size={14} /> Create First Campaign
              </button>
            </div>
          ) : campaigns.map(c => (
            <div
              key={c.id}
              onClick={() => loadItems(c)}
              className={`card p-4 cursor-pointer transition-all duration-150 hover:border-brand-500/30
                ${selectedCampaign?.id === c.id ? 'border-brand-500/40 bg-brand-500/5' : ''}`}
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-sm font-medium text-slate-200">{c.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{c.campaign_type} · {c.compliance_standard}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={STATUS_COLORS[c.status] ?? 'badge-info'}>{c.status}</span>
                  <ArrowRight size={13} className="text-slate-600" />
                </div>
              </div>

              <ProgressBar value={c.completion_rate ?? 0} />

              <div className="flex items-center justify-between mt-2">
                <div className="flex gap-3 text-[11px] text-slate-500">
                  <span className="text-green-400">{c.certified_count} certified</span>
                  <span className="text-red-400">{c.revoked_count} revoked</span>
                  <span>{c.total_items - c.certified_count - c.revoked_count} pending</span>
                </div>
                <span className="text-[11px] text-slate-500">
                  Due {new Date(c.due_date).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Review items panel */}
        <div className="card">
          {!selectedCampaign ? (
            <div className="flex items-center justify-center h-48 text-sm text-slate-500">
              Select a campaign to review items
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-slate-800/60">
                <div className="text-sm font-medium text-slate-200">{selectedCampaign.name}</div>
                <div className="text-xs text-slate-500 mt-0.5">{items.length} items · click to certify or revoke</div>
              </div>
              <div className="overflow-y-auto max-h-[480px] divide-y divide-slate-800/40">
                {itemsLoading ? (
                  <div className="p-8 text-center text-slate-500 text-sm">Loading items...</div>
                ) : items.length === 0 ? (
                  <div className="p-8 text-center text-slate-500 text-sm">No items in this campaign</div>
                ) : items.map(item => (
                  <div key={item.id} className="px-4 py-3 flex items-center gap-3 hover:bg-slate-800/20">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-slate-400 font-mono truncate">{item.user_id.slice(0, 8)}…</div>
                      <div className="text-[11px] text-slate-600 mt-0.5">
                        Risk at review: <span className="text-slate-400">{Math.round(item.risk_score_at_review)}</span>
                      </div>
                    </div>

                    {item.decision === 'pending' ? (
                      <div className="flex gap-1.5">
                        <button
                          onClick={() => decide(item.id, 'certified')}
                          className="p-1.5 rounded-lg bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/20 transition-all"
                          title="Certify"
                        >
                          <CheckCircle size={14} />
                        </button>
                        <button
                          onClick={() => decide(item.id, 'revoked')}
                          className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 transition-all"
                          title="Revoke"
                        >
                          <XCircle size={14} />
                        </button>
                      </div>
                    ) : (
                      <span className={item.decision === 'certified' ? 'badge-low' : 'badge-critical'}>
                        {item.decision}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {showCreate && <CreateCampaignModal onClose={() => setShowCreate(false)} onSuccess={fetchCampaigns} />}
    </div>
  )
}

function CreateCampaignModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const today = new Date().toISOString().split('T')[0]
  const future = new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0]

  const [form, setForm] = useState({
    name: 'Q1 2026 Vendor Access Review',
    campaign_type: 'quarterly',
    compliance_standard: 'SOX',
    start_date: today,
    due_date: future,
    description: ''
  })
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setLoading(true)
    try {
      await api.post('/reviews/campaigns', {
        ...form,
        start_date: new Date(form.start_date).toISOString(),
        due_date: new Date(form.due_date).toISOString(),
      })
      onSuccess(); onClose()
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-md p-6 space-y-4 animate-slide-up">
        <h2 className="text-base font-semibold text-white">Create Review Campaign</h2>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Campaign Name</label>
          <input className="input-field" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Type</label>
            <select className="input-field" value={form.campaign_type} onChange={e => setForm(f => ({ ...f, campaign_type: e.target.value }))}>
              {['quarterly', 'annual', 'triggered', 'ad_hoc'].map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Standard</label>
            <select className="input-field" value={form.compliance_standard} onChange={e => setForm(f => ({ ...f, compliance_standard: e.target.value }))}>
              {['SOX', 'HIPAA', 'PCI-DSS', 'ISO-27001', 'SOC2'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Start Date</label>
            <input type="date" className="input-field" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Due Date</label>
            <input type="date" className="input-field" value={form.due_date} onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))} />
          </div>
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="btn-ghost flex-1 justify-center">Cancel</button>
          <button onClick={submit} disabled={loading} className="btn-primary flex-1 justify-center">
            {loading ? 'Launching...' : 'Launch Campaign'}
          </button>
        </div>
      </div>
    </div>
  )
}
