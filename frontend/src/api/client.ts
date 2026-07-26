import axios from 'axios'

// In-memory access token — never touches localStorage or cookies.
// AuthContext calls setAccessToken after login/refresh; this module reads it.
let _accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  _accessToken = token
}

export function getAccessToken(): string | null {
  return _accessToken
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true, // send the httpOnly refresh_token cookie on every request
  // Fail a stalled request instead of hanging forever — surfaces the retry UI
  // rather than leaving the page stuck on loading skeletons.
  timeout: 20_000,
})

apiClient.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`
  }
  return config
})

// Singleton so concurrent 401s don't each kick off their own refresh call.
let _refreshing: Promise<string | null> | null = null

function doRefresh(): Promise<string | null> {
  if (_refreshing) return _refreshing
  _refreshing = apiClient
    .post<{ access_token: string }>('/api/auth/refresh')
    .then((res) => {
      _accessToken = res.data.access_token
      return _accessToken
    })
    .catch(() => {
      _accessToken = null
      return null
    })
    .finally(() => {
      _refreshing = null
    })
  return _refreshing
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    const url: string = error.config?.url ?? ''
    const alreadyRetried: boolean = error.config?._retry ?? false

    const isAuthEndpoint = url.includes('/api/auth/login') || url.includes('/api/auth/refresh')

    if (status === 401 && !isAuthEndpoint && !alreadyRetried) {
      error.config._retry = true
      const newToken = await doRefresh()
      if (newToken) {
        error.config.headers.Authorization = `Bearer ${newToken}`
        return apiClient(error.config)
      }
      // Refresh failed — session is dead; send user to login.
      _accessToken = null
      window.location.href = '/login'
    }

    return Promise.reject(error)
  },
)

export default apiClient
