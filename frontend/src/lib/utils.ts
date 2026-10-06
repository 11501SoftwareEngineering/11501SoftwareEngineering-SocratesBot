import type { ClassValue } from 'clsx'
import axios from 'axios'
import { clsx } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// Teach the merger our typography and shadow tokens so it preserves colors.
const mergeClasses = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        'text-header',
        'text-h1-title',
        'text-footer',
        'text-h2-title',
        'text-body',
        'text-caption',
      ],
      shadow: ['shadow-elevated', 'shadow-input'],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return mergeClasses(clsx(inputs))
}

// 統一從 axios 錯誤裡撈出後端回傳的錯誤訊息，避免每個畫面都自己寫
// `catch (err: any)` 去猜 err.response.data.detail 長怎樣。
export function getApiErrorMessage(error: unknown, fallback = '發生錯誤，請稍後再試'): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}
