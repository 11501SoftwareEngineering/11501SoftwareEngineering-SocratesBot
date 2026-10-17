import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from '../App.vue'
import AnnouncementsView from '@/views/common/AnnouncementsView.vue'
import CourseView from '@/views/student/CourseView.vue'
import { studentApi } from '@/api/student'

vi.mock('@/api/student', () => ({
  studentApi: { getCourseTopics: vi.fn<typeof studentApi.getCourseTopics>() },
}))

describe('App', () => {
  let wrapper: VueWrapper | undefined
  let queryClient: QueryClient | undefined

  afterEach(() => {
    wrapper?.unmount()
    queryClient?.clear()
    vi.clearAllMocks()
  })

  it('renders the public announcements with the shared header and footer', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', alias: '/announcements', component: AnnouncementsView },
        { path: '/login', component: { template: '<div />' } },
      ],
    })
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    })
    await router.push('/')
    await router.isReady()

    wrapper = mount(App, {
      global: { plugins: [createPinia(), router, [VueQueryPlugin, { queryClient }]] },
    })

    await vi.waitFor(() => expect(wrapper?.find('article').text()).toContain('課程頁面預覽'))
    expect(wrapper.find('header').text()).toContain('問導魷')
    expect(wrapper.find('header a[href="/login"]').text()).toBe('登入')
    expect(wrapper.find('footer').text()).toContain('隱私權')
    expect(studentApi.getCourseTopics).not.toHaveBeenCalled()
  })
  it('shares the student course request between the header and page', async () => {
    vi.mocked(studentApi.getCourseTopics).mockResolvedValueOnce({
      data: {
        course_id: 'course-1',
        name: '公民思辨',
        invite_code: 'CLASS1',
        topics: [
          {
            topic_id: 'topic-1',
            title: '課程問題',
            description: '',
            status: 'ACTIVE',
            session_id: null,
          },
        ],
      },
    } as never)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', alias: '/announcements', component: AnnouncementsView },
        { path: '/student/courses', name: 'StudentCourses', component: { template: '<div />' } },
        { path: '/student/courses/:courseId', name: 'StudentCourse', component: CourseView },
        {
          path: '/student/chat/:questionId',
          name: 'StudentChat',
          component: { template: '<div />' },
        },
        { path: '/login', component: { template: '<div />' } },
      ],
    })
    const pinia = createPinia()
    pinia.state.value.auth = {
      token: 'test-token',
      user: { id: 's1', email: 's1', name: '學生', role: 'STUDENT' },
    }
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    })
    await router.push('/student/courses/course-1')
    await router.isReady()
    wrapper = mount(App, {
      global: { plugins: [pinia, router, [VueQueryPlugin, { queryClient }]] },
    })

    await vi.waitFor(() => expect(wrapper?.find('li').text()).toContain('課程問題'))
    expect(wrapper.find('header nav').text()).toContain('公民思辨')
    expect(wrapper.find('header nav a').attributes('href')).toBe('/student/courses')
    expect(studentApi.getCourseTopics).toHaveBeenCalledTimes(1)
    await wrapper.find('header a[href="/announcements"]').trigger('click')
    await vi.waitFor(() => expect(wrapper?.find('main h1').text()).toBe('公告'))
    expect(router.currentRoute.value.path).toBe('/announcements')
    expect(wrapper.find('article').text()).toContain('課程頁面預覽')
    expect(studentApi.getCourseTopics).toHaveBeenCalledTimes(1)
    await router.push('/announcements?courseId=another-course')
    await flushPromises()
    expect(wrapper.find('main h1').text()).toBe('公告')
    expect(studentApi.getCourseTopics).toHaveBeenCalledTimes(1)
  })
})
