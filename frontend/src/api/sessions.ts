import { apiClient } from './client'

/**
 * 學生的對話與個人報告（docs/API功能規格.md v0.2「題目對話階段」）。
 * 送出回答（SSE 串流）在 composables/useChatStream.ts。
 */

const enc = encodeURIComponent

/**
 * 對話本身的狀態（對話相關 API：建立、訊息、結束 都回這個，小寫）：
 *   open 進行中
 *   completed 達成目標後學生選「結束」
 *   ended 回合用完（後端自動結束）或學生回答 3 次後提早結束
 *   abandoned 放棄（沒有報告）
 *   closed_by_summary 老師產生摘要時被關閉
 * completed、ended 都會自動開始產生報告（report_eligible）。
 * 注意：課程題目列表 GET /courses/{id}/topics 的 session_status 是另一套（IN_PROGRESS／COMPLETED，見 courses.ts）。
 */
export type DialogueStatus = 'open' | 'completed' | 'ended' | 'abandoned' | 'closed_by_summary'

/** 對話怎麼結束的：達成目標後選結束｜學生提早結束｜回合用完（舊資料可能是 completed） */
export type EndingReason = 'goal_reached' | 'student_requested_stop' | 'turn_limit' | 'completed'

/** 讀訊息、結束對話、串流 done 都會帶的結束相關欄位（後端 #267） */
export interface LifecycleFields {
  /** 可以看報告了（completed 或 ended） */
  report_eligible?: boolean
  ending_reason?: EndingReason | null
  /** 學生已經回答 3 次以上、對話還開著：可以提早結束（action: finish） */
  can_finish_early?: boolean
}

export interface SessionMessage {
  message_id: string
  sender: 'ai' | 'student'
  content: string
  created_at: string
}

/** GET /sessions/{sessionId}/messages */
export interface SessionMessages extends LifecycleFields {
  messages: SessionMessage[]
  session_status: DialogueStatus
  /** 題目沒設定回合上限時是 null */
  max_turns: number | null
  completed_turns: number
  goal_reached: boolean
  /** AI 判斷可以結束了，等學生選「結束」或「繼續」 */
  awaiting_end_consent: boolean
}

/**
 * complete：達成目標後選結束｜continue：達成目標後選繼續｜finish：回答 3 次後提早結束｜abandon：放棄
 */
export type EndAction = 'complete' | 'continue' | 'finish' | 'abandon'

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
  /** 新版報告：這一回合引用的學生原話（evidence 是描述文字） */
  evidence_reference?: EvidenceQuote | null
}

/** 個人報告（學生本人看、老師在全班報告裡看同一個結構） */
export interface PersonalReport {
  report_id: string
  version: number
  session_id: string
  topic_id: string
  anonymous_id?: string | null
  completed_at?: string | null
  ended_at?: string | null
  completed_turns: number
  /** 結束原因（goal_reached／student_requested_stop／turn_limit；舊資料是 completed） */
  completion_reason: string | null
  /** 有沒有達成探究目標；跟報告有沒有產生成功是兩回事 */
  goal_reached?: boolean | null
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
      session_status: DialogueStatus
    }>(`/topics/${enc(topicId)}/sessions`)
    return res.data
  },
  async messages(sessionId: string) {
    const res = await apiClient.get<SessionMessages>(`/sessions/${enc(sessionId)}/messages`)
    return res.data
  },
  async end(sessionId: string, action: EndAction) {
    const res = await apiClient.post<
      {
        session_id: string
        session_status: DialogueStatus
        message: string
        goal_reached?: boolean
      } & LifecycleFields
    >(`/sessions/${enc(sessionId)}/end`, { action })
    return res.data
  },
  /**
   * 查詢本人個人報告的進度（只看、不會觸發產生）。
   * 對話結束時後端會自動開始產生；舊資料可能還沒有報告（回 404），所以報告頁先 startReport 再用這個輪詢。
   */
  async report(sessionId: string) {
    const res = await apiClient.get<ReportResponse>(`/sessions/${enc(sessionId)}/report`)
    return res.data
  },
  /**
   * 開始產生本人個人報告（或拿回已經在產生／已產生的那一筆）。
   * 新的後端在對話結束時就會自動開始，這支主要用來重試失敗的報告、補舊資料。
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
