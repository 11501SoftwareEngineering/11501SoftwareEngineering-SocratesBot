import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import AnnouncementsView from '../AnnouncementsView.vue'
import { announcementsApi } from '@/api/announcements'

vi.mock('@/api/announcements', () => ({
  announcementsApi: { getAnnouncements: vi.fn<typeof announcementsApi.getAnnouncements>() },
}))
const getAnnouncements = vi.mocked(announcementsApi.getAnnouncements)

describe('AnnouncementsView', () => {
  let queryClient: QueryClient
  let wrappers: VueWrapper[]

  beforeEach(() => {
    getAnnouncements.mockReset()
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    })
    wrappers = []
  })

  afterEach(() => {
    wrappers.forEach((wrapper) => wrapper.unmount())
    queryClient.clear()
  })

  function mountView() {
    const wrapper = mount(AnnouncementsView, {
      global: { plugins: [[VueQueryPlugin, { queryClient }]] },
    })
    wrappers.push(wrapper)
    return wrapper
  }

  it('shows loading, API content and the Taipei publication date', async () => {
    getAnnouncements.mockResolvedValueOnce({
      data: [
        { id: '1', title: '公告標題', content: '公告內容', published_at: '2026-10-04T18:00:00Z' },
      ],
    } as never)
    const wrapper = mountView()
    expect(wrapper.find('[role="status"]').text()).toContain('公告載入中')
    expect(wrapper.attributes('aria-busy')).toBe('true')

    await vi.waitFor(() => expect(wrapper.find('time').exists()).toBe(true))
    expect(wrapper.text()).toContain('公告標題')
    expect(wrapper.text()).toContain('公告內容')
    expect(wrapper.find('time').text()).toBe('2026-10-05')
    expect(wrapper.attributes('aria-busy')).toBe('false')
  })

  it('shows an empty state', async () => {
    getAnnouncements.mockResolvedValueOnce({ data: [] } as never)
    const wrapper = mountView()
    await vi.waitFor(() => expect(wrapper.text()).toContain('目前沒有公告'))
    expect(wrapper.find('article').exists()).toBe(false)
  })

  it('shows the API error and allows a successful refetch', async () => {
    getAnnouncements.mockRejectedValueOnce({
      isAxiosError: true,
      response: { data: { detail: '服務暫停' } },
    })
    getAnnouncements.mockResolvedValueOnce({ data: [] } as never)
    const wrapper = mountView()
    await vi.waitFor(() => expect(wrapper.find('[role="alert"]').text()).toBe('服務暫停'))

    await wrapper.find('button').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('目前沒有公告'))
    expect(getAnnouncements).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.attributes('aria-busy')).toBe('false')
  })

  it('uses the shared fallback message for a non-API error', async () => {
    getAnnouncements.mockRejectedValueOnce(new Error('Network unavailable'))
    const wrapper = mountView()
    await vi.waitFor(() =>
      expect(wrapper.find('[role="alert"]').text()).toBe('公告載入失敗，請稍後再試'),
    )
  })

  it('reuses fresh query data when the page is mounted again', async () => {
    queryClient.setQueryDefaults(['announcements'], { staleTime: Infinity })
    getAnnouncements.mockResolvedValueOnce({
      data: [
        {
          id: 'cached',
          title: '快取公告',
          content: '公告內容',
          published_at: '2026-10-05T00:00:00Z',
        },
      ],
    } as never)
    const first = mountView()
    await vi.waitFor(() => expect(first.find('article').exists()).toBe(true))
    first.unmount()

    const second = mountView()
    expect(second.text()).toContain('快取公告')
    expect(second.find('[role="status"]').exists()).toBe(false)
    expect(getAnnouncements).toHaveBeenCalledTimes(1)
  })
})
