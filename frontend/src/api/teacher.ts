import { apiClient } from './client'

/**
 * 老師端：課程、題目、學生名單、結論。
 * 欄位名稱已對照後端 OpenAPI（backend/app/schemas/course.py、topic.py）。
 * 標 ⚠️ 的 API 後端還沒做，只有假後端（pnpm dev:mock）能用，見 src/config/features.ts。
 */

export interface TeacherCourse {
  course_id: string
  name: string
  description: string | null
  invite_code: string
  student_count: number
  topic_count: number
}

export interface CoursePayload {
  /** 1–255 字 */
  name: string
  description?: string | null
}

export interface CourseCreateResponse {
  course_id: string
  name: string
  description: string | null
  invite_code: string
  message?: string
}

/** Figma「新增問題」的年齡層選項 ⚠️ 後端還沒有這個欄位（features.topicSettings） */
export const AGE_RANGES = ['13-15', '16-18', '18+'] as const

/** Figma「新增問題」的回合數選項 ⚠️ 後端還沒有這個欄位（features.topicSettings） */
export const ROUND_OPTIONS = [
  { value: 5, label: '簡短' },
  { value: 10, label: '標準' },
  { value: 15, label: '較長' },
] as const

export interface TeacherTopic {
  topic_id: string
  title: string
  description: string | null
  /** 已完成作答的學生人數 */
  answered_count: number
  /** ⚠️ 後端還沒有，假後端才有 */
  age_range?: string | null
  /** ⚠️ 後端還沒有，假後端才有 */
  max_rounds?: number | null
}

export interface TeacherCourseTopics {
  course_id: string
  name: string
  invite_code: string
  topics: TeacherTopic[]
}

export interface TopicPayload {
  course_id: string
  /** 1–255 字 */
  title: string
  description?: string | null
  /** ⚠️ 後端還沒有，假後端才會存 */
  age_range?: string
  /** ⚠️ 後端還沒有，假後端才會存 */
  max_rounds?: number
}

export interface CourseStudent {
  student_id: string
  account_id: string
  name: string
  joined_at: string
}

export interface ConclusionStudent {
  student_id: string
  display_name: string
}

export interface Conclusion {
  conclusion_id: string
  title: string
  description: string | null
  count: number
  percentage: number
  students: ConclusionStudent[]
}

export interface TopicConclusions {
  topic_id: string
  total_answered: number
  conclusions: Conclusion[]
}

export interface ConclusionPayload {
  title: string
  description: string
}

export interface StudentArgument {
  student_id: string
  display_name: string
  is_anonymous: boolean
  conclusion_id: string | null
  conclusion_title: string | null
  summary: string
}

export interface TeacherTopicAnalytics {
  total_answered: number
  arguments: StudentArgument[]
}

export const teacherKeys = {
  courses: ['teacher', 'courses'] as const,
  course: (courseId: string) => ['teacher', 'course', courseId] as const,
  students: (courseId: string) => ['teacher', 'course', courseId, 'students'] as const,
  conclusions: (topicId: string) => ['teacher', 'topic', topicId, 'conclusions'] as const,
  analytics: (topicId: string) => ['teacher', 'topic', topicId, 'analytics'] as const,
}

const enc = encodeURIComponent

export const teacherApi = {
  async getCourses() {
    const res = await apiClient.get<TeacherCourse[]>('/teacher/courses')
    return res.data
  },
  async createCourse(payload: CoursePayload) {
    const res = await apiClient.post<CourseCreateResponse>('/teacher/courses', payload)
    return res.data
  },
  /** ⚠️ 後端還沒有（features.courseEdit） */
  updateCourse(courseId: string, payload: CoursePayload) {
    return apiClient.put(`/teacher/courses/${enc(courseId)}`, payload)
  },
  /** 只有開課老師可以刪；成功回 204 */
  deleteCourse(courseId: string) {
    return apiClient.delete(`/teacher/courses/${enc(courseId)}`)
  },
  async getCourseTopics(courseId: string) {
    const res = await apiClient.get<TeacherCourseTopics>(`/teacher/courses/${enc(courseId)}/topics`)
    return res.data
  },
  async getCourseStudents(courseId: string) {
    const res = await apiClient.get<CourseStudent[]>(`/teacher/courses/${enc(courseId)}/students`)
    return res.data
  },
  /** 用學生帳號手動加入課程 */
  addStudent(courseId: string, accountId: string) {
    return apiClient.post<{ message: string }>(`/teacher/courses/${enc(courseId)}/students`, {
      account_id: accountId,
    })
  },
  /** 把學生移出課程；成功回 204 */
  removeStudent(courseId: string, studentId: string) {
    return apiClient.delete(`/teacher/courses/${enc(courseId)}/students/${enc(studentId)}`)
  },
  createTopic(payload: TopicPayload) {
    return apiClient.post('/teacher/topics', payload)
  },
  /** 後端只收 title、description（不能換課程） */
  updateTopic(topicId: string, payload: Omit<TopicPayload, 'course_id'>) {
    return apiClient.put(`/teacher/topics/${enc(topicId)}`, payload)
  },
  /** 成功回 204 */
  deleteTopic(topicId: string) {
    return apiClient.delete(`/teacher/topics/${enc(topicId)}`)
  },
  /** ⚠️ 後端還沒有（features.conclusions） */
  async getConclusions(topicId: string) {
    const res = await apiClient.get<TopicConclusions>(`/teacher/topics/${enc(topicId)}/conclusions`)
    return res.data
  },
  /** ⚠️ 後端還沒有（features.conclusions） */
  createConclusion(topicId: string, payload: ConclusionPayload) {
    return apiClient.post(`/teacher/topics/${enc(topicId)}/conclusions`, payload)
  },
  /** ⚠️ 後端還沒有（features.conclusions） */
  deleteConclusion(topicId: string, conclusionId: string) {
    return apiClient.delete(`/teacher/topics/${enc(topicId)}/conclusions/${enc(conclusionId)}`)
  },
  /** ⚠️ 後端還沒有（features.conclusions） */
  async getTopicAnalytics(topicId: string) {
    const res = await apiClient.get<TeacherTopicAnalytics>(
      `/teacher/topics/${enc(topicId)}/analytics`,
    )
    return res.data
  },
}
