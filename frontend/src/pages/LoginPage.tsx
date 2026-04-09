import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../store/authStore'

export default function LoginPage() {
  const [email, setEmail]       = useState('admin@nexusguard.io')
  const [password, setPassword] = useState('admin123')
  const [showPw, setShowPw]     = useState(false)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch {
      setError('Invalid credentials. Use admin@nexusguard.io / admin123')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm animate-slide-up">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex w-14 h-14 rounded-2xl bg-brand-600 items-center justify-center shadow-2xl shadow-brand-600/40 mb-4">
            <Shield size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-semibold text-white">NexusGuard</h1>
          <p className="text-sm text-slate-400 mt-1">External Identity Governance</p>
        </div>

        <div className="card p-6 space-y-4">
          <div>
            <p className="text-xs text-slate-500 mb-4 text-center">Sign in to your IAM console</p>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              <AlertCircle size={15} className="mt-0.5 flex-shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Email</label>
              <input
                className="input-field"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@nexusguard.io"
                required
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1.5 block">Password</label>
              <div className="relative">
                <input
                  className="input-field pr-10"
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-2.5 mt-1"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Authenticating...
                </span>
              ) : 'Sign in'}
            </button>
          </form>
        </div>

        <div className="mt-4 p-3 rounded-lg bg-slate-800/40 border border-slate-700/40">
          <p className="text-[11px] text-slate-500 text-center">
            Demo: <span className="text-slate-400 font-mono">admin@nexusguard.io</span> / <span className="font-mono text-slate-400">admin123</span>
          </p>
        </div>
      </div>
    </div>
  )
}
