import { computed, ref, watch } from 'vue'
import { authApi, type UiLanguage } from '@/api/auth'
import {
  DEFAULT_LOCALE,
  ENABLED_LOCALES,
  isEnabledLocale,
  localeInfo,
  setLocale,
  type Locale,
} from '@/i18n'
import { useAuthStore } from '@/stores/auth'

const STORAGE_KEY = 'socratesbot-ui-language'

function load(): Locale | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return isEnabledLocale(saved) ? saved : null
  } catch {
    return null
  }
}

/** 這台電腦最後選的語言（沒登入、或選了後端不支援的語言時用） */
const localChoice = ref<Locale | null>(load())

/**
 * 介面語言（Header 右上角的語言選單）。
 * - 正體中文／English／Español：已登入時存到帳號（PATCH /users/me/preferences），換電腦也記得
 * - 其他語言（简体中文、日本語…）：後端還不接受，只記在這台電腦的瀏覽器；
 *   目前先隱藏（i18n/index.ts 的 enabled: false），之前選過的會改回帳號的語言
 * - 已登入時：這台電腦選了「只能存在本機」的語言就用它，否則用帳號的設定
 */
export function useUiLanguage() {
  const authStore = useAuthStore()

  const language = computed<Locale>(() => {
    const local = localChoice.value
    if (isEnabledLocale(local) && !localeInfo(local).backend) return local
    const fromUser = authStore.user?.preferred_language
    if (isEnabledLocale(fromUser)) return fromUser
    return local ?? DEFAULT_LOCALE
  })

  const label = computed(() => localeInfo(language.value).label)

  async function setLanguage(value: Locale) {
    localChoice.value = value
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // 存不了沒關係
    }
    if (!authStore.user || !localeInfo(value).backend) return
    const previous = authStore.user.preferred_language
    authStore.user = { ...authStore.user, preferred_language: value as UiLanguage }
    try {
      await authApi.updatePreferences(value as UiLanguage)
    } catch {
      authStore.user = { ...authStore.user, preferred_language: previous }
    }
  }

  return { language, label, options: ENABLED_LOCALES, setLanguage }
}

/** App.vue 呼叫一次：語言改變時載入語言檔、更新畫面與 <html lang> */
export function useLocaleSync() {
  const { language } = useUiLanguage()
  watch(language, (value) => void setLocale(value), { immediate: true })
  return language
}
