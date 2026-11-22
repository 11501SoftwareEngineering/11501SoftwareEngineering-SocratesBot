import { afterEach, describe, expect, it, vi } from 'vitest'
import { authApi } from '@/api/auth'
import { readCookie } from '@/lib/cookies'
import { apiClient } from '@/api/client'

function setCookie(value: string) {
  document.cookie = value
}

describe('登出帶 CSRF', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    setCookie('csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT')
  })

  it('讀得到 csrf_token cookie', () => {
    setCookie('csrf_token=abc%2B123')
    expect(readCookie('csrf_token')).toBe('abc+123')
    expect(readCookie('refresh_token')).toBeNull()
  })

  it('登出時把 csrf_token cookie 放進 X-CSRF-Token header（後端規定）', async () => {
    setCookie('csrf_token=token-1')
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { ok: true } })
    await authApi.logout()
    expect(post).toHaveBeenCalledWith('/auth/logout', null, {
      headers: { 'X-CSRF-Token': 'token-1' },
    })
  })

  it('沒有 csrf_token cookie 時照樣送出（後端會回 403，前端仍會清除登入狀態）', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { ok: true } })
    await authApi.logout()
    expect(post).toHaveBeenCalledWith('/auth/logout', null, { headers: undefined })
  })
})
