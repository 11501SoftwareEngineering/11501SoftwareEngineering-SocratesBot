import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import LoginView from '../LoginView.vue'
import { authApi, type User } from '@/api/auth'
import { coursesApi, type CourseSummary } from '@/api/courses'

// 把真正打 API 的 authApi.login 換成假的，測試時不會發出網路請求、不需要後端
vi.mock('@/api/auth', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/auth')>()
  return { ...actual, authApi: { ...actual.authApi, login: vi.fn<typeof actual.authApi.login>() } }
})
// 學生登入後會查課程列表，判斷是不是助教（決定首頁）
vi.mock('@/api/courses', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/courses')>()
  return {
    ...actual,
    coursesApi: { ...actual.coursesApi, list: vi.fn<typeof actual.coursesApi.list>() },
  }
})

const stub = { template: '<div />' }

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'Login', component: LoginView },
      { path: '/register', name: 'Register', component: stub },
      { path: '/student/courses', name: 'StudentCourses', component: stub },
      { path: '/teacher/courses', name: 'TeacherCourses', component: stub },
      { path: '/admin/teachers', name: 'AdminTeachers', component: stub },
      { path: '/student/courses/:courseId', name: 'StudentCourse', component: stub },
    ],
  })
}

async function mountLogin(router: Router, path = '/login') {
  await router.push(path)
  await router.isReady()
  const queryClient = new QueryClient()
  return mount(LoginView, { global: { plugins: [router, [VueQueryPlugin, { queryClient }]] } })
}

async function submit(
  wrapper: Awaited<ReturnType<typeof mountLogin>>,
  account: string,
  password: string,
) {
  await wrapper.find('input[autocomplete="username"]').setValue(account)
  await wrapper.find('input[type="password"]').setValue(password)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

const teacher: User = {
  account_id: 'wang',
  name: '王老師',
  role: 'TEACHER',
  roles: ['TEACHER'],
  preferred_language: 'zh-TW',
  must_change_password: false,
}

describe('LoginView', () => {
  let router: Router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createTestRouter()
    vi.mocked(authApi.login).mockReset()
    vi.mocked(coursesApi.list).mockReset().mockResolvedValue([])
  })

  it('沒填帳號密碼時，不送出並提示', async () => {
    const wrapper = await mountLogin(router)
    await wrapper.find('form').trigger('submit')
    expect(wrapper.text()).toContain('請輸入帳號')
    expect(wrapper.text()).toContain('請輸入密碼')
    expect(authApi.login).not.toHaveBeenCalled()
  })

  it('帳號密碼錯誤時，顯示翻成中文的錯誤訊息', async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 401, data: { detail: 'Invalid account or password' } },
    })
    const wrapper = await mountLogin(router)
    await submit(wrapper, 'wrong', 'wrong')
    expect(wrapper.text()).toContain('帳號或密碼錯誤')
  })

  it('登入成功後，依身分導到首頁', async () => {
    vi.mocked(authApi.login).mockResolvedValueOnce({ token: 't', user: teacher })
    const wrapper = await mountLogin(router)
    await submit(wrapper, 'wang', 'password123')
    expect(router.currentRoute.value.path).toBe('/teacher/courses')
  })

  it('有 redirect 時，登入後回到原本的頁面', async () => {
    vi.mocked(authApi.login).mockResolvedValueOnce({
      token: 't',
      user: { ...teacher, role: 'STUDENT', roles: ['STUDENT'] },
    })
    const wrapper = await mountLogin(router, '/login?redirect=/student/courses/c1')
    await submit(wrapper, 's001', 'password123')
    expect(router.currentRoute.value.path).toBe('/student/courses/c1')
  })

  it('學生帳號在某門課當助教時，登入後先進教學端（照 Prototype）', async () => {
    vi.mocked(authApi.login).mockResolvedValueOnce({
      token: 't',
      user: { ...teacher, role: 'STUDENT', roles: ['STUDENT'] },
    })
    vi.mocked(coursesApi.list).mockResolvedValueOnce([
      { course_id: 'c1', name: '哲學', my_role: 'ta' } as CourseSummary,
    ])
    const wrapper = await mountLogin(router)
    await submit(wrapper, 's011', 'password123')
    expect(router.currentRoute.value.path).toBe('/teacher/courses')
  })

  it('不會被 redirect 導到外部網站', async () => {
    vi.mocked(authApi.login).mockResolvedValueOnce({ token: 't', user: teacher })
    const wrapper = await mountLogin(router, '/login?redirect=//evil.example.com')
    await submit(wrapper, 'wang', 'password123')
    expect(router.currentRoute.value.path).toBe('/teacher/courses')
  })
})
