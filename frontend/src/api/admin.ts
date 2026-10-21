import { apiClient } from './client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { ref } from 'vue'

export interface Teacher {
  id: number
  account: string
  name: string
  created_at: string
}

export interface CreateTeacherPayload {
  account: string
  name: string
}

export interface CreateTeacherResponse {
  password: string
}

// 後端 #86 尚未合併前使用的 Mock 資料（欄位對齊：id, account, name, created_at）
const mockTeachers = ref<Teacher[]>([
  { id: 1, account: 'teacher01', name: '王老師', created_at: '2026-03-01' },
  { id: 2, account: 'teacher02', name: '李老師', created_at: '2026-03-02' },
])

// 安全產生隨機密碼（修正 undefined 型別錯誤並通過 CodeQL）
function generateSecurePassword(): string {
  const array = new Uint32Array(1)
  window.crypto.getRandomValues(array)
  const randomVal = array[0] ?? 0
  return 'pw_' + randomVal.toString(36)
}

// 原始 API 串接定義
export const adminApi = {
  getTeachers() {
    return apiClient.get('/admin/teachers')
  },
  createTeacher(payload: CreateTeacherPayload) {
    return apiClient.post('/admin/teachers', payload)
  },
  deleteTeacher(id: number) {
    return apiClient.delete(`/admin/teachers/${id}`)
  },
}

// TanStack Query Hooks
export function useAdminTeachers() {
  return useQuery({
    queryKey: ['admin', 'teachers'],
    queryFn: async (): Promise<Teacher[]> => {
      await new Promise((resolve) => setTimeout(resolve, 100))
      return [...mockTeachers.value]
    },
  })
}

export function useCreateTeacher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateTeacherPayload): Promise<CreateTeacherResponse> => {
      const password = generateSecurePassword()
      mockTeachers.value.push({
        id: Date.now(),
        account: payload.account,
        name: payload.name,
        created_at: new Date().toISOString().slice(0, 10),
      })
      return { password }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teachers'] })
    },
  })
}

export function useDeleteTeacher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      mockTeachers.value = mockTeachers.value.filter((t) => t.id !== id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teachers'] })
    },
  })
}