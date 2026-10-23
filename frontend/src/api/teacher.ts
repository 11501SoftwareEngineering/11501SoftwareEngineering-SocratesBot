import { apiClient } from './client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { ref } from 'vue'

export interface TeacherQuestion {
  id: number
  title: string
  grade_level: string
  rounds: number
  completed_count: number
  total_count: number
}

export interface CreateQuestionPayload {
  title: string
  grade_level: string
  rounds: number
  total_count: number
}

export interface UpdateQuestionPayload {
  id: number
  title: string
  grade_level: string
  rounds: number
  total_count: number
}

// Mock 資料（後端 API 尚未完全就緒前確保 UI 運作正常）
const mockQuestions = ref<TeacherQuestion[]>([
  { id: 1, title: '社會議題思辨：科技與隱私', grade_level: '7-9', rounds: 3, completed_count: 18, total_count: 25 },
  { id: 2, title: '自然科學探究：氣候變遷因應', grade_level: '10-12', rounds: 5, completed_count: 22, total_count: 24 },
  { id: 3, title: '倫理學入門：人工智慧自主權', grade_level: '10-12', rounds: 4, completed_count: 15, total_count: 26 },
])

// 原始 API 串接定義（依原架構保留擴充）
export const teacherApi = {
  getCourses() {
    return apiClient.get('/teacher/courses')
  },
  getQuestions() {
    return apiClient.get('/teacher/questions')
  },
  createQuestion(payload: CreateQuestionPayload) {
    return apiClient.post('/teacher/questions', payload)
  },
  updateQuestion(payload: UpdateQuestionPayload) {
    return apiClient.put(`/teacher/questions/${payload.id}`, payload)
  },
  deleteQuestion(id: number) {
    return apiClient.delete(`/teacher/questions/${id}`)
  },
}

// TanStack Query Hooks
export function useTeacherQuestions() {
  return useQuery({
    queryKey: ['teacher', 'questions'],
    queryFn: async (): Promise<TeacherQuestion[]> => {
      await new Promise((resolve) => setTimeout(resolve, 100))
      return [...mockQuestions.value]
    },
  })
}

export function useCreateQuestion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateQuestionPayload): Promise<TeacherQuestion> => {
      const newQuestion: TeacherQuestion = {
        id: Date.now(),
        title: payload.title,
        grade_level: payload.grade_level,
        rounds: payload.rounds,
        completed_count: 0,
        total_count: payload.total_count || 30,
      }
      mockQuestions.value.push(newQuestion)
      return newQuestion
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teacher', 'questions'] })
    },
  })
}

export function useUpdateQuestion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: UpdateQuestionPayload): Promise<void> => {
      const idx = mockQuestions.value.findIndex((q) => q.id === payload.id)
      if (idx !== -1) {
        const current = mockQuestions.value[idx]
        if (current) {
          mockQuestions.value[idx] = {
            ...current,
            title: payload.title,
            grade_level: payload.grade_level,
            rounds: payload.rounds,
            total_count: payload.total_count,
          }
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teacher', 'questions'] })
    },
  })
}

export function useDeleteQuestion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      mockQuestions.value = mockQuestions.value.filter((q) => q.id !== id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teacher', 'questions'] })
    },
  })
}