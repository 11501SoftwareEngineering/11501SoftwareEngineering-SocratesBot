import { apiClient } from './client'
import { translate } from '@/i18n'

/**
 * 老師的 AI 金鑰、用量、預設模型（docs/API功能規格.md v0.2「AI 金鑰與用量」）。
 */

/** 用量的階段（規格沒有定義 by_stage 的格式，這是前端先假設的，後端做好後要核對） */
export type UsageStage = 'setup' | 'dialogue' | 'report' | 'summary'

export const USAGE_STAGES: { value: UsageStage; label: string }[] = (
  ['setup', 'dialogue', 'report', 'summary'] as const
).map((value) => ({
  value,
  get label() {
    return translate(`usageStages.${value}`)
  },
}))

export interface StageUsage {
  stage: UsageStage
  request_count: number
  total_tokens: number
  /** 規格沒寫；Figma 的「各階段用量」有輸入／輸出兩欄，後端有給就顯示 */
  input_tokens?: number
  output_tokens?: number
  cost_usd: number | null
}

export interface AiUsage {
  /** 例如 "2026-11" */
  month: string
  total_tokens: number
  input_tokens: number
  output_tokens: number
  request_count: number
  by_stage: StageUsage[]
  /** 沒有資料時是 null，不代表 0 */
  cost_usd: number | null
  cost_source: string | null
  updated_at: string | null
}

export interface AiSettings {
  configured: boolean
  masked_key: string | null
  updated_at: string | null
  default_model: { id: string; name: string } | null
}

export const aiKeys = {
  usage: ['ai', 'usage'] as const,
  settings: ['ai', 'settings'] as const,
}

export const aiApi = {
  async usage() {
    const res = await apiClient.get<AiUsage>('/users/me/ai/usage')
    return res.data
  },
  async settings() {
    const res = await apiClient.get<AiSettings>('/users/me/ai/settings')
    return res.data
  },
  async setApiKey(api_key: string) {
    const res = await apiClient.put<Omit<AiSettings, 'default_model'>>('/users/me/ai/api-key', {
      api_key,
    })
    return res.data
  },
  removeApiKey() {
    return apiClient.delete('/users/me/ai/api-key')
  },
  async setDefaultModel(model_id: string) {
    const res = await apiClient.patch<{ default_model: { id: string; name: string } }>(
      '/users/me/ai/model',
      { model_id },
    )
    return res.data
  },
}

/** 金額顯示：null 顯示「—」 */
export function formatUsd(value: number | null | undefined, digits = 2) {
  return value == null ? '—' : `US$${value.toFixed(digits)}`
}
