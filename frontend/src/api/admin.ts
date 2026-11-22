import { apiClient } from './client'

/**
 * 管理員：老師帳號管理。
 * 欄位名稱照 docs/API功能規格.md v0.2。
 */

export interface Teacher {
  id: string
  account_id: string
  name: string
  created_at: string
}

export interface CreateTeacherPayload {
  account_id: string
  name: string
}

/** 建立或重設密碼後回傳的一次性初始密碼，只會出現這一次 */
export interface TeacherPasswordResponse {
  account_id: string
  name: string
  password: string
}

export const adminKeys = {
  teachers: ['admin', 'teachers'] as const,
}

export const adminApi = {
  async getTeachers() {
    const res = await apiClient.get<Teacher[]>('/admin/teachers')
    return res.data
  },
  async createTeacher(payload: CreateTeacherPayload) {
    const res = await apiClient.post<TeacherPasswordResponse>('/admin/teachers', payload)
    return res.data
  },
  deleteTeacher(teacherId: string) {
    return apiClient.delete(`/admin/teachers/${encodeURIComponent(teacherId)}`)
  },
  /** 重設老師密碼：回傳新的一次性初始密碼，老師下次登入要修改 */
  async resetTeacherPassword(teacherId: string) {
    const res = await apiClient.post<{ password: string; message: string }>(
      `/admin/teachers/${encodeURIComponent(teacherId)}/reset-password`,
    )
    return res.data
  },
}
