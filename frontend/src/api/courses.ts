import { apiClient } from './client'

/**
 * 課程、課程名單、助教（docs/API功能規格.md v0.2「課程 Course」「課程名單」）。
 * 老師、助教、學生共用同一組 API，回應裡的 `my_role` 說明本人在這門課的身分。
 */

const enc = encodeURIComponent

/** 本人在課程裡的身分 */
export type CourseRole = 'teacher' | 'ta' | 'student'

/** 助教權限 */
export type TaPermission = 'edit_topics' | 'view_reports' | 'edit_summary' | 'view_members'

export const TA_PERMISSIONS: { value: TaPermission; label: string; hint: string }[] = [
  { value: 'view_members', label: '檢視學生名單', hint: '不能移除學生或管理助教' },
  { value: 'view_reports', label: '檢視學生報告', hint: '包含觀點 tag 與學生姓名' },
  { value: 'edit_topics', label: '編輯活動', hint: '新增活動、修改草稿的設定' },
  { value: 'edit_summary', label: '編輯全班摘要', hint: '重新產生、修改摘要；不能發布' },
]

/** GET /courses 的一筆 */
export interface CourseSummary {
  course_id: string
  name: string
  description: string | null
  teacher_name: string
  topic_count: number
  my_role: CourseRole
  my_permissions: TaPermission[]
  invite_code: string
  /** 只有老師、有 view_members 的助教拿得到 */
  student_count?: number | null
}

/** GET /courses/{courseId} */
export interface CourseDetail {
  course_id: string
  name: string
  description: string | null
  teacher_name: string
  my_role: CourseRole
  my_permissions: TaPermission[]
  invite_code: string
  default_model?: { id: string; name: string } | null
}

export interface CoursePayload {
  name: string
  description?: string
}

/** 題目年齡層 */
export type AgeBand = '13-15' | '16-18' | 'university_plus'
export const AGE_BANDS: { value: AgeBand; label: string }[] = [
  { value: '13-15', label: '13-15 歲' },
  { value: '16-18', label: '16-18 歲' },
  { value: 'university_plus', label: '大學以上' },
]
export const ageBandLabel = (value: AgeBand | null | undefined) =>
  AGE_BANDS.find((a) => a.value === value)?.label ?? '—'

/** 對話回合上限 */
export type MaxTurns = 5 | 10 | 15
export const MAX_TURNS: MaxTurns[] = [5, 10, 15]

/** 題目階段：設定（草稿）→ 學生對話（已發布）→ 觀點摘要 */
export type TopicStatus = 'setup' | 'conversation' | 'summary'

/** 學生本人的對話狀態 */
export type SessionStatus = 'IN_PROGRESS' | 'COMPLETED'

/** GET /courses/{courseId}/topics 的一筆 */
export interface TopicListItem {
  topic_id: string
  title: string
  description: string | null
  topic_status: TopicStatus
  age_band: AgeBand | null
  max_turns: MaxTurns | null
  /** 學生：還沒開始時是 null */
  session_status?: SessionStatus | null
  session_id?: string | null
  /** 老師、助教：完成人數 / 全班人數 */
  answered_count?: number
  student_count?: number
}

export interface CourseTopics {
  course_id: string
  name: string
  invite_code: string
  my_role: CourseRole
  my_permissions: TaPermission[]
  topics: TopicListItem[]
}

export interface CourseMember {
  user_id: string
  account_id: string
  name: string
  role: 'student' | 'ta'
  joined_at: string
  permissions: TaPermission[]
}

export const courseKeys = {
  all: ['courses'] as const,
  detail: (courseId: string) => ['courses', courseId] as const,
  topics: (courseId: string) => ['courses', courseId, 'topics'] as const,
  members: (courseId: string, role?: 'student' | 'ta') =>
    ['courses', courseId, 'members', role ?? 'all'] as const,
}

export const coursesApi = {
  async list() {
    const res = await apiClient.get<CourseSummary[]>('/courses')
    return res.data
  },
  async get(courseId: string) {
    const res = await apiClient.get<CourseDetail>(`/courses/${enc(courseId)}`)
    return res.data
  },
  async create(payload: CoursePayload) {
    const res = await apiClient.post<CourseDetail & { message: string }>('/courses', payload)
    return res.data
  },
  async update(courseId: string, payload: CoursePayload) {
    const res = await apiClient.put(`/courses/${enc(courseId)}`, payload)
    return res.data
  },
  remove(courseId: string) {
    return apiClient.delete(`/courses/${enc(courseId)}`)
  },
  async join(invite_code: string) {
    const res = await apiClient.post<{ course_id: string; name: string; message: string }>(
      '/courses/join',
      { invite_code },
    )
    return res.data
  },
  /** 學生退出課程 */
  leave(courseId: string) {
    return apiClient.delete(`/courses/${enc(courseId)}/member`)
  },
  async topics(courseId: string) {
    const res = await apiClient.get<CourseTopics>(`/courses/${enc(courseId)}/topics`)
    return res.data
  },
  async members(courseId: string, role?: 'student' | 'ta') {
    const res = await apiClient.get<CourseMember[]>(`/courses/${enc(courseId)}/members`, {
      params: role ? { role } : undefined,
    })
    return res.data
  },
  removeStudent(courseId: string, userId: string) {
    return apiClient.delete(`/courses/${enc(courseId)}/students/${enc(userId)}`)
  },
  async addTa(courseId: string, account_id: string, permissions: TaPermission[]) {
    const res = await apiClient.post<{
      user_id: string
      account_id: string
      name: string
      permissions: TaPermission[]
      message: string
    }>(`/courses/${enc(courseId)}/tas`, { account_id, permissions })
    return res.data
  },
  async updateTa(courseId: string, userId: string, permissions: TaPermission[]) {
    const res = await apiClient.put(`/courses/${enc(courseId)}/tas/${enc(userId)}`, {
      permissions,
    })
    return res.data
  },
  removeTa(courseId: string, userId: string) {
    return apiClient.delete(`/courses/${enc(courseId)}/tas/${enc(userId)}`)
  },
}
