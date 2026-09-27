import { apiClient } from './client'

// 欄位名稱依 docs/API功能規格.md 的登入 API 猜測，實際串接前務必跟後端組確認
// Pydantic schema 裡的真實欄位名稱是否一致。
export interface LoginPayload {
  account: string
  password: string
}

export interface LoginResponse {
  access_token: string
  account: string
  name: string
  role: 'STUDENT' | 'TEACHER' | 'ADMIN'
}

export const authApi = {
  login(payload: LoginPayload) {
    return apiClient.post<LoginResponse>('/auth/login', payload)
  },
}
