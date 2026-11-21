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

/** 全班報告表格的一列：個人報告加上學生姓名（前端把後端的巢狀格式攤平成這樣） */
export interface TeachingReport extends PersonalReport {
  student_display_name: string
}

/** GET /topics/{topicId}/reports 後端原始格式：每一筆是 { report_status, report, student_display_name } */
interface TopicReportsResponse {
  class_size: number
  completed_count: number
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

/** 學生報告分頁用來篩選的觀點群組：從摘要的 groups 來（後端沒有 group_id，用順序當代號） */
export interface ReportGroup {
  group_id: string
  name: string
  report_ids: string[]
}

export function reportGroups(summary: ClassSummary | null | undefined): ReportGroup[] {
  return (summary?.groups ?? []).map((g, i) => ({
    group_id: g.group_id ?? `g${i + 1}`,
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

const AI_TIMEOUT = 120_000

export const summaryKeys = {
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
  /** 報告產生失敗時，老師幫學生重試：POST /topics/{topicId}/reports/{sessionId} */
  async retryReport(topicId: string, sessionId: string) {
    return apiClient.post(`/topics/${enc(topicId)}/reports/${enc(sessionId)}`)
  },
}
