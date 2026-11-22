/// <reference types="vite/client" />
/// <reference types="pinia-plugin-persistedstate" />

interface ImportMetaEnv {
  /** 後端網址（不含 /api/v1）。開發時由 .env.development 提供；正式環境建置時一定要設定 */
  readonly VITE_API_BASE_URL?: string
  /** 'true' 時用瀏覽器裡的假後端（MSW），並顯示 Debug 面板 */
  readonly VITE_USE_MOCK?: string
}
