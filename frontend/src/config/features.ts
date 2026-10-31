/**
 * 後端還沒提供 API 的功能開關。
 *
 * - Demo 模式（`pnpm dev:mock`，VITE_USE_MOCK=true）全部打開，用假後端展示完整流程
 * - 接真的後端時，沒有 API 的功能會關掉：按鈕藏起來，或顯示「尚未開放」
 *
 * 後端做好某個 API 之後，把對應的開關改成 `true` 就好，頁面不用改。
 * 對照文件：docs/API功能規格.md
 */
const mock = import.meta.env.VITE_USE_MOCK === 'true'

export const features = {
  /** AI 對話：POST /student/sessions/{id}/messages/stream、GET /student/sessions/{id}/messages */
  chat: mock,
  /** 語音輸入：POST /student/audio/transcribe */
  voiceInput: mock,
  /** 結論與統計：GET/POST/DELETE /teacher/topics/{id}/conclusions、GET /teacher/topics/{id}/analytics、GET /student/topics/{id}/analytics */
  conclusions: mock,
  /** 編輯課程：PUT /teacher/courses/{id}（規格沒有，要跟後端確認） */
  courseEdit: mock,
  /** 重設老師密碼：POST /admin/teachers/{id}/reset-password（規格沒有，要跟後端確認） */
  teacherPasswordReset: mock,
  /** 問題的年齡層、回合數（Figma 有，後端 schema 沒有這兩個欄位） */
  topicSettings: mock,
} as const
