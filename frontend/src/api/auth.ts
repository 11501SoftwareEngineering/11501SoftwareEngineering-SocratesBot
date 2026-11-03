import { apiClient } from './client'

/**
 * 登入、註冊、帳號相關 API。
 * 欄位名稱已對照後端 OpenAPI（backend/app/schemas/auth.py）。
 */

/** 前端統一使用的角色名稱（路由 meta.roles、畫面判斷都用這個） */
export type UserRole = 'STUDENT' | 'TEACHER' | 'SUPER_ADMIN'

/** 後端實際回傳的角色字串（backend/app/core/enums.py） */
type BackendRole = 'USER' | 'TEACHER' | 'SUPERADMIN'

// 後端的學生叫 USER、管理員叫 SUPERADMIN，跟前端規範不同，只在這裡轉換一次。
const ROLE_MAP: Record<BackendRole, UserRole> = {
  USER: 'STUDENT',
  TEACHER: 'TEACHER',
  SUPERADMIN: 'SUPER_ADMIN',
}

/** 一個人有多個身分時（例如管理員同時也是老師），用權限最高的當「主要身分」 */
const ROLE_PRIORITY: UserRole[] = ['SUPER_ADMIN', 'TEACHER', 'STUDENT']

/**
 * 把後端的 `role`（字串陣列，例如 `["SUPERADMIN", "TEACHER"]`）轉成前端角色。
 * 也接受單一字串，相容舊版後端。
 */
export function toUserRoles(role: string | string[]): UserRole[] {
  const list = Array.isArray(role) ? role : [role]
  const roles = list.map((r) => ROLE_MAP[r as BackendRole]).filter((r): r is UserRole => !!r)
  return roles.length ? roles : ['STUDENT']
}

export function primaryRole(roles: UserRole[]): UserRole {
  return ROLE_PRIORITY.find((r) => roles.includes(r)) ?? 'STUDENT'
}

export const ROLE_LABELS: Record<UserRole, string> = {
  STUDENT: '學生',
  TEACHER: '老師',
  SUPER_ADMIN: '管理員',
}

export interface User {
  account: string
  name: string
  /** 主要身分：決定首頁、Header 顯示 */
  role: UserRole
  /** 全部身分：決定能進哪些頁面 */
  roles: UserRole[]
  preferred_language: string
  /** 管理員建立的老師帳號第一次登入時為 true，要先改密碼才能用其他功能 */
  must_change_password: boolean
}

/** POST /auth/login、GET /users/me 的回應 */
interface UserResponse {
  account: string
  name: string
  role: string[]
  preferred_language?: string
  must_change_password?: boolean
}

export interface LoginPayload {
  account: string
  password: string
}

export interface RegisterPayload {
  /** 1–64 字 */
  account: string
  /** 8–128 字 */
  password: string
  /** 1–128 字 */
  name: string
}

export interface ChangePasswordPayload {
  old_password: string
  /** 8–128 字 */
  new_password: string
}

export function toUser(data: UserResponse): User {
  const roles = toUserRoles(data.role)
  return {
    account: data.account,
    name: data.name,
    role: primaryRole(roles),
    roles,
    preferred_language: data.preferred_language ?? 'zh-TW',
    must_change_password: !!data.must_change_password,
  }
}

export const authApi = {
  /** 登入。後端把 access token 放在回應的 Authorization header，不在 JSON 裡 */
  async login(payload: LoginPayload) {
    const res = await apiClient.post<UserResponse>('/auth/login', payload)
    const header = String(res.headers.authorization ?? '')
    const token = header.replace(/^Bearer\s+/i, '')
    return { token, user: toUser(res.data) }
  },
  register(payload: RegisterPayload) {
    return apiClient.post('/auth/register', payload)
  },
  /** 登出（清掉後端的 refresh cookie）。失敗也沒關係，前端照樣清除登入狀態 */
  logout() {
    return apiClient.post('/auth/logout', null)
  },
  async getMe() {
    const res = await apiClient.get<UserResponse>('/users/me')
    return toUser(res.data)
  },
  changePassword(payload: ChangePasswordPayload) {
    return apiClient.put<{ message: string }>('/auth/password', payload)
  },
}
