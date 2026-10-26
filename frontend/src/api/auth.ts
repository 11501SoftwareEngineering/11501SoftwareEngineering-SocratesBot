// @ts-nocheck
import { apiClient } from './client'

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
  getCurrentUser() {
    return apiClient.get('/users/me')
  },
}