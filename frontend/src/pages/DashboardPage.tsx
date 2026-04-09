import { useEffect, useState } from 'react'
import {
  Users, ShieldAlert, AlertTriangle, ClipboardCheck,
  TrendingUp, Clock, Activity, ArrowUpRight
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import api from '../utils/api'

const RISK_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#22c55e',
  minimal:  '#6b7280',
}

interface Summary {
  users: { total: number; active: number; expiring_contracts: number }
  risk:  { distribution: Record<string, number>; critical: number; high: number; medium: number; low: number }
  sod:   { open_violations: number; critical_violations: number }
  reviews: { active_campaigns: number }
  audit: { events_last_24h: number }
}

interface ActivityEvent {
  id: string; event_type: string; action: string; outcome: string
  actor_email: string; target_email: string; category: string; created_at: string
}

function StatCard({ icon: Icon, label, value, sub, color = 'brand', trend }: {
  icon: any; label: string; value: number | string; sub?: string; color?: string; trend?: string
}) {
  const colorMap: Record<string, string> = {
    brand:   'text-brand-400 bg-brand-500/10',
    red:     'text-red-400 bg-red-500/10',
    orange:  'text-orange-400 bg-orange-500/10',
    green:   'text-green-400 bg-green-500/10',
    yellow:  'text-yellow-400 bg-yellow-500/10',
  }
  return (
    <div className="stat-card group hover:border-slate-600/60 transition-all duration-200">
      <div className="flex items-start justify-between">
        <div className={`p-2 rounded-lg ${colorMap[color] ?? colorMap.brand}`}>
          <Icon size={16} className={colorMap[color]?.split(' ')[0]} />
        </div>
        {trend && (
          <span className="text-[11px] text-slate-500 flex items-center gap-0.5">
            <ArrowUpRight size={10} />{trend}
          </span>
        )}
      </div>
      <div className="mt-3">
        <div className="text-2xl font-semibold text-white tabular-nums">{value}</div>
        <div className="text-xs text-slate-400 mt-0.5">{label}</div>
        {sub && <div className="text-[11px] text-slate-600 mt-1">{sub}</div>}
      </div>
    </div>
  )
}

const outcomeColor = (outcome: string) =>
  outcome === 'success' ? 'text-green-400' : 'text-red-400'

const categoryBadge = (cat: string) => {
  const map: Record<string, string> = {
    identity_lifecycle: 'badge-info',
    access_change: 'badge-medium',
    authentication: 'badge-low',
    sod_event: 'badge-critical',
    review_action: 'badge-high',
    admin_action: 'badge-high',
  }
  return map[cat] ?? 'badge-info'
}

export default function DashboardPage() {
  const [summary, setSummary]     = useState<Summary | null>(null)
  const [breakdown, setBreakdown] = useState<any[]>([])
  const [activity, setActivity]   = useState<ActivityEvent[]>([])
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/dashboard/summary'),
      api.get('/dashboard/identity-breakdown'),
      api.get('/dashboard/recent-activity'),
    ]).then(([s, b, a]) => {
      setSummary(s.data)
      setBreakdown(b.data)
      setActivity(a.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-6 h-6 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
    </div>
  )

  const riskPieData = summary ? Object.entries(summary.risk.distribution).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1), value
  })) : []

  const barData = breakdown.map(b => ({
    name: b.class.replace('_', ' '), count: b.count
  }))

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-white">Risk Overview</h1>
        <p className="text-sm text-slate-400 mt-0.5">External identity governance at a glance</p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Users}         label="Active Identities"   value={summary?.users.active ?? 0}            color="brand" />
        <StatCard icon={ShieldAlert}   label="Critical Risk Users" value={summary?.risk.critical ?? 0}           color="red"    sub="Requires immediate action" />
        <StatCard icon={AlertTriangle} label="Open SoD Violations" value={summary?.sod.open_violations ?? 0}     color="orange" />
        <StatCard icon={ClipboardCheck} label="Active Campaigns"   value={summary?.reviews.active_campaigns ?? 0} color="green" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={TrendingUp}    label="High Risk Users"     value={summary?.risk.high ?? 0}               color="orange" />
        <StatCard icon={Clock}         label="Expiring Contracts"  value={summary?.users.expiring_contracts ?? 0} color="yellow" sub="Within 30 days" />
        <StatCard icon={Activity}      label="Audit Events (24h)"  value={summary?.audit.events_last_24h ?? 0}   color="brand" />
        <StatCard icon={ShieldAlert}   label="Critical SoD"        value={summary?.sod.critical_violations ?? 0} color="red" sub="SOX control risk" />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Risk Distribution Pie */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-slate-200">Risk Distribution</h2>
            <span className="text-xs text-slate-500">{summary?.users.active} active identities</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={riskPieData}
                cx="50%" cy="50%"
                innerRadius={60} outerRadius={90}
                paddingAngle={3}
                dataKey="value"
              >
                {riskPieData.map((entry) => (
                  <Cell key={entry.name} fill={RISK_COLORS[entry.name.toLowerCase()] ?? '#6b7280'} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Legend
                formatter={(value) => <span style={{ color: '#94a3b8', fontSize: 11 }}>{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Identity Breakdown Bar */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-slate-200">Identities by Class</h2>
            <span className="text-xs text-slate-500">Active only</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                cursor={{ fill: 'rgba(99,102,241,0.08)' }}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Activity Feed */}
      <div className="card">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/60">
          <h2 className="text-sm font-medium text-slate-200">Recent Activity</h2>
          <span className="text-xs text-slate-500">Last 20 events</span>
        </div>
        <div className="divide-y divide-slate-800/40">
          {activity.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-slate-500">No recent activity</div>
          ) : activity.slice(0, 10).map(event => (
            <div key={event.id} className="px-5 py-3 flex items-start gap-3 hover:bg-slate-800/20 transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-medium ${categoryBadge(event.category)}`}>{event.category.replace(/_/g, ' ')}</span>
                  <span className="text-xs text-slate-300 font-mono">{event.event_type}</span>
                  <span className={`text-xs ${outcomeColor(event.outcome)}`}>• {event.outcome}</span>
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {event.actor_email && <span>{event.actor_email}</span>}
                  {event.target_email && <span> → {event.target_email}</span>}
                </div>
              </div>
              <div className="text-[11px] text-slate-600 whitespace-nowrap">
                {new Date(event.created_at).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
