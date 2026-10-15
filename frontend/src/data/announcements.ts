// Edit this list to publish announcements. No network request is needed.
export interface Announcement {
  id: string
  title: string
  content: string
  published_at: string
}

export const announcements: readonly Announcement[] = [
  {
    id: 'preview-announcement',
    title: '課程頁面預覽',
    content: '這是前端示範資料，可用來檢查畫面與搜尋互動。',
    published_at: '2026-10-13T09:00:00+08:00',
  },
]
