import { apiClient } from './client'
import type { SessionStatus } from './courses'

/**
 * 學生的對話與個人報告（docs/API功能規格.md v0.2「題目對話階段」）。
 * 送出回答（SSE 串流）在 composables/useChatStream.ts。
 */

const enc = encodeURIComponent

export interface SessionMessage {
  message_id: string
  sender: 'ai' | 'student'
  content: string
  created_at: string
}

/** GET /sessions/{sessionId}/messages */
export interface SessionMessages {
  messages: SessionMessage[]
  session_status: SessionStatus
  max_turns: number
  completed_turns: number
  goal_reached: boolean
  /** AI 判斷可以結束了，等學生選「結束」或「繼續」 */
  awaiting_end_consent: boolean
}

export type EndAction = 'complete' | 'continue' | 'abandon'

export type GenerationStatus = 'pending' | 'processing' | 'ready' | 'failed'

/** 報告引用的學生原話 */
export interface EvidenceQuote {
  message_id: string
  turn: number
  quote: string
}

export interface TimelineEntry {
  turn: number
  question: string
  evidence: EvidenceQuote[] | EvidenceQuote | string | null
  viewpoint_before: string | null
  viewpoint_after: string | null
  change_type: string | null
  attribution: 'explicit' | 'sequence_only' | 'none' | null
}

/** 個人報告（學生本人看、老師在全班報告裡看同一個結構） */
export interface PersonalReport {
  report_id: string
  version: number
  session_id: string
  topic_id: string
  anonymous_id?: string | null
  completed_at?: string | null
  completed_turns: number
  completion_reason: string | null
  viewpoint_summary: string | null
  final_viewpoint: string | null
  viewpoint_status: string | null
  reasons: string[] | null
  strongest_reason: string | null
  challenges: { challenge: string; responded: boolean }[] | null
  revision_or_defense: string | null
  focus_connection: string | null
  other_perspectives: string | null
  open_questions: string[] | null
  evidence_status: 'sufficient' | 'partial' | 'insufficient' | null
  limitations: string | null
  timeline: TimelineEntry[] | null
}

export interface ReportResponse {
  report_status: GenerationStatus
  report: PersonalReport | null
}

export const sessionKeys = {
  messages: (sessionId: string) => ['sessions', sessionId, 'messages'] as const,
  report: (sessionId: string) => ['sessions', sessionId, 'report'] as const,
}

export const sessionsApi = {
  /** 第一次進入題目時建立 Session（已有 session_id 就直接讀訊息） */
  async create(topicId: string) {
    const res = await apiClient.post<{
      session_id: string
      topic_id: string
      session_status: SessionStatus
    }>(`/topics/${enc(topicId)}/sessions`)
    return res.data
  },
  async messages(sessionId: string) {
    const res = await apiClient.get<SessionMessages>(`/sessions/${enc(sessionId)}/messages`)
    return res.data
  },
  async end(sessionId: string, action: EndAction) {
    const res = await apiClient.post<{ session_id: string; session_status: SessionStatus }>(
      `/sessions/${enc(sessionId)}/end`,
      { action },
    )
    return res.data
  },
  /**
   * 查詢本人個人報告的進度（只看、不會觸發產生）。
   * 還沒呼叫過 startReport 時後端回 404，所以要先 startReport 再用這個輪詢。
   */
  async report(sessionId: string) {
    const res = await apiClient.get<ReportResponse>(`/sessions/${enc(sessionId)}/report`)
    return res.data
  },
  /**
   * 開始產生本人個人報告。結束對話不會自動產生報告，要呼叫這個才會開始。
   * 可以重複呼叫：正在產生或已完成就直接回傳那一筆；只有還沒有報告、上次失敗、處理逾時才會重新產生。
   * 不要拿來輪詢（上次失敗時每呼叫一次就會重做一次），輪詢用 report()。
   */
  async startReport(sessionId: string) {
    const res = await apiClient.post<ReportResponse>(`/sessions/${enc(sessionId)}/report`)
    return res.data
  },
}

/** 報告還在產生中 → 每 3 秒重問一次（給 useQuery 的 refetchInterval 用） */
export function reportPollInterval(data: ReportResponse | undefined) {
  return data && (data.report_status === 'pending' || data.report_status === 'processing')
    ? 3000
    : false
}
