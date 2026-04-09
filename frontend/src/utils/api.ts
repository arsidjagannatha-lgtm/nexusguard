import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Restore token from storage on page load
const stored = localStorage.getItem('nexusguard-auth')
if (stored) {
  try {
    const { state } = JSON.parse(stored)
    if (state?.token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${state.token}`
    }
  } catch { /* ignore */ }
}

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('nexusguard-auth')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
