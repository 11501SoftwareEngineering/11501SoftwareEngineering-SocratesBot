// @ts-nocheck
import { apiClient } from './client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { ref } from 'vue'

export interface TeacherCourse {
  id: number
  name: string
  code: string
  description?: string
}

export interface CreateCoursePayload {
  name: string
  code: string
  description?: string
}

export interface UpdateCoursePayload {
  id: number
  name: string
  code: string
  description?: string
}

// Mock 資料（後端 API 尚未完全就緒前確保 UI 運作正常）
const mockCourses = ref<TeacherCourse[]>([
  { id: 1, name: '批判性思考與蘇格拉底對話法', code: 'SOC-101' },
  { id: 2, name: '基礎哲學導論與邏輯推論', code: 'PHI-202' },
  { id: 3, name: '倫理學與當代科技議題思辨', code: 'ETH-303' },
])

export const teacherApi = {
  getCourses() {
    return apiClient.get('/teacher/courses')
  },
  createCourse(payload: CreateCoursePayload) {
    return apiClient.post('/teacher/courses', payload)
  },
  updateCourse(payload: UpdateCoursePayload) {
    return apiClient.put(`/teacher/courses/${payload.id}`, payload)
  },
  deleteCourse(id: number) {
    return apiClient.delete(`/teacher/courses/${id}`)
  },
}

// TanStack Query Hooks
export function useTeacherCourses() {
  return useQuery({
    queryKey: ['teacher', 'courses'],
    queryFn: async (): Promise<TeacherCourse[]> => {
      await new Promise((resolve) => setTimeout(resolve, 100))
      return [...mockCourses.value]
    },
  })
}

export function useCreateCourse() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateCoursePayload): Promise<TeacherCourse> => {
      const newCourse: TeacherCourse = {
        id: Date.now(),
        name: payload.name,
        code: payload.code || `CRS-${Date.now().toString().slice(-4)}`,
        description: payload.description || '',
      }
      mockCourses.value.push(newCourse)
      return newCourse
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teacher', 'courses'] })
    },
  })
}

export function useUpdateCourse() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: UpdateCoursePayload): Promise<void> => {
      const idx = mockCourses.value.findIndex((c) => c.id === payload.id)
      if (idx !== -1) {
        const current = mockCourses.value[idx]
        if (current) {
          mockCourses.value[idx] = {
            ...current,
            name: payload.name,
            code: payload.code,
            description: payload.description,
          }
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teacher', 'courses'] })
    },
  })
}

export function useDeleteCourse() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      mockCourses.value = mockCourses.value.filter((c) => c.id !== id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teacher', 'courses'] })
    },
  })
}