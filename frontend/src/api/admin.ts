// @ts-nocheck
import { apiClient } from './client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { ref } from 'vue'

export interface TeacherAccount {
  id: number
  account: string
  defaultPassword: string
}

export interface CreateTeacherPayload {
  account: string
  password: string
}

const mockTeachers = ref<TeacherAccount[]>([
  { id: 1, account: 'teacher01', defaultPassword: 'password123' },
  { id: 2, account: 'teacher02', defaultPassword: 'password456' },
  { id: 3, account: 'teacher03', defaultPassword: 'password789' },
])

export const adminApi = {
  getTeachers() {
    return apiClient.get('/admin/teachers')
  },
  createTeacher(payload: CreateTeacherPayload) {
    return apiClient.post('/admin/teachers', payload)
  },
  resetPassword(id: number) {
    return apiClient.post(`/admin/teachers/${id}/reset-password`)
  },
  deleteTeacher(id: number) {
    return apiClient.delete(`/admin/teachers/${id}`)
  },
}

export function useAdminTeachers() {
  return useQuery({
    queryKey: ['admin', 'teachers'],
    queryFn: async (): Promise<TeacherAccount[]> => {
      await new Promise((resolve) => setTimeout(resolve, 100))
      return [...mockTeachers.value]
    },
  })
}

export function useCreateTeacher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateTeacherPayload): Promise<TeacherAccount> => {
      const newTeacher: TeacherAccount = {
        id: Date.now(),
        account: payload.account,
        defaultPassword: payload.password,
      }
      mockTeachers.value.push(newTeacher)
      return newTeacher
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teachers'] })
    },
  })
}

export function useResetTeacherPassword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      const target = mockTeachers.value.find((t) => t.id === id)
      if (target) {
        target.defaultPassword = `pwd-${Date.now().toString().slice(-5)}`
      }
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