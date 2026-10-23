// @ts-nocheck
import { apiClient } from './client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { ref } from 'vue'

export interface StudentCourse {
  id: number
  name: string
  code: string
}

export interface JoinCoursePayload {
  code: string
}

// Mock 資料（後端 API 尚未完全就緒前確保 UI 運作正常）
const mockStudentCourses = ref<StudentCourse[]>([
  { id: 1, name: '批判性思考與蘇格拉底對話法', code: 'SOC-101' },
  { id: 2, name: '基礎哲學導論與邏輯推論', code: 'PHI-202' },
])

export const studentApi = {
  getMyCourses() {
    return apiClient.get('/student/courses')
  },
  joinCourse(payload: JoinCoursePayload) {
    return apiClient.post('/student/courses/join', payload)
  },
  leaveCourse(id: number) {
    return apiClient.delete(`/student/courses/${id}`)
  },
  transcribeAudio(audioBlob: Blob) {
    const formData = new FormData()
    formData.append('audio', audioBlob)
    return apiClient.post('/student/transcribe', formData)
  },
  createSession(topicId: string | number) {
    return apiClient.post('/student/sessions', { topic_id: topicId })
  },
}

// TanStack Query Hooks
export function useStudentCourses() {
  return useQuery({
    queryKey: ['student', 'courses'],
    queryFn: async (): Promise<StudentCourse[]> => {
      await new Promise((resolve) => setTimeout(resolve, 100))
      return [...mockStudentCourses.value]
    },
  })
}

export function useJoinCourse() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: JoinCoursePayload): Promise<StudentCourse> => {
      const trimmedCode = payload.code.trim().toUpperCase()
      const newCourse: StudentCourse = {
        id: Date.now(),
        name: `新加入課程 (${trimmedCode})`,
        code: trimmedCode,
      }
      mockStudentCourses.value.push(newCourse)
      return newCourse
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['student', 'courses'] })
    },
  })
}

export function useLeaveCourse() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      mockStudentCourses.value = mockStudentCourses.value.filter((c) => c.id !== id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['student', 'courses'] })
    },
  })
}