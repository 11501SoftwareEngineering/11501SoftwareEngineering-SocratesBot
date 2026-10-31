import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type LoginPayload, type User, type UserRole } from '@/api/auth'
import { queryClient } from '@/queryClient'
import router from '@/router'

export type { User, UserRole } from '@/api/auth'

/** 各角色登入後的首頁 */
export const HOME_ROUTE: Record<UserRole, string> = {
  STUDENT: 'StudentCourses',
  TEACHER: 'TeacherCourses',
  SUPER_ADMIN: 'AdminTeachers',
}

export const useAuthStore = defineStore(
  'auth',
  () => {
    const token = ref<string | null>(null)
    const user = ref<User | null>(null)
    /** 登入過期被踢回登入頁時，登入頁要顯示提示 */
    const sessionExpired = ref(false)

    const isAuthenticated = computed(() => !!token.value)
    const userRole = computed(() => user.value?.role ?? null)
    /** 全部身分（例如管理員同時也是老師）。舊版存下來的資料沒有 roles，用 role 補 */
    const userRoles = computed<UserRole[]>(() =>
      user.value ? (user.value.roles ?? [user.value.role]) : [],
    )
    const mustChangePassword = computed(() => !!user.value?.must_change_password)

    function setAuth(newToken: string, userData: User) {
      token.value = newToken
      user.value = userData
      sessionExpired.value = false
      localStorage.setItem('access_token', newToken)
    }

    /** 後端自動續期後換上新的 token（api/client.ts 呼叫） */
    function setToken(newToken: string) {
      if (!token.value) return
      token.value = newToken
      localStorage.setItem('access_token', newToken)
    }

    function hasRole(role: UserRole) {
      return userRoles.value.includes(role)
    }

    async function login(payload: LoginPayload) {
      const { token: newToken, user: userData } = await authApi.login(payload)
      queryClient.clear()
      setAuth(newToken, userData)
      return userData
    }

    function clearAuth() {
      token.value = null
      user.value = null
      localStorage.removeItem('access_token')
      // 換帳號前把快取清掉，避免看到上一個人的資料
      queryClient.clear()
    }

    async function logout(options: { expired?: boolean } = {}) {
      if (!options.expired && token.value) {
        // 通知後端清掉 refresh cookie；失敗也照樣登出
        await authApi.logout().catch(() => undefined)
      }
      const wasLoggedIn = !!token.value
      clearAuth()
      sessionExpired.value = !!options.expired && wasLoggedIn
      const current = router.currentRoute.value
      const redirect = options.expired && current.name !== 'Login' ? current.fullPath : undefined
      return router.replace({ name: 'Login', query: redirect ? { redirect } : undefined })
    }

    async function fetchCurrentUser() {
      if (!token.value) return
      try {
        user.value = await authApi.getMe()
      } catch {
        // 401 會由 api/client.ts 統一處理
      }
    }

    function requirePasswordChange() {
      if (user.value) user.value = { ...user.value, must_change_password: true }
    }

    function markPasswordChanged() {
      if (user.value) user.value = { ...user.value, must_change_password: false }
      // 改密碼前被擋掉（403）的資料重新抓一次
      void queryClient.invalidateQueries()
    }

    return {
      token,
      user,
      sessionExpired,
      isAuthenticated,
      userRole,
      userRoles,
      mustChangePassword,
      setAuth,
      setToken,
      hasRole,
      login,
      logout,
      fetchCurrentUser,
      requirePasswordChange,
      markPasswordChanged,
    }
  },
  {
    persist: { pick: ['token', 'user'] },
  },
)
