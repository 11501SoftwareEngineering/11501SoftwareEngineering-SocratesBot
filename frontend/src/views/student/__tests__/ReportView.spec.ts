import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ReportView from '../ReportView.vue'
import { sampleReport } from '@/data/sampleReport'

describe('student ReportView', () => {
  let router: Router
  let wrapper: VueWrapper | undefined
  const speak = vi.fn<(utterance: { text: string }) => void>()
  const cancel = vi.fn<() => void>()

  beforeEach(async () => {
    setActivePinia(createPinia())
    speak.mockReset()
    cancel.mockReset()
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
  })

  async function open(path: string) {
    await router.push(path)
    await router.isReady()
    wrapper = mount(ReportView, { global: { plugins: [router] } })
    await flushPromises()
    return wrapper
  }

  it('對話紀錄分頁依序顯示每一則訊息，AI 訊息有朗讀按鈕', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result/chat')

    const items = view.findAll('ol[aria-label="對話紀錄"] > li')
    expect(items).toHaveLength(sampleReport.messages.length)
    sampleReport.messages.forEach((message, i) => {
      expect(items[i]!.text()).toContain(message.content)
    })
    const aiCount = sampleReport.messages.filter((m) => m.sender === 'ai').length
    expect(view.findAll('button[aria-label="朗讀這則訊息"]')).toHaveLength(aiCount)
    expect(view.get('[aria-current="page"]').text()).toBe('對話紀錄')
  })

  it('按喇叭會朗讀，再按一次會停止', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result/chat')

    await view.get('button[aria-label="朗讀這則訊息"]').trigger('click')
    expect(speak).toHaveBeenCalledTimes(1)
    expect(speak.mock.calls[0]![0].text).toBe(sampleReport.messages[0]!.content)

    await view.get('button[aria-label="停止朗讀"]').trigger('click')
    expect(cancel).toHaveBeenCalled()
    expect(view.find('button[aria-label="停止朗讀"]').exists()).toBe(false)
  })

  it('沒指定分頁時是「個人報告」，還沒做的分頁顯示製作中', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result')

    expect(view.get('[aria-current="page"]').text()).toBe('個人報告')
    expect(view.text()).toContain('個人報告製作中')
    expect(view.find('ol[aria-label="對話紀錄"]').exists()).toBe(false)
  })

  it('麵包屑連回我的課程和課程頁', async () => {
    const view = await open('/student/courses/course-1/sessions/s1/result/chat')

    const links = view.findAll('nav[aria-label="目前位置"] a')
    expect(links.map((a) => a.attributes('href'))).toEqual([
      '/student/courses',
      '/student/courses/course-1',
    ])
  })
})
