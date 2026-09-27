import { apiClient } from './client'

// 同上,欄位名稱是依 API 規格文件的描述推測,實際串接時請跟後端同學核對一次。

export interface Course {
  course_id: string
  name: string
  invite_code: string
  teacher_name: string
  active_topic_count: number
}

export interface Topic {
  topic_id: string
  title: string
  description: string
  status: string
  session_id: string | null
}

export interface TopicExplanation {
  title: string
  background: string
  key_terms: string[]
}

export interface CreateSessionResponse {
  session_id: string
  topic_id: string
}

export interface SessionResult {
  session_id: string
  topic_id: string
  conclusion: string
  is_anonymous: boolean
}

export const studentApi = {
  getCourses() {
    return apiClient.get<Course[]>('/student/courses')
  },
  joinCourse(inviteCode: string) {
    return apiClient.post('/student/courses/join', { invite_code: inviteCode })
  },
  leaveCourse(courseId: string) {
    return apiClient.delete(`/student/courses/${courseId}`)
  },
  getCourseTopics(courseId: string) {
    return apiClient.get<{ topics: Topic[] }>(`/student/courses/${courseId}/topics`)
  },
  getTopicExplanation(topicId: string) {
    return apiClient.get<TopicExplanation>(`/student/topics/${topicId}/explanation`)
  },
  createSession(topicId: string) {
    return apiClient.post<CreateSessionResponse>(`/student/topics/${topicId}/sessions`)
  },
  // 語音辨識:錄音錄好的 Blob 直接上傳,後端回傳轉錄文字。
  // 欄位名稱 "file" 是常見慣例,請跟後端同學確認 FastAPI 那邊 UploadFile 參數叫什麼。
  transcribeAudio(audioBlob: Blob) {
    const formData = new FormData()
    formData.append('file', audioBlob, 'recording.webm')
    return apiClient.post<{ text: string }>('/student/audio/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getSessionResult(sessionId: string) {
    return apiClient.get<SessionResult>(`/student/sessions/${sessionId}/result`)
  },
  updatePrivacy(sessionId: string, isAnonymous: boolean) {
    return apiClient.patch(`/student/sessions/${sessionId}/privacy`, { is_anonymous: isAnonymous })
  },
  getTopicAnalytics(topicId: string) {
    return apiClient.get(`/student/topics/${topicId}/analytics`)
  },
}
