import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import CourseView from '../CourseView.vue'
import { studentApi, type CourseTopics } from '@/api/student'

vi.mock('@/api/student', () => ({
  studentApi: { getCourseTopics: vi.fn<typeof studentApi.getCourseTopics>() },
}))
const getCourseTopics = vi.mocked(studentApi.getCourseTopics)
const course: CourseTopics = {
  course_id: 'course-1',
  name: '公民思辨',
  invite_code: 'CLASS1',
  topics: [
    {
      topic_id: 'topic-1',
      title: '民主與自由',
      description: '公共生活',
      status: 'ACTIVE',
      session_id: null,
      age_range: '12–18',
      round_count: 0,
    },
    {
      topic_id: 'topic-2',
      title: '社會責任',
      description: 'Responsibility',
      status: 'ACTIVE',
      session_id: null,
      age_range: '15–18',
      round_count: 5,
    },
  ],
}

describe('CourseView', () => {
  let client: QueryClient
  let router: Router
  let wrapper: VueWrapper | undefined
  let container: HTMLDivElement

  beforeEach(async () => {
    getCourseTopics.mockReset()
    client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/student/courses/:courseId', name: 'StudentCourse', component: CourseView },
        {
          path: '/student/chat/:questionId',
          name: 'StudentChat',
          component: { template: '<div />' },
        },
      ],
    })
    container = document.createElement('div')
    document.body.append(container)
    await router.push('/student/courses/course-1')
    await router.isReady()
  })

  afterEach(() => {
    wrapper?.unmount()
    client.clear()
    container.remove()
  })

  function mountView() {
    wrapper = mount(CourseView, {
      attachTo: container,
      global: { plugins: [router, [VueQueryPlugin, { queryClient: client }]] },
    })
    return wrapper
  }

  it('loads the selected course through Query and shows the supplied metadata', async () => {
    getCourseTopics.mockResolvedValueOnce({ data: course } as never)
    const view = mountView()
    expect(view.find('[role="status"]').text()).toBe('問題載入中…')
    expect(view.attributes('aria-busy')).toBe('true')
    await vi.waitFor(() => expect(view.findAll('li')).toHaveLength(2))
    expect(view.text()).toContain('年齡層：12–18')
    expect(view.text()).toContain('回合數：0')
    expect(getCourseTopics).toHaveBeenCalledWith('course-1', expect.any(AbortSignal))
    expect(view.attributes('aria-busy')).toBe('false')
  })

  it('filters titles and descriptions without another request and restores focus when cleared', async () => {
    getCourseTopics.mockResolvedValueOnce({ data: course } as never)
    const view = mountView()
    await vi.waitFor(() => expect(view.findAll('li')).toHaveLength(2))
    await view.find('input').setValue('  RESPONSIBILITY  ')
    expect(view.findAll('li')).toHaveLength(1)
    expect(view.find('li').text()).toContain('社會責任')
    await view.find('input').setValue('不存在的問題')
    expect(view.find('[role="status"]').text()).toBe('找不到符合搜尋的問題')
    await view.find('button[aria-label="清除搜尋"]').trigger('click')
    expect(view.findAll('li')).toHaveLength(2)
    expect(document.activeElement).toBe(view.find('input').element)
    expect(getCourseTopics).toHaveBeenCalledTimes(1)
  })

  it('clears the search with Escape', async () => {
    getCourseTopics.mockResolvedValueOnce({ data: course } as never)
    const view = mountView()
    await vi.waitFor(() => expect(view.findAll('li')).toHaveLength(2))
    await view.find('input').setValue('民主')
    await view.find('input').trigger('keydown', { key: 'Escape' })
    expect(view.findAll('li')).toHaveLength(2)
    expect((view.find('input').element as HTMLInputElement).value).toBe('')
  })

  it('distinguishes a course with no topics from unmatched search results', async () => {
    getCourseTopics.mockResolvedValueOnce({ data: { ...course, topics: [] } } as never)
    const view = mountView()
    await vi.waitFor(() => expect(view.find('[role="status"]').text()).toBe('這門課程目前沒有問題'))
    expect(view.find('li').exists()).toBe(false)
  })

  it('uses the API error detail and retries successfully', async () => {
    getCourseTopics.mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { detail: '尚未加入該課程' } },
    })
    getCourseTopics.mockResolvedValueOnce({ data: course } as never)
    const view = mountView()
    await vi.waitFor(() => expect(view.find('[role="alert"]').text()).toBe('尚未加入該課程'))
    await view.find('button:not([aria-label])').trigger('click')
    await vi.waitFor(() => expect(view.findAll('li')).toHaveLength(2))
    expect(getCourseTopics).toHaveBeenCalledTimes(2)
    expect(view.find('[role="alert"]').exists()).toBe(false)
  })

  it('uses the shared fallback for a network error', async () => {
    getCourseTopics.mockRejectedValueOnce(new Error('Network unavailable'))
    const view = mountView()
    await vi.waitFor(() =>
      expect(view.find('[role="alert"]').text()).toBe('課程載入失敗，請稍後再試'),
    )
  })

  it('fetches new course data and resets local search after a route change', async () => {
    getCourseTopics.mockResolvedValueOnce({ data: course } as never)
    getCourseTopics.mockResolvedValueOnce({
      data: {
        ...course,
        course_id: 'course-2',
        topics: [{ ...course.topics[0], topic_id: 'new', title: '新課程問題' }],
      },
    } as never)
    const view = mountView()
    await vi.waitFor(() => expect(view.findAll('li')).toHaveLength(2))
    await view.find('input').setValue('民主')
    await router.push('/student/courses/course-2')
    await vi.waitFor(() => expect(view.find('li').text()).toContain('新課程問題'))
    expect((view.find('input').element as HTMLInputElement).value).toBe('')
    expect(getCourseTopics.mock.calls.map(([id]) => id)).toEqual(['course-1', 'course-2'])
  })

  it('links to the topic route and retains course context', async () => {
    getCourseTopics.mockResolvedValueOnce({ data: course } as never)
    const view = mountView()
    await vi.waitFor(() => expect(view.findAll('li')).toHaveLength(2))
    await view.find('li a').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('StudentChat'))
    expect(router.currentRoute.value.params.questionId).toBe('topic-1')
    expect(router.currentRoute.value.query.courseId).toBe('course-1')
  })

  it('does not invent missing age or round counts', async () => {
    getCourseTopics.mockResolvedValueOnce({
      data: {
        ...course,
        topics: [
          {
            topic_id: 'missing',
            title: '未設定問題',
            description: '',
            status: 'ACTIVE',
            session_id: null,
          },
        ],
      },
    } as never)
    const view = mountView()
    await vi.waitFor(() => expect(view.find('li').exists()).toBe(true))
    expect(view.find('li').text()).toContain('年齡層：未提供')
    expect(view.find('li').text()).toContain('回合數：未提供')
  })
})
