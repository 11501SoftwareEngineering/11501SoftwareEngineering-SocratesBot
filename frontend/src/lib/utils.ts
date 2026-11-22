import type { ClassValue } from 'clsx'
import axios from 'axios'
import { clsx } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'
import { translate } from '@/i18n'

// Teach the merger our typography and shadow tokens so it preserves colors.
const mergeClasses = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        'text-header',
        'text-page-title',
        'text-h1-title',
        'text-footer',
        'text-h2-title',
        'text-body',
        'text-body-lg',
        'text-caption',
      ],
      shadow: ['shadow-elevated', 'shadow-input'],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return mergeClasses(clsx(inputs))
}

// 後端回傳的錯誤訊息是英文，這裡對應到 i18n 的 errors.api.*，畫面會顯示目前介面語言的文字。
// 後端新增錯誤訊息時，把英文原文加進來，再到語言檔加上翻譯。
// 用 [英文原文, key] 的清單建 Map（不用物件屬性，避免 SonarCloud 把含 password 的屬性誤判成寫死的密碼）
const API_ERROR_KEYS = new Map<string, string>([
  ['Invalid account or password', 'invalidLogin'],
  ['Account already exists', 'accountExists'],
  ['Account name reserved', 'accountReserved'],
  ['Not authenticated or token expired', 'notAuthenticated'],
  ['Current password is incorrect', 'password.wrong'],
  ['New password must be different from the current password', 'password.same'],
  ['Password change required', 'password.changeRequired'],
  ['Invalid language code', 'invalidLanguage'],
  ['CSRF token missing or mismatch', 'csrf'],
  ['Admin privileges required', 'adminRequired'],
  ['Teacher privileges required', 'teacherRequired'],
  ['Student privileges required', 'studentRequired'],
  ['Course instructor required', 'instructorRequired'],
  ['Course membership required', 'membershipRequired'],
  ['Only the course creator can delete this course', 'creatorOnly'],
  ['Teacher not found', 'teacherNotFound'],
  ['Cannot delete elevated admin account', 'cannotDeleteAdmin'],
  ['Course not found', 'courseNotFound'],
  ['Course not found for this invitation code', 'inviteNotFound'],
  ['Invalid invitation code format', 'inviteFormat'],
  ['Already a member of this course', 'alreadyMember'],
  ['Cannot rejoin after leaving this course', 'cannotRejoin'],
  ['Could not allocate invitation code; retry later', 'inviteUnavailable'],
  ['Topic not found', 'topicNotFound'],
  ['Session not found', 'sessionNotFound'],
  ['Dialogue is not completed', 'sessionNotCompleted'],
  ['Report not found', 'reportNotStarted'],
  ['Not Found', 'notFound'],
  ['Too many login attempts. Try again later.', 'tooManyLogins'],
  ['Cannot reset elevated admin account password', 'cannotResetAdmin'],
  ['Teacher or TA privileges required', 'staffRequired'],
  ['Course teacher required', 'teacherOnly'],
  ['Teachers and TAs cannot leave a course this way', 'staffCannotLeave'],
  ['Course membership changed concurrently; retry', 'membershipChanged'],
  ['Account not found', 'accountNotFound'],
  ['Admins cannot be TAs', 'adminCannotBeTa'],
  ['Teacher accounts cannot be TAs', 'teacherCannotBeTa'],
  ['Already a TA of this course', 'alreadyTa'],
  ['Already a teacher or TA of this course', 'alreadyStaff'],
  ['TA not found', 'taNotFound'],
  ['Teacher API key cannot be read', 'apiKeyUnreadable'],
  ['Invalid model id', 'invalidModel'],
  ['Unknown model', 'invalidModel'],
  ['Model call failed', 'modelFailed'],
  ['Inquiry generation failed', 'generationFailed'],
  ['Inquiry was updated', 'setupChanged'],
  ['Topic is not in setup', 'topicNotInSetup'],
  ['Topic is still in setup', 'topicInSetup'],
  ['Topic is in summary', 'topicInSummary'],
  ['Dialogue is not accepting replies', 'dialogueClosed'],
  ['Turn cap reached', 'turnCapReached'],
  ['Another reply is in progress', 'replyInProgress'],
  ['Inquiry goal is not met', 'goalNotMet'],
  ['No ready reports', 'noReadyReports'],
  ['Summary not found', 'summaryNotFound'],
  ['No published summary', 'noPublishedSummary'],
  ['Summary contains a name or identifier', 'summaryHasName'],
  ['Dialogue has already ended', 'dialogueEnded'],
  ['Finish early requires three student answers', 'finishTooEarly'],
  ['Dialogue is not report-eligible', 'sessionNotCompleted'],
  ['Dialogue changed while replying', 'dialogueChanged'],
  ['Internal Server Error', 'server'],
])

/** 後端訊息裡帶變數的（權限名稱、缺少的欄位），用開頭比對 */
function apiErrorPatternKey(detail: string) {
  if (/^Course teacher or TA with \w+ permission required$/.test(detail))
    return 'permissionRequired'
  if (detail.startsWith('Incomplete setup:')) return 'incompleteSetup'
  return undefined
}

// 統一從 axios 錯誤裡撈出後端回傳的錯誤訊息，避免每個畫面都自己寫
// `catch (err: any)` 去猜 err.response.data.detail 長怎樣。
export function getApiErrorMessage(error: unknown, fallback?: string): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return translate('errors.network')
    const detail = error.response.data?.detail
    if (typeof detail === 'string') {
      if (detail === 'Request validation failed') return translate('errors.validation')
      const key = API_ERROR_KEYS.get(detail) ?? apiErrorPatternKey(detail)
      return key ? translate(`errors.api.${key}`) : detail
    }
    // FastAPI 欄位驗證錯誤（422）的 detail 是陣列
    if (Array.isArray(detail)) return translate('errors.validation')
  }
  return fallback ?? translate('errors.generic')
}
/** 日期顯示成 YYYY-MM-DD（台北時區） */
export function formatDate(value: string | null | undefined) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('sv-SE', { timeZone: 'Asia/Taipei' })
}
