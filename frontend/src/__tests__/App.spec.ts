import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from '../App.vue'

const stub = { template: '<div />' }
// App 的測試只看 Header、Footer 和共用資料，頁面本身用簡單的替身
const AnnouncementsView = { template: '<h1>公告</h1>' }

function createAppRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'Home', component: AnnouncementsView },
      { path: '/login', name: 'Login', component: stub },
      { path: '/register', name: 'Register', component: stub },
      { path: '/student/courses', name: 'StudentCourses', component: stub },
      { path: '/student/courses/:courseId', name: 'StudentCourse', component: stub },
      { path: '/student/courses/:courseId/topics/:topicId', name: 'StudentChat', component: stub },
    ],
  })
}

describe('App', () => {
  let wrapper: VueWrapper | undefined
  let queryClient: QueryClient | undefined

  afterEach(() => {
    wrapper?.unmount()
    queryClient?.clear()
    vi.clearAllMocks()
  })

  it('未登入時顯示公告、註冊和登入按鈕、頁尾', async () => {
    const router = createAppRouter()
    queryClient = new QueryClient()
    await router.push('/')
    await router.isReady()
    wrapper = mount(App, {
      global: { plugins: [createPinia(), router, [VueQueryPlugin, { queryClient }]] },
    })

    await vi.waitFor(() => expect(wrapper?.find('main h1').text()).toBe('公告'))
    expect(wrapper.find('header').text()).toContain('問導魷')
    expect(wrapper.find('header a[href="/login"]').text()).toBe('登入')
    expect(wrapper.find('header a[href="/register"]').text()).toBe('註冊')
    expect(wrapper.find('footer').text()).toContain('隱私權')
  })

  it('登入後 Header 顯示語言切換和帳號，不放導覽（照 Figma）', async () => {
    const router = createAppRouter()
    const pinia = createPinia()
    pinia.state.value.auth = {
      token: 'test-token',
      user: {
        account_id: 's1',
        name: '王小明',
        role: 'STUDENT',
        roles: ['STUDENT'],
        preferred_language: 'zh-TW',
        must_change_password: false,
      },
    }
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    await router.push('/student/courses/course-1')
    await router.isReady()
    wrapper = mount(App, {
      global: { plugins: [pinia, router, [VueQueryPlugin, { queryClient }]] },
    })

    const header = wrapper.find('header')
    expect(header.text()).toContain('王小明')
    expect(header.find('[aria-label="介面語言：正體中文"]').exists()).toBe(true)
    expect(header.find('nav').exists()).toBe(false)
  })
})
