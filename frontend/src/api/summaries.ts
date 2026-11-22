import { apiClient } from './client'
import type { TopicStatus } from './courses'
import type { GenerationStatus, PersonalReport } from './sessions'

/**
 * 全班報告與摘要（docs/API功能規格.md v0.2「全班報告與摘要」）。
 *
 * 流程：產生摘要草稿 → 修改文字 → 勾「我已確認…」（review，帶畫面上的文字）→ 發布（只發布最新且已審閱的版本）
 */

const enc = encodeURIComponent

export type SummaryStatus = 'draft' | 'reviewed' | 'published' | 'withdrawn'

export interface SummaryGroup {
  group_id?: string
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
  summary: ClassSummary | null
}

export interface TeachingReport extends PersonalReport {
  student_display_name: string
  /** 這份報告屬於哪些觀點群組（#195 規格） */
  group_ids?: string[]
}

export interface TopicReports {
  class_size: number
  completed_count: number
  ready_count: number
  processing_count: number
  failed_count: number
  summary_version?: number | null
  groups?: { group_id: string; name: string; count: number }[]
  reports: TeachingReport[]
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

const AI_TIMEOUT = 120_000

export const summaryKeys = {
  reports: (topicId: string) => ['topics', topicId, 'reports'] as const,
  summary: (topicId: string, version?: number) =>
    ['topics', topicId, 'summary', version ?? 'latest'] as const,
  published: (topicId: string) => ['topics', topicId, 'summary', 'published'] as const,
}

export const summariesApi = {
  async reports(topicId: string) {
    const res = await apiClient.get<TopicReports>(`/topics/${enc(topicId)}/reports`)
    return res.data
  },
  async get(topicId: string, version?: number) {
    const res = await apiClient.get<TeacherSummaryResponse>(`/topics/${enc(topicId)}/summary`, {
      params: version ? { version } : undefined,
    })
    return res.data
  },
  /** 產生新的摘要草稿（第一次會結束學生作答） */
  async generate(topicId: string) {
    const res = await apiClient.post<TeacherSummaryResponse>(
      `/topics/${enc(topicId)}/summary`,
      null,
      { timeout: AI_TIMEOUT },
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
  /** 報告產生失敗時，老師幫學生重試（實作已有，規格還沒寫） */
  async retryReport(topicId: string, sessionId: string) {
    return apiClient.post(`/topics/${enc(topicId)}/reports/${enc(sessionId)}`)
  },
}
