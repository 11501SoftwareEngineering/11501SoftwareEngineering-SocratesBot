import axios from 'axios'
import router from '@/router'

// 後端 API 規格文件（docs/API功能規格.md）裡的路徑都是 /api/v1/... 開頭，
// 例如 /api/v1/auth/login，如果這裡沒有補上 /api/v1，所有請求都會 404。
export const API_BASE_URL = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1`

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      router.push('/login')
    }
    return Promise.reject(error)
  }
)