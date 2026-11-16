import { computed, ref, watchEffect } from 'vue'
import { authApi, UI_LANGUAGES, type UiLanguage } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const STORAGE_KEY = 'socratesbot-ui-language'

function load(): UiLanguage {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (UI_LANGUAGES.some((l) => l.value === saved)) return saved as UiLanguage
  } catch {
    // 讀不到就用預設
  }
  return 'zh-TW'
}

/** 還沒登入時選的語言（登入後以帳號的 preferred_language 為準） */
const guestLanguage = ref<UiLanguage>(load())

/**
 * 介面語言（Header 右上角的「正體中文」）。
 * - 已登入：存到帳號（PATCH /users/me/preferences），換電腦也記得
 * - 沒登入：存在這台電腦的瀏覽器
 *
 * ⚠️ 目前畫面文字還沒有翻譯，切換只會記住選擇並設定 <html lang>；翻譯另外做。
 */
export function useUiLanguage() {
  const authStore = useAuthStore()

  const language = computed<UiLanguage>(() => {
    const fromUser = authStore.user?.preferred_language
    return UI_LANGUAGES.some((l) => l.value === fromUser)
      ? (fromUser as UiLanguage)
      : guestLanguage.value
  })

  const label = computed(
    () => UI_LANGUAGES.find((l) => l.value === language.value)?.label ?? '正體中文',
  )

  watchEffect(() => {
    document.documentElement.lang = language.value
  })

  async function setLanguage(value: UiLanguage) {
    guestLanguage.value = value
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // 存不了沒關係
    }
    if (authStore.user) {
      const previous = authStore.user.preferred_language
      authStore.user = { ...authStore.user, preferred_language: value }
      try {
        await authApi.updatePreferences(value)
      } catch {
        authStore.user = { ...authStore.user, preferred_language: previous }
      }
    }
  }

  return { language, label, options: UI_LANGUAGES, setLanguage }
}
