import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useUiLanguage } from '../useUiLanguage'

describe('useUiLanguage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('後端支援的語言存到帳號，其他語言只記在這台電腦', async () => {
    const patch = vi
      .spyOn(authApi, 'updatePreferences')
      .mockResolvedValue({ preferred_language: 'en', message: '' })
    const auth = useAuthStore()
    auth.user = {
      account_id: 's1',
      name: 'S',
      role: 'STUDENT',
      roles: ['STUDENT'],
      preferred_language: 'zh-TW',
      must_change_password: false,
    }
    const { language, setLanguage } = useUiLanguage()
    expect(language.value).toBe('zh-TW')

    await setLanguage('en')
    expect(patch).toHaveBeenCalledWith('en')
    expect(language.value).toBe('en')

    patch.mockClear()
    await setLanguage('ja')
    expect(patch).not.toHaveBeenCalled()
    expect(localStorage.getItem('socratesbot-ui-language')).toBe('ja')
    expect(auth.user?.preferred_language).toBe('en')
    // 日本語目前隱藏（enabled: false），所以還是用帳號的語言
    expect(language.value).toBe('en')
  })

  it('語言選單只列出開放的語言', () => {
    const { options } = useUiLanguage()
    expect(options.map((o) => o.value)).toEqual(['zh-TW', 'en', 'es'])
  })

  it('存到帳號失敗時還原', async () => {
    vi.spyOn(authApi, 'updatePreferences').mockRejectedValue(new Error('x'))
    const auth = useAuthStore()
    auth.user = {
      account_id: 's1',
      name: 'S',
      role: 'STUDENT',
      roles: ['STUDENT'],
      preferred_language: 'zh-TW',
      must_change_password: false,
    }
    await useUiLanguage().setLanguage('es')
    expect(auth.user?.preferred_language).toBe('zh-TW')
  })
})
