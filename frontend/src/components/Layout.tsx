import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  Shield, LayoutDashboard, Users, ClipboardCheck,
  AlertTriangle, FileText, LogOut, Bell, ChevronRight
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/users',     icon: Users,            label: 'Identities' },
  { to: '/reviews',   icon: ClipboardCheck,   label: 'Access Reviews' },
  { to: '/sod',       icon: AlertTriangle,    label: 'SoD Violations' },
  { to: '/audit',     icon: FileText,         label: 'Audit Log' },
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="flex h-screen overflow-hidden">

      {/* ── Sidebar ── */}
      <aside className="w-64 flex-shrink-0 flex flex-col bg-slate-900/95 border-r border-slate-800/60 backdrop-blur-xl">

        {/* Logo */}
        <div className="px-6 py-5 border-b border-slate-800/60">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/30">
              <Shield size={16} className="text-white" />
            </div>
            <div>
              <span className="font-semibold text-white tracking-tight">NexusGuard</span>
              <div className="text-[10px] text-slate-500 tracking-widest uppercase">IAM Platform</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group
                ${isActive
                  ? 'bg-brand-600/20 text-brand-400 border border-brand-500/20'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={16} className={isActive ? 'text-brand-400' : 'text-slate-500 group-hover:text-slate-300'} />
                  <span className="flex-1">{label}</span>
                  {isActive && <ChevronRight size={12} className="text-brand-500" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User info */}
        <div className="px-4 py-4 border-t border-slate-800/60">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-brand-600/30 border border-brand-500/30 flex items-center justify-center text-xs font-semibold text-brand-400">
              {user?.email?.[0]?.toUpperCase() ?? 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-slate-300 truncate">{user?.email}</div>
              <div className="text-[10px] text-slate-500 capitalize">{user?.role}</div>
            </div>
          </div>
          <button onClick={handleLogout} className="btn-ghost w-full justify-start text-slate-500 hover:text-red-400 text-xs px-2 py-1.5">
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-slate-800/60 bg-slate-900/60 backdrop-blur-xl flex-shrink-0">
          <div className="text-sm text-slate-500">
            External Identity Governance Platform
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors">
              <Bell size={16} />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse-glow" />
            </button>
            <div className="w-px h-5 bg-slate-700" />
            <span className="badge-info text-[10px]">v1.0.0</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
