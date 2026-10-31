// 公告直接改這個檔案就好，不需要 API。
// （Demo 模式下 Debug 面板可以臨時新增公告，重新整理後就會消失。）
import { reactive } from 'vue'

export interface Announcement {
  id: string
  title: string
  content: string
  published_at: string
}

export const announcements = reactive<Announcement[]>([
  {
    id: 'welcome',
    title: '歡迎使用問導魷',
    content:
      '問導魷會用提問的方式陪你思考問題，沒有標準答案，重點是說出你的理由。\n學生請先用老師給的課程代碼加入課程。',
    published_at: '2026-10-20T09:00:00+08:00',
  },
  {
    id: 'ai-coming-soon',
    title: '和導魷對話的功能即將開放',
    content:
      '目前可以加入課程、瀏覽老師出的問題和題目說明。和導魷對話、語音輸入、結論統計正在開發中，開放後會再公告。',
    published_at: '2026-10-30T09:00:00+08:00',
  },
])
