import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import AiSettingsView from '../AiSettingsView.vue'
import { aiApi, type AiSettings, type AiUsage } from '@/api/ai'
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
      setApiKey: vi.fn<AiModule['aiApi']['setApiKey']>(),
      removeApiKey: vi.fn<AiModule['aiApi']['removeApiKey']>(),
      setDefaultModel: vi.fn<AiModule['aiApi']['setDefaultModel']>(),
    },
  }
})
vi.mock('@/api/topics', async (importOriginal) => {
  const actual = await importOriginal<TopicsModule>()
  return { ...actual, topicsApi: { models: vi.fn<TopicsModule['topicsApi']['models']>() } }
})

const usage: AiUsage = {
  month: '2026-11',
  total_tokens: 1500,
  input_tokens: 1000,
  output_tokens: 500,
  request_count: 3,
  by_stage: [
    {
      stage: 'dialogue',
      request_count: 3,
      total_tokens: 1500,
      input_tokens: 1000,
      output_tokens: 500,
      cost_usd: 0.01,
    },
  ],
  cost_usd: 0.01,
  cost_source: 'estimate',
  updated_at: '2026-11-16T08:00:00Z',
}
const configured: AiSettings = {
  configured: true,
  masked_key: 'sk-or-****ABCD',
  updated_at: null,
  default_model: { id: 'm1', name: '模型一' },
}

describe('teacher AiSettingsView（P14）', () => {
  let wrapper: VueWrapper | undefined

  async function mountView() {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/teacher/ai-settings', name: 'TeacherAiSettings', component: AiSettingsView },
        { path: '/teacher/courses', name: 'TeacherCourses', component: { template: '<div />' } },
      ],
    })
    await router.push('/teacher/ai-settings')
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    wrapper = mount(AiSettingsView, {
      global: { plugins: [router, [VueQueryPlugin, { queryClient: client }]] },
      attachTo: document.body,
    })
    await flushPromises()
    return wrapper
  }

  beforeEach(() => {
    vi.mocked(aiApi.usage).mockResolvedValue(usage)
    vi.mocked(topicsApi.models).mockResolvedValue([
      {
        model_id: 'm1',
        name: '模型一',
        description: '說明',
        provider_id: 'p',
        input_price_usd: 0.4,
        output_price_usd: 1.6,
      },
    ])
  })
  afterEach(() => {
    wrapper?.unmount()
    vi.clearAllMocks()
  })

  it('顯示本月用量、各階段用量、遮罩後的 key 與目前預設模型', async () => {
    vi.mocked(aiApi.settings).mockResolvedValue(configured)
    const w = await mountView()
    expect(w.text()).toContain('2026 年 11 月')
    expect(w.text()).toContain('1,500')
    expect(w.text()).toContain('已設定')
    expect(w.text()).toContain('sk-or-****ABCD')
    expect(w.text()).toContain('目前預設')
    const dialogueRow = w.findAll('tbody tr').find((tr) => tr.text().includes('學生對話'))
    expect(dialogueRow?.text()).toContain('1,000')
    // 沒有用到的階段顯示「—」，不顯示 0
    expect(
      w
        .findAll('tbody tr')
        .find((tr) => tr.text().includes('課程設定'))
        ?.text(),
    ).toContain('—')
  })

  it('沒有 key 時顯示「尚未設定」、沒有移除按鈕，空白送出會提示', async () => {
    vi.mocked(aiApi.settings).mockResolvedValue({
      ...configured,
      configured: false,
      masked_key: null,
    })
    const w = await mountView()
    expect(w.text()).toContain('尚未設定')
    expect(w.findAll('button').some((b) => b.text() === '移除')).toBe(false)
    await w.find('form').trigger('submit')
    expect(w.text()).toContain('請輸入 API key')
    expect(aiApi.setApiKey).not.toHaveBeenCalled()
  })

  it('輸入新的 key 後儲存', async () => {
    vi.mocked(aiApi.settings).mockResolvedValue(configured)
    vi.mocked(aiApi.setApiKey).mockResolvedValue({
      configured: true,
      masked_key: 'x',
      updated_at: null,
    })
    const w = await mountView()
    await w.find('#api-key').setValue(' sk-or-new-key-123 ')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(aiApi.setApiKey).toHaveBeenCalledWith('sk-or-new-key-123')
    expect(w.text()).toContain('API key 已儲存')
  })
})
