import { apiClient } from './client'
import type { TopicStatus } from './courses'
import type { GenerationStatus, PersonalReport } from './sessions'

/**
 * 全班報告與摘要（docs/API功能規格.md v0.2「全班報告與摘要」）。
 *
 * 流程（後端 #272）：
 *   第一次：老師「結束對話並整理摘要」→ POST /topics/{id}/end-conversation（結束還開著的對話、活動進入 summary、
 *           背景先產生個人報告再整理全班摘要）→ 輪詢 GET /summary 的 preparation_status
 *   之後：重新整理摘要 POST /summary（也是背景處理，馬上回 pending）→ 輪詢
 *   草稿好了 → 修改文字 → 勾「我已確認…」（review，帶畫面上的文字）→ 發布（只發布最新且已審閱的版本）
 */

const enc = encodeURIComponent

export type SummaryStatus = 'draft' | 'reviewed' | 'published' | 'withdrawn'

export interface SummaryGroup {
  name: string
  conditions: string
  count: number
  percentage: number
  report_ids: string[]
}

export interface ClassSummary {
  summary_id: string
  version: number
  summary_status: SummaryStatus
  overview: string
  viewpoint_summary: string
  denominator: number
  groups: SummaryGroup[]
  ungrouped_report_ids: string[]
  created_at?: string | null
  updated_at?: string | null
}

export interface TeacherSummaryResponse {
  topic_status: TopicStatus
  /** 學生目前看到的版本；沒有發布過是 null */
  published_version: number | null
  /** 目前可以看的草稿；還在整理第一版時是 null */
  summary: ClassSummary | null
  /** 背景整理的進度；沒有整理過是 null。topic_status 是 summary 不代表草稿已經好了 */
  preparation_status?: GenerationStatus | null
}

/** 正在背景整理全班摘要（要輪詢） */
export function isPreparing(data: TeacherSummaryResponse | undefined) {
  return data?.preparation_status === 'pending' || data?.preparation_status === 'processing'
}

/** GET /topics/{topicId}/conversation-status、POST .../end-conversation 的回應 */
export interface ConversationStatus {
  topic_id: string
  topic_status: TopicStatus
  /** 已經進入、還沒結束的對話數（沒進入過的學生不算） */
  open_dialogue_count: number
  /** 老師已經結束對話階段 */
  stage2_closed: boolean
  /** 有還開著的對話，結束前要老師確認 */
  confirmation_required: boolean
  /** 這次被老師結束的對話數 */
  ended_dialogue_count: number
  preparation_status: GenerationStatus | null
}

/** 全班報告表格的一列：個人報告加上學生姓名（前端把後端的巢狀格式攤平成這樣） */
export interface TeachingReport extends PersonalReport {
  student_display_name: string
}

/** GET /topics/{topicId}/reports 後端原始格式：每一筆是 { report_status, report, student_display_name } */
interface TopicReportsResponse {
  class_size: number
  /** 達成目標後結束的人數 */
  completed_count: number
  /** 回合用完、提早結束、老師結束對話的人數（後端 #267 新增；也有報告） */
  ended_count?: number
  ready_count: number
  processing_count: number
  failed_count: number
  reports: {
    report_status: GenerationStatus
    report: PersonalReport | null
    student_display_name: string
  }[]
}

export interface TopicReports extends Omit<TopicReportsResponse, 'reports'> {
  /** 只放已經產生好的報告（還在產生、失敗的只算在上面的數量裡） */
  reports: TeachingReport[]
}

/**
 * 觀點群組的代號：後端的群組沒有 id，用順序當代號（g1、g2…）。
 * 「檢視報告」連結（網址的 ?group=）和學生報告分頁的篩選都要用這個，兩邊才對得上
 */
export function groupCode(index: number) {
  return `g${index + 1}`
}

/** 學生報告分頁用來篩選的觀點群組：從摘要的 groups 來 */
export interface ReportGroup {
  group_id: string
  name: string
  report_ids: string[]
}

export function reportGroups(summary: ClassSummary | null | undefined): ReportGroup[] {
  return (summary?.groups ?? []).map((g, i) => ({
    group_id: groupCode(i),
    name: g.name,
    report_ids: g.report_ids,
  }))
}

export interface PublishedSummary {
  overview: string
  viewpoint_summary: string
  groups: { name: string; conditions: string; count: number; percentage: number }[]
  ungrouped_count: number
  ungrouped_percentage: number
  denominator: number
}

export interface SummaryText {
  overview: string
  viewpoint_summary: string
}

export type { GenerationStatus }

export const summaryKeys = {
  conversation: (topicId: string) => ['topics', topicId, 'conversation-status'] as const,
  reports: (topicId: string) => ['topics', topicId, 'reports'] as const,
  summary: (topicId: string, version?: number) =>
    ['topics', topicId, 'summary', version ?? 'latest'] as const,
  published: (topicId: string) => ['topics', topicId, 'summary', 'published'] as const,
}

export const summariesApi = {
  async reports(topicId: string): Promise<TopicReports> {
    const res = await apiClient.get<TopicReportsResponse>(`/topics/${enc(topicId)}/reports`)
    const { reports, ...counts } = res.data
    return {
      ...counts,
      reports: reports.flatMap(({ report_status, report, student_display_name }) =>
        report_status === 'ready' && report ? [{ ...report, student_display_name }] : [],
      ),
    }
  },
  async get(topicId: string, version?: number) {
    const res = await apiClient.get<TeacherSummaryResponse>(`/topics/${enc(topicId)}/summary`, {
      params: version ? { version } : undefined,
    })
    return res.data
  },
  /**
   * 重新整理摘要：背景處理，馬上回 preparation_status: pending（不是草稿），之後輪詢 get()。
   * 所有對話都要先結束、個人報告都要好了，不然回 409。
   */
  async generate(topicId: string) {
    const res = await apiClient.post<TeacherSummaryResponse>(`/topics/${enc(topicId)}/summary`)
    return res.data
  },
  /** 對話階段的狀態：還有幾個對話開著（只看，不會結束任何東西） */
  async conversationStatus(topicId: string) {
    const res = await apiClient.get<ConversationStatus>(
      `/topics/${enc(topicId)}/conversation-status`,
    )
    return res.data
  },
  /**
   * 老師結束對話階段：結束還開著的對話（學生的報告照樣產生）、活動進入 summary，
   * 背景先等個人報告好了再自動整理全班摘要。整理失敗或逾時時再呼叫一次就會重試。
   */
  async endConversation(topicId: string) {
    const res = await apiClient.post<ConversationStatus>(
      `/topics/${enc(topicId)}/end-conversation`,
      { confirm_open_dialogues: true },
    )
    return res.data
  },
  async edit(topicId: string, text: SummaryText) {
    const res = await apiClient.patch<{ summary: ClassSummary }>(
      `/topics/${enc(topicId)}/summary`,
      text,
    )
    return res.data
  },
  async review(topicId: string, text: SummaryText) {
    const res = await apiClient.post<{ version: number; summary_status: SummaryStatus }>(
      `/topics/${enc(topicId)}/summary/review`,
      text,
    )
    return res.data
  },
  async publish(topicId: string) {
    const res = await apiClient.post<{ version: number; summary_status: SummaryStatus }>(
      `/topics/${enc(topicId)}/summary/publish`,
    )
    return res.data
  },
  async withdraw(topicId: string) {
    const res = await apiClient.post<{ summary_status: SummaryStatus }>(
      `/topics/${enc(topicId)}/summary/withdraw`,
    )
    return res.data
  },
  async published(topicId: string) {
    const res = await apiClient.get<{ summary: PublishedSummary | null }>(
      `/topics/${enc(topicId)}/summary/published`,
    )
    return res.data.summary
  },
  /** 報告產生失敗時，老師幫學生重試：POST /topics/{topicId}/reports/{sessionId} */
  async retryReport(topicId: string, sessionId: string) {
    return apiClient.post(`/topics/${enc(topicId)}/reports/${enc(sessionId)}`)
  },
}
