import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import LoginView from '../LoginView.vue'

// 這是重點:把真正打 API 的 authApi 換成假的(vi.mock),
// 這樣測試的時候完全不會發出真正的網路請求,不需要後端跑起來。
vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
  },
}))

import { authApi } from '@/api/auth'

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: { template: '<div />' } },
      { path: '/student/courses', component: { template: '<div />' } },
      { path: '/teacher/dashboard', component: { template: '<div />' } },
      { path: '/admin/users', component: { template: '<div />' } },
    ],
  })
}

describe('LoginView', () => {
  let router: Router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createTestRouter()
    vi.mocked(authApi.login).mockReset()
  })

  it('帳號密碼錯誤時,畫面要顯示錯誤訊息', async () => {
    // 模擬後端回傳 401 帳號密碼錯誤
    vi.mocked(authApi.login).mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { detail: '帳號或密碼錯誤' } },
    })

    await router.push('/login')
    const wrapper = mount(LoginView, { global: { plugins: [router] } })

    await wrapper.find('input[placeholder="請輸入帳號"]').setValue('wrong')
    await wrapper.find('input[placeholder="請輸入密碼"]').setValue('wrong')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('帳號或密碼錯誤')
  })

  it('登入成功後,要導向學生的課程列表頁', async () => {
    // 模擬後端回傳成功登入的學生資料
    vi.mocked(authApi.login).mockResolvedValueOnce({
      data: {
        access_token: 'fake-token',
        account: 's1',
        name: '王小明',
        role: 'STUDENT',
      },
    } as never)

    await router.push('/login')
    const wrapper = mount(LoginView, { global: { plugins: [router] } })

    await wrapper.find('input[placeholder="請輸入帳號"]').setValue('s1')
    await wrapper.find('input[placeholder="請輸入密碼"]').setValue('correct')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/student/courses')
  })
})
