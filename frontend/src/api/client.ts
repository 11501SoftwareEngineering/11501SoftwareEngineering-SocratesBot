import axios, { type AxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'

// 後端 API 規格文件（docs/API功能規格.md）裡的路徑都是 /api/v1/... 開頭，
// 例如 /api/v1/auth/login，如果這裡沒有補上 /api/v1，所有請求都會 404。
export const API_BASE_URL = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1`

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  // 後端用 refresh cookie 自動續期登入，要讓瀏覽器帶 cookie
  withCredentials: true,
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 登入、註冊時的 401 是「帳號密碼錯誤」，不是登入過期，不能把人踢回登入頁
const AUTH_FORM_PATHS = ['/auth/login', '/auth/register', '/auth/logout']
const SAFE_METHODS = ['get', 'head']

type RetryableConfig = AxiosRequestConfig & { _renewed?: boolean }

/**
 * 登入續期（後端 backend/app/api/deps.py）：
 * - access token 只有 15 分鐘。GET 請求過期時，後端會用 refresh cookie 自動續期，
 *   新的 token 放在回應的 Authorization header → 這裡收到就換掉
 * - POST/PUT/DELETE 過期時後端直接回 401 → 這裡先打一次 GET /users/me 續期，再重送一次
 */
apiClient.interceptors.response.use(
  (response) => {
    const header = String(response.headers.authorization ?? '')
    const renewed = header.replace(/^Bearer\s+/i, '')
    if (renewed && renewed !== localStorage.getItem('access_token')) {
      useAuthStore().setToken(renewed)
    }
    return response
  },
  async (error) => {
    const status = error.response?.status
    const config: RetryableConfig | undefined = error.config
    const url = config?.url ?? ''
    const method = (config?.method ?? 'get').toLowerCase()
    const isAuthForm = AUTH_FORM_PATHS.some((path) => url.endsWith(path))

    if (status === 401 && !isAuthForm && config) {
      if (!SAFE_METHODS.includes(method) && !config._renewed) {
        try {
          await apiClient.get('/users/me')
          return await apiClient({ ...config, _renewed: true } as RetryableConfig)
        } catch {
          // 續期失敗：GET /users/me 的 401 會走下面的登出流程
          return Promise.reject(error)
        }
      }
      void useAuthStore().logout({ expired: true })
    }
    // 老師帳號第一次登入要先改密碼，其他 API 會回 403
    if (status === 403 && error.response?.data?.detail === 'Password change required') {
      useAuthStore().requirePasswordChange()
    }
    return Promise.reject(error)
  },
)
