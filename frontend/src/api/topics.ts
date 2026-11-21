import { apiClient } from './client'
import type { AgeBand, MaxTurns, TopicStatus } from './courses'

/**
 * 題目（探究活動）：建立、設定、發布（docs/API功能規格.md v0.2「題目」「題目設定階段」）。
 *
 * 「所見即所存」：AI 重新產生只回傳結果、不存檔；按「儲存」或「發布」才把畫面上的 setup 存進去。
 */

const enc = encodeURIComponent

/** 題目八欄設定 */
export interface TopicSetup {
  age_band: AgeBand
  max_turns: MaxTurns
  topic: string
  core_question: string
  inquiry_focus: string
  background_info: string
  exclusions: string
  opening_message: string
}

/** GET /topics/{topicId}/setup */
export interface TopicSetupResponse {
  topic_id: string
  course_id: string
  topic_status: TopicStatus
  model_id?: string | null
  setup: TopicSetup
}

export interface CreateTopicPayload {
  age_band: AgeBand
  max_turns: MaxTurns
  course_description: string
  /** Figma 沒有這兩個欄位：送目前的介面語言、老師的預設模型（有設定才送） */
  content_language?: string
  model_id?: string
}

export interface TopicExplanation {
  topic_id: string
  title: string
  background: string
  key_terms: string[]
}

export interface InquiryModel {
  model_id: string
  name: string
  description: string
  provider_id: string
  /** 每百萬 token 的價格（美元） */
  input_price_usd: number
  output_price_usd: number
}

/** 欄位名稱 → 畫面上的標題（Figma「確認活動設定」） */
export const SETUP_FIELDS: { key: keyof TopicSetup; label: string }[] = [
  { key: 'topic', label: '主題' },
  { key: 'core_question', label: '核心問題' },
  { key: 'inquiry_focus', label: '探究重點' },
  { key: 'background_info', label: '背景資訊' },
  { key: 'exclusions', label: '排除事項' },
  { key: 'opening_message', label: '開場訊息' },
]

/** 課程描述、對話內容的字數上限 */
export const LONG_TEXT_MAX = 6000

/** AI 產生設定可能要等幾十秒，這幾支 API 的逾時拉長到 2 分鐘 */
const AI_TIMEOUT = 120_000

export const topicKeys = {
  setup: (topicId: string) => ['topics', topicId, 'setup'] as const,
  explanation: (topicId: string) => ['topics', topicId, 'explanation'] as const,
  models: ['inquiry-models'] as const,
}

/**
 * 後端有的版本把 opening_message 放在最外層（規格有兩種寫法），這裡統一放進 setup。
 */
function normalize(data: TopicSetupResponse & { opening_message?: string | null }) {
  const opening = data.setup?.opening_message ?? data.opening_message ?? ''
  return { ...data, setup: { ...data.setup, opening_message: opening } } as TopicSetupResponse
}

export const topicsApi = {
  /** 新增活動：AI 依課程描述產生八欄設定並建立草稿 */
  async create(courseId: string, payload: CreateTopicPayload) {
    const res = await apiClient.post<TopicSetupResponse>(
      `/courses/${enc(courseId)}/topics`,
      payload,
      { timeout: AI_TIMEOUT },
    )
    return normalize(res.data)
  },
  remove(topicId: string) {
    return apiClient.delete(`/topics/${enc(topicId)}`)
  },
  async getSetup(topicId: string) {
    const res = await apiClient.get<TopicSetupResponse>(`/topics/${enc(topicId)}/setup`)
    return normalize(res.data)
  },
  /** 儲存草稿 */
  async saveSetup(topicId: string, setup: TopicSetup) {
    const res = await apiClient.put<TopicSetupResponse>(`/topics/${enc(topicId)}/setup`, { setup })
    return normalize(res.data)
  },
  /** 依老師回饋重新產生：帶畫面上的 setup，結果只回傳、不存檔 */
  async refine(topicId: string, setup: TopicSetup, feedback: string) {
    const res = await apiClient.post<TopicSetupResponse>(
      `/topics/${enc(topicId)}/setup/refine`,
      { setup, feedback },
      { timeout: AI_TIMEOUT },
    )
    return normalize(res.data)
  },
  /** 重新產生開場訊息：帶畫面上的 setup，不存檔 */
  async openingMessage(topicId: string, setup: TopicSetup) {
    const res = await apiClient.post<{ opening_message: string }>(
      `/topics/${enc(topicId)}/setup/opening-message`,
      { setup },
      { timeout: AI_TIMEOUT },
    )
    return res.data.opening_message
  },
  /** 發布：先存畫面上的 setup 再發布 */
  async publish(topicId: string, setup: TopicSetup) {
    const res = await apiClient.post<TopicSetupResponse>(`/topics/${enc(topicId)}/publish`, {
      setup,
    })
    return normalize(res.data)
  },
  async explanation(topicId: string) {
    const res = await apiClient.get<TopicExplanation>(`/topics/${enc(topicId)}/explanation`)
    return res.data
  },
  async models() {
    const res = await apiClient.get<InquiryModel[]>('/inquiry-models')
    return res.data
  },
}
