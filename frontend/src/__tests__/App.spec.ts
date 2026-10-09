import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from '../App.vue'
import AnnouncementsView from '@/views/common/AnnouncementsView.vue'
import { announcementsApi } from '@/api/announcements'

vi.mock('@/api/announcements', () => ({
  announcementsApi: { getAnnouncements: vi.fn<typeof announcementsApi.getAnnouncements>() },
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
    vi.mocked(announcementsApi.getAnnouncements).mockResolvedValueOnce({
      data: [
        {
          id: 'home',
          title: '首頁公告',
          content: '公告內容',
          published_at: '2026-10-05T00:00:00Z',
        },
      ],
    } as never)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: AnnouncementsView },
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

    await vi.waitFor(() => expect(wrapper?.find('article').text()).toContain('首頁公告'))
    expect(wrapper.find('header').text()).toContain('問導魷')
    expect(wrapper.find('header a[href="/login"]').text()).toBe('登入')
    expect(wrapper.find('footer').text()).toContain('隱私權')
    expect(announcementsApi.getAnnouncements).toHaveBeenCalledTimes(1)
  })
})
