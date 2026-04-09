import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../utils/api'

interface AuthUser {
  id: string
  email: string
  role: string
  is_admin: boolean
}

interface AuthStore {
  token: string | null
  user: AuthUser | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      login: async (email, password) => {
        const res = await api.post('/auth/login', { email, password })
        const { access_token, user } = res.data
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        set({ token: access_token, user })
      },
      logout: () => {
        delete api.defaults.headers.common['Authorization']
        set({ token: null, user: null })
      },
    }),
    { name: 'nexusguard-auth' }
  )
)
