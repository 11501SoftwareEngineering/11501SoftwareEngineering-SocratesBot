import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import CourseView from '../CourseView.vue'
import { coursesApi, type CourseTopics } from '@/api/courses'

vi.mock('@/api/courses', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/courses')>()
  return {
    ...actual,
    coursesApi: {
      get: vi.fn<(typeof import('@/api/courses'))['coursesApi']['get']>(),
      topics: vi.fn<(typeof import('@/api/courses'))['coursesApi']['topics']>(),
    },
  }
})

const course: CourseTopics = {
  course_id: 'course-1',
  name: '公民思辨',
  invite_code: 'CLASS234',
  my_role: 'student',
  my_permissions: [],
  topics: [
    {
      topic_id: 't1',
      title: '民主與自由',
      description: '多數決公平嗎？',
      topic_status: 'conversation',
      age_band: '13-15',
      max_turns: 5,
      session_status: null,
      session_id: null,
    },
    {
      topic_id: 't2',
      title: '社會責任',
      description: '誰該負責？',
      topic_status: 'conversation',
      age_band: '16-18',
      max_turns: 10,
      session_status: 'IN_PROGRESS',
      session_id: 's2',
    },
    {
      topic_id: 't3',
      title: '善意的謊言',
      description: '可以說謊嗎？',
      topic_status: 'summary',
      age_band: '16-18',
      max_turns: 5,
      session_status: 'COMPLETED',
      session_id: 's3',
    },
    {
      topic_id: 't4',
      title: '公平',
      description: '一樣多就公平？',
      topic_status: 'summary',
      age_band: '13-15',
      max_turns: 5,
      session_status: null,
      session_id: null,
    },
  ],
}

describe('student CourseView（P06）', () => {
  let router: Router
  let wrapper: VueWrapper | undefined

  beforeEach(async () => {
    vi.mocked(coursesApi.topics).mockResolvedValue(course)
    vi.mocked(coursesApi.get).mockResolvedValue({
      course_id: 'course-1',
      name: '公民思辨',
      description: '討論公共議題',
      teacher_name: '王老師',
      my_role: 'student',
      my_permissions: [],
      invite_code: 'CLASS234',
    })
    const stub = { template: '<div />' }
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/student/courses', name: 'StudentCourses', component: stub },
        { path: '/student/courses/:courseId', name: 'StudentCourse', component: CourseView },
        {
          path: '/student/courses/:courseId/topics/:topicId',
          name: 'StudentChat',
          component: stub,
        },
        {
          path: '/student/courses/:courseId/sessions/:sessionId/result/:tab?',
          name: 'StudentReport',
          component: stub,
        },
      ],
    })
    await router.push('/student/courses/course-1')
    await router.isReady()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    wrapper = mount(CourseView, {
      global: { plugins: [router, [VueQueryPlugin, { queryClient: client }]] },
    })
    await flushPromises()
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.clearAllMocks()
  })

  it('顯示課程名稱、描述和活動數量', () => {
    expect(wrapper!.find('h1').text()).toBe('公民思辨')
    expect(wrapper!.text()).toContain('討論公共議題')
    expect(wrapper!.findAll('article')).toHaveLength(4)
  })

  it('依作答狀態顯示標籤和連結', () => {
    const cards = wrapper!.findAll('article')
    expect(cards[0]!.text()).toContain('尚未開始')
    expect(cards[0]!.find('a').attributes('href')).toBe('/student/courses/course-1/topics/t1')
    expect(cards[1]!.text()).toContain('進行中')
    expect(cards[1]!.text()).toContain('繼續探究')
    expect(cards[2]!.text()).toContain('已完成')
    expect(cards[2]!.find('a').attributes('href')).toBe(
      '/student/courses/course-1/sessions/s3/result/personal',
    )
    expect(cards[3]!.text()).toContain('已結束')
    expect(cards[3]!.find('a').exists()).toBe(false)
  })

  it('搜尋只留下符合的活動', async () => {
    await wrapper!.find('input[type="search"]').setValue('謊言')
    expect(wrapper!.findAll('article')).toHaveLength(1)
  })
})
