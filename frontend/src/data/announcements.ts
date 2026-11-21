// 公告直接改這個檔案就好，不需要 API。
// title、content 寫 i18n key（文字放在 src/i18n/locales/*），畫面會依介面語言顯示；
// 直接寫文字也可以（例如 Debug 面板臨時新增的），就照原文顯示。
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
    title: 'announcements.welcome.title',
    content: 'announcements.welcome.content',
    published_at: '2026-10-20T09:00:00+08:00',
  },
  {
    id: 'v02-dialogue',
    title: 'announcements.v02.title',
    content: 'announcements.v02.content',
    published_at: '2026-11-16T09:00:00+08:00',
  },
])
