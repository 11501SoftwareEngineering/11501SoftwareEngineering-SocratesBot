/**
 * 介面多語系（vue-i18n）。
 *
 * - 正體中文（zh-TW.ts）是預設語言，也是其他語言檔的型別依據：少翻一個 key，type-check 就會失敗
 * - 其他語言用到才下載（動態 import），不會讓第一次載入變慢
 * - 後端的偏好設定（PATCH /users/me/preferences）只接受 zh-TW / en / es，
 *   其他語言（backend: false）只記在這台電腦，見 composables/useUiLanguage.ts
 *
 * 元件裡用 `const { t } = useI18n()`；不在元件裡（router、常數、錯誤訊息）用 `translate()`。
 * 新增語言：在 locales/ 加一個檔案（`export default { ... } satisfies Messages`），再加進下面的 LOCALES。
 * enabled: false 的語言保留翻譯檔、測試照跑，但語言選單不顯示（等 PM 決定要不要開放）。
 */
import { createI18n } from 'vue-i18n'
import zhTW from './locales/zh-TW'

export type Messages = typeof zhTW

export const LOCALES = [
  { value: 'zh-TW', label: '正體中文', speech: 'zh-TW', backend: true, enabled: true },
  { value: 'en', label: 'English', speech: 'en-US', backend: true, enabled: true },
  { value: 'es', label: 'Español', speech: 'es-ES', backend: true, enabled: true },
  { value: 'zh-CN', label: '简体中文', speech: 'zh-CN', backend: false, enabled: false },
  { value: 'ja', label: '日本語', speech: 'ja-JP', backend: false, enabled: false },
  { value: 'ko', label: '한국어', speech: 'ko-KR', backend: false, enabled: false },
  { value: 'fr', label: 'Français', speech: 'fr-FR', backend: false, enabled: false },
  { value: 'de', label: 'Deutsch', speech: 'de-DE', backend: false, enabled: false },
] as const

export type Locale = (typeof LOCALES)[number]['value']
export const DEFAULT_LOCALE: Locale = 'zh-TW'

export function isLocale(value: unknown): value is Locale {
  return LOCALES.some((l) => l.value === value)
}

/** 語言選單裡顯示的語言 */
export const ENABLED_LOCALES = LOCALES.filter((l) => l.enabled)

export function isEnabledLocale(value: unknown): value is Locale {
  return ENABLED_LOCALES.some((l) => l.value === value)
}

export function localeInfo(locale: Locale) {
  return LOCALES.find((l) => l.value === locale) ?? LOCALES[0]
}

export const i18n = createI18n<[Messages], Locale, false>({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: { 'zh-TW': zhTW } as Record<Locale, Messages>,
  missingWarn: false,
  fallbackWarn: false,
})

/** 不在元件裡時用（router 標題、常數的 label、API 錯誤訊息） */
export function translate(key: string, params?: Record<string, unknown>): string {
  return params ? i18n.global.t(key, params) : i18n.global.t(key)
}

const loaders = import.meta.glob<{ default: Messages }>('./locales/*.ts')
const loaded = new Set<Locale>([DEFAULT_LOCALE])

/** 切換介面語言：需要時先下載語言檔，再更新 i18n 與 <html lang> */
export async function setLocale(locale: Locale) {
  if (!loaded.has(locale)) {
    const load = loaders[`./locales/${locale}.ts`]
    if (!load) return
    const messages = await load()
    i18n.global.setLocaleMessage(locale, messages.default)
    loaded.add(locale)
  }
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
}
