import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError, AxiosHeaders } from 'axios'
import { API_BASE_URL } from '@/api/client'
import { summariesApi } from '@/api/summaries'
import { topicsApi } from '@/api/topics'
import { useChatStream } from '@/composables/useChatStream'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/lib/utils'

/** 前端對真後端格式的整理（後端 OpenAPI，main f762701） */
const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())
afterEach(() => server.resetHandlers())
beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.setItem('access_token', 'old-token')
})

const report = (id: string) => ({
  report_id: id,
  version: 1,
  session_id: `s-${id}`,
  topic_id: 't1',
  completed_turns: 3,
  final_viewpoint: '觀點',
})

function apiError(detail: unknown, status = 400) {
  const response = {
    status,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { detail },
  }
  return new AxiosError('fail', 'ERR', undefined, undefined, response)
}

describe('後端格式整理', () => {
  it('全班報告：巢狀的 { report_status, report } 攤平，只留已產生好的', async () => {
    server.use(
      http.get(`${API_BASE_URL}/topics/t1/reports`, () =>
        HttpResponse.json({
          class_size: 3,
          completed_count: 3,
          ready_count: 1,
          processing_count: 1,
          failed_count: 1,
          reports: [
            { report_status: 'ready', report: report('r1'), student_display_name: '王小明' },
            { report_status: 'processing', report: null, student_display_name: '李小華' },
            { report_status: 'failed', report: null, student_display_name: '陳小美' },
          ],
        }),
      ),
    )
    const data = await summariesApi.reports('t1')
    expect(data.ready_count).toBe(1)
    expect(data.reports).toEqual([{ ...report('r1'), student_display_name: '王小明' }])
  })

  it('活動設定：null 的文字欄位換成空字串', async () => {
    server.use(
      http.get(`${API_BASE_URL}/topics/t1/setup`, () =>
        HttpResponse.json({
          topic_id: 't1',
          course_id: 'c1',
          topic_status: 'setup',
          setup: { age_band: '16-18', max_turns: 10, topic: '題目', core_question: null },
        }),
      ),
    )
    const { setup } = await topicsApi.getSetup('t1')
    expect(setup).toMatchObject({
      age_band: '16-18',
      max_turns: 10,
      topic: '題目',
      core_question: '',
      exclusions: '',
      opening_message: '',
    })
  })

  it('錯誤訊息：後端的英文訊息都翻成介面文字（含帶變數的）', () => {
    expect(getApiErrorMessage(apiError('Turn cap reached'))).toBe('回合已經用完了')
    expect(
      getApiErrorMessage(apiError('Course teacher or TA with view_reports permission required')),
    ).toBe('你沒有這項功能的權限')
    expect(getApiErrorMessage(apiError('Incomplete setup: topic, exclusions'))).toBe(
      '活動設定還沒填完整',
    )
    expect(getApiErrorMessage(apiError('Request validation failed', 422))).not.toBe(
      'Request validation failed',
    )
  })

  it('串流：token 過期（401）先續期再用同一個 request_id 重送', async () => {
    const seen: { auth: string | null; body: unknown }[] = []
    server.use(
      http.post(`${API_BASE_URL}/sessions/s1/messages/stream`, async ({ request }) => {
        const auth = request.headers.get('Authorization')
        seen.push({ auth, body: await request.json() })
        if (auth !== 'Bearer new-token')
          return HttpResponse.json(
            { detail: 'Not authenticated or token expired' },
            { status: 401 },
          )
        const done = { message_id: 'm1', completed_turns: 1, is_completed: false }
        return new HttpResponse(`data: 你好\n\nevent: done\ndata: ${JSON.stringify(done)}\n\n`, {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
      http.get(`${API_BASE_URL}/users/me`, () =>
        HttpResponse.json(
          { account_id: 's001', name: '學生', role: ['USER'] },
          {
            headers: {
              Authorization: 'Bearer new-token',
              'Access-Control-Expose-Headers': 'Authorization',
            },
          },
        ),
      ),
    )
    useAuthStore().setAuth('old-token', {
      account_id: 's001',
      name: '學生',
      role: 'STUDENT',
      roles: ['STUDENT'],
      preferred_language: 'zh-TW',
      must_change_password: false,
    })
    let text = ''
    await useChatStream().streamMessage('s1', '回答', 'req-1', {
      onChunk: (chunk) => (text += chunk),
    })
    expect(text).toBe('你好')
    expect(seen.map((s) => s.auth)).toEqual(['Bearer old-token', 'Bearer new-token'])
    expect(seen.map((s) => (s.body as { request_id: string }).request_id)).toEqual([
      'req-1',
      'req-1',
    ])
  })
})
