import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import AiUsagePanel from '../AiUsagePanel.vue'
import { aiApi } from '@/api/ai'
import { topicsApi } from '@/api/topics'

type AiModule = typeof import('@/api/ai')
type TopicsModule = typeof import('@/api/topics')

vi.mock('@/api/ai', async (importOriginal) => {
  const actual = await importOriginal<AiModule>()
  return {
    ...actual,
    aiApi: {
      usage: vi.fn<AiModule['aiApi']['usage']>(),
      settings: vi.fn<AiModule['aiApi']['settings']>(),
      setDefaultModel: vi.fn<AiModule['aiApi']['setDefaultModel']>(),
    },
  }
})
vi.mock('@/api/topics', async (importOriginal) => {
  const actual = await importOriginal<TopicsModule>()
  return { ...actual, topicsApi: { models: vi.fn<TopicsModule['topicsApi']['models']>() } }
})

describe('AiUsagePanel', () => {
  it('用量不明（後端回 null）時顯示「—」，卡片不會因為渲染失敗而消失', async () => {
    vi.mocked(aiApi.usage).mockResolvedValue({
      month: '2026-11',
      request_count: 2,
      input_tokens: null,
      output_tokens: 120,
      total_tokens: null,
      cost_usd: null,
      cost_source: null,
      updated_at: null,
      by_stage: [],
    })
    vi.mocked(aiApi.settings).mockResolvedValue({
      configured: true,
      masked_key: null,
      updated_at: null,
      default_model: null,
    })
    vi.mocked(topicsApi.models).mockResolvedValue([])
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/ai', name: 'TeacherAiSettings', component: { template: '<div />' } },
      ],
    })
    // 先把資料放進快取：從其他頁回來時就是這個情況（第一次渲染就有資料）
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    await client.prefetchQuery({ queryKey: ['ai', 'usage'], queryFn: aiApi.usage })
    const wrapper = mount(AiUsagePanel, {
      global: { plugins: [router, [VueQueryPlugin, { queryClient: client }]] },
    })
    await flushPromises()
    const values = wrapper.findAll('dd').map((d) => d.text())
    expect(values).toContain('120')
    expect(values.filter((v) => v === '—').length).toBeGreaterThanOrEqual(2)
  })
})
