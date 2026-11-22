import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import ReportView from '../ReportView.vue'
import { coursesApi } from '@/api/courses'
import { sessionsApi, type PersonalReport, type SessionMessage } from '@/api/sessions'
import { summariesApi } from '@/api/summaries'

vi.mock('@/api/courses', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/courses')>()),
  coursesApi: { topics: vi.fn<(typeof import('@/api/courses'))['coursesApi']['topics']>() },
}))
vi.mock('@/api/sessions', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/sessions')>()),
  sessionsApi: {
    messages: vi.fn<(typeof import('@/api/sessions'))['sessionsApi']['messages']>(),
    report: vi.fn<(typeof import('@/api/sessions'))['sessionsApi']['report']>(),
    startReport: vi.fn<(typeof import('@/api/sessions'))['sessionsApi']['startReport']>(),
  },
}))
vi.mock('@/api/summaries', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/summaries')>()),
  summariesApi: {
    published: vi.fn<(typeof import('@/api/summaries'))['summariesApi']['published']>(),
  },
}))

const messages: SessionMessage[] = [
  {
    message_id: 'm1',
    sender: 'ai',
    content: '你覺得善意的謊言可以嗎？',
    created_at: '2026-11-10T10:00:00Z',
  },
  {
    message_id: 'm2',
    sender: 'student',
    content: '要看情況。',
    created_at: '2026-11-10T10:01:00Z',
  },
  {
    message_id: 'm3',
    sender: 'ai',
    content: '什麼情況下不行？',
    created_at: '2026-11-10T10:02:00Z',
  },
]

const report: PersonalReport = {
  report_id: 'r1',
  version: 1,
  session_id: 's1',
  topic_id: 't1',
  anonymous_id: '學生 A',
  completed_at: '2026-11-10T10:05:00Z',
  completed_turns: 1,
  completion_reason: 'goal_reached',
  viewpoint_summary: '你認為要看情況。',
  final_viewpoint: '要看情況決定',
  viewpoint_status: '已表達立場',
  reasons: [],
  strongest_reason: '信任很重要',
  challenges: [{ challenge: '如果永遠不會被發現呢？', responded: true }],
  revision_or_defense: null,
  focus_connection: null,
  other_perspectives: null,
  open_questions: ['什麼事情重要到一定要說實話？'],
  evidence_status: 'partial',
  limitations: '回合數較少。',
  timeline: [
    {
      turn: 1,
      question: '你覺得善意的謊言可以嗎？',
      evidence: [{ message_id: 'm2', turn: 1, quote: '要看情況。' }],
      viewpoint_before: null,
      viewpoint_after: '初步觀點：要看情況',
      change_type: '初步表態',
      attribution: 'none',
    },
  ],
}

describe('student ReportView（P08）', () => {
  let router: Router
  let wrapper: VueWrapper | undefined
  const speak = vi.fn<(utterance: { text: string }) => void>()
  const cancel = vi.fn<() => void>()

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('speechSynthesis', { speak, cancel })
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        lang = ''
        onend: (() => void) | null = null
        onerror: (() => void) | null = null
        constructor(public text: string) {}
      },
    )
    vi.mocked(coursesApi.topics).mockResolvedValue({
      course_id: 'course-1',
      name: '哲學概論',
      invite_code: 'PHSP3456',
      my_role: 'student',
      my_permissions: [],
      topics: [
        {
          topic_id: 't1',
          title: '善意的謊言',
          description: null,
          topic_status: 'summary',
          age_band: '16-18',
          max_turns: 5,
          session_status: 'COMPLETED',
          session_id: 's1',
        },
      ],
    })
    vi.mocked(sessionsApi.messages).mockResolvedValue({
      messages,
      session_status: 'completed',
      max_turns: 5,
      completed_turns: 1,
      goal_reached: true,
      awaiting_end_consent: false,
    })
    vi.mocked(sessionsApi.startReport).mockResolvedValue({ report_status: 'ready', report })
    vi.mocked(sessionsApi.report).mockResolvedValue({ report_status: 'ready', report })
    vi.mocked(summariesApi.published).mockResolvedValue(null)
    const stub = { template: '<div />' }
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/student/courses', name: 'StudentCourses', component: stub },
        { path: '/student/courses/:courseId', name: 'StudentCourse', component: stub },
        {
          path: '/student/courses/:courseId/sessions/:sessionId/result/:tab(personal|chat|summary)?',
          name: 'StudentReport',
          component: ReportView,
        },
      ],
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  async function open(path: string) {
    await router.push(path)
    await router.isReady()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    wrapper = mount(ReportView, {
      global: { plugins: [router, [VueQueryPlugin, { queryClient: client }]] },
    })
    await flushPromises()
    return wrapper
  }

  it('標題是這次對話的題目，麵包屑連回課程', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result/chat')
    expect(view.find('h2').text()).toBe('善意的謊言')
    const links = view.findAll('nav[aria-label="目前位置"] a')
    expect(links.map((a) => a.attributes('href'))).toEqual([
      '/student/courses',
      '/student/courses/course-1',
    ])
  })

  it('對話紀錄：每一則訊息都在，AI 訊息可以朗讀', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result/chat')
    expect(view.findAll('ol[aria-label="對話紀錄"] > li')).toHaveLength(3)
    expect(view.findAll('button[aria-label="朗讀這則訊息"]')).toHaveLength(2)
    await view.get('button[aria-label="朗讀這則訊息"]').trigger('click')
    expect(speak).toHaveBeenCalledTimes(1)
    expect(view.get('[aria-current="page"]').text()).toBe('對話紀錄')
  })

  it('個人報告：顯示觀點、時間軸、證據不足的提醒，展開看到學生原話', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result')
    expect(view.get('[aria-current="page"]').text()).toBe('個人報告')
    expect(view.text()).toContain('要看情況決定')
    expect(view.text()).toContain('觀點變化時間軸')
    expect(view.text()).toContain('未完成或證據不足')
    await view.get('button[aria-expanded="false"]').trigger('click')
    expect(view.text()).toContain('要看情況。')
  })

  it('報告還在產生時顯示整理中', async () => {
    vi.mocked(sessionsApi.startReport).mockResolvedValue({
      report_status: 'processing',
      report: null,
    })
    const view = await open('/student/courses/course-1/sessions/s1/result/personal')
    expect(view.text()).toContain('導魷正在整理你的報告')
  })

  it('進個人報告先 POST 開始產生（結束對話不會自動產生），不是只用 GET 查', async () => {
    await open('/student/courses/course-1/sessions/s1/result/personal')
    expect(sessionsApi.startReport).toHaveBeenCalledTimes(1)
    expect(sessionsApi.startReport).toHaveBeenCalledWith('s1')
    expect(sessionsApi.report).not.toHaveBeenCalled()
  })

  it('產生失敗時按「重新產生」再 POST 一次', async () => {
    vi.mocked(sessionsApi.startReport)
      .mockResolvedValueOnce({ report_status: 'failed', report: null })
      .mockResolvedValueOnce({ report_status: 'processing', report: null })
    const view = await open('/student/courses/course-1/sessions/s1/result/personal')
    const retry = view.findAll('button').find((b) => b.text().includes('重新產生'))
    expect(retry).toBeTruthy()
    await retry!.trigger('click')
    await flushPromises()
    expect(sessionsApi.startReport).toHaveBeenCalledTimes(2)
    expect(view.text()).toContain('導魷正在整理你的報告')
  })

  it('拿不到報告（對話還沒完成）：顯示原因和「回到課程」，不給重新載入', async () => {
    vi.mocked(sessionsApi.startReport).mockRejectedValue(
      new AxiosError('fail', 'ERR', undefined, undefined, {
        status: 409,
        statusText: '',
        headers: {},
        config: { headers: new AxiosHeaders() },
        data: { detail: 'Dialogue is not completed' },
      }),
    )
    const view = await open('/student/courses/course-1/sessions/s1/result/personal')
    expect(view.text()).toContain('對話還沒結束')
    const back = view.findAll('a').find((a) => a.text() === '回到課程')
    expect(back?.attributes('href')).toBe('/student/courses/course-1')
    expect(view.findAll('button').some((b) => b.text().includes('重新載入'))).toBe(false)
  })

  it('網路錯誤：顯示網路問題，可以重新載入', async () => {
    vi.mocked(sessionsApi.startReport).mockRejectedValue(
      new AxiosError('Network Error', 'ERR_NETWORK'),
    )
    const view = await open('/student/courses/course-1/sessions/s1/result/personal')
    expect(view.text()).not.toContain('無法取得個人報告')
    expect(view.findAll('button').some((b) => b.text().includes('重新載入'))).toBe(true)
  })

  it('重新產生也失敗時顯示錯誤', async () => {
    vi.mocked(sessionsApi.startReport)
      .mockResolvedValueOnce({ report_status: 'failed', report: null })
      .mockRejectedValueOnce(new AxiosError('Network Error', 'ERR_NETWORK'))
    const view = await open('/student/courses/course-1/sessions/s1/result/personal')
    await view
      .findAll('button')
      .find((b) => b.text().includes('重新產生'))!
      .trigger('click')
    await flushPromises()
    expect(view.find('[role="alert"]').exists()).toBe(true)
  })

  it('老師還沒發布全班摘要時告訴學生', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result/summary')
    expect(view.text()).toContain('老師還沒有發布全班摘要')
  })
})
