import { apiClient } from './client'

export interface LoginPayload {
  account: string
  password: string
}

// Updated to match the actual JSON body fields. Token is now retrieved from headers.
export interface LoginResponse {
  account: string
  name: string
  role: 'STUDENT' | 'TEACHER' | 'ADMIN'
  preferred_language: string
  must_change_password: boolean
}

// Added the payload interface for registration
export interface RegisterPayload {
  account: string
  password: string
  name: string
}

export const authApi = {
  login(payload: LoginPayload) {
    return apiClient.post<LoginResponse>('/auth/login', payload)
  },
  // Added the register API endpoint
  register(payload: RegisterPayload) {
    return apiClient.post('/auth/register', payload)
  },
}
