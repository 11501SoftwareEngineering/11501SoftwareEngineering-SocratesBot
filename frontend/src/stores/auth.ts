import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type LoginPayload, type User, type UserRole } from '@/api/auth'
import { coursesApi, type CourseSummary } from '@/api/courses'
import { queryClient } from '@/queryClient'
import router from '@/router'

export type { User, UserRole } from '@/api/auth'

/** 各角色登入後的首頁 */
export const HOME_ROUTE: Record<UserRole, string> = {
  STUDENT: 'StudentCourses',
  TEACHER: 'TeacherCourses',
  SUPER_ADMIN: 'AdminTeachers',
}

/**
 * 登入後的首頁。和 Prototype 一樣：學生帳號只要在某門課當助教，就先進教學端（老師的我的課程），
 * 學生課程從頁首的「學生課程」切換。
 */
export function homeRouteFor(role: UserRole, hasTaAssignments = false): string {
  return role === 'STUDENT' && hasTaAssignments ? 'TeacherCourses' : HOME_ROUTE[role]
}

export const useAuthStore = defineStore(
  'auth',
  () => {
    const token = ref<string | null>(null)
    const user = ref<User | null>(null)
    /** 登入過期被踢回登入頁時，登入頁要顯示提示 */
    const sessionExpired = ref(false)
    /**
     * 第一次登入（must_change_password）時記住登入用的初始密碼，
     * 「設定首次登入密碼」就不用再輸入一次原密碼。只放在記憶體、不存 localStorage，改完就清掉。
     */
    const initialPassword = ref<string | null>(null)
    /**
     * 這個學生帳號是不是某門課的助教。後端沒有 has_ta_assignments 欄位（Prototype 有），
     * 用 GET /courses 的 my_role 判斷：登入時查一次，之後每次拿到課程列表都更新。
     */
    const hasTaAssignments = ref(false)

    const isAuthenticated = computed(() => !!token.value)
    const userRole = computed(() => user.value?.role ?? null)
    /** 全部身分（例如管理員同時也是老師）。舊版存下來的資料沒有 roles，用 role 補 */
    const userRoles = computed<UserRole[]>(() =>
      user.value ? (user.value.roles ?? [user.value.role]) : [],
    )
    const mustChangePassword = computed(() => !!user.value?.must_change_password)
    /** 能不能進教學端（老師，或當助教的學生） */
    const canTeach = computed(
      () =>
        userRole.value === 'TEACHER' || (userRole.value === 'STUDENT' && hasTaAssignments.value),
    )
    const homeRoute = computed(() =>
      userRole.value ? homeRouteFor(userRole.value, hasTaAssignments.value) : 'Home',
    )

    function syncTaAssignments(courses: CourseSummary[]) {
      hasTaAssignments.value = courses.some((c) => c.my_role === 'ta')
    }

    /** 學生帳號重新查一次有沒有助教課程；查不到就維持原狀 */
    async function refreshTaAssignments() {
      if (userRole.value !== 'STUDENT') {
        hasTaAssignments.value = false
        return
      }
      try {
        syncTaAssignments(await coursesApi.list())
      } catch {
        // 401 由 api/client.ts 處理；其他錯誤不影響登入
      }
    }

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
      initialPassword.value = userData.must_change_password ? payload.password : null
      hasTaAssignments.value = false
      if (!userData.must_change_password) await refreshTaAssignments()
      return userData
    }

    function clearAuth() {
      token.value = null
      user.value = null
      initialPassword.value = null
      hasTaAssignments.value = false
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
        await refreshTaAssignments()
      } catch {
        // 401 會由 api/client.ts 統一處理
      }
    }

    function requirePasswordChange() {
      if (user.value) user.value = { ...user.value, must_change_password: true }
    }

    function markPasswordChanged() {
      if (user.value) user.value = { ...user.value, must_change_password: false }
      initialPassword.value = null
      // 改密碼前被擋掉（403）的資料重新抓一次
      void queryClient.invalidateQueries()
      void refreshTaAssignments()
    }

    return {
      token,
      user,
      sessionExpired,
      initialPassword,
      hasTaAssignments,
      canTeach,
      homeRoute,
      isAuthenticated,
      userRole,
      userRoles,
      mustChangePassword,
      setAuth,
      setToken,
      hasRole,
      syncTaAssignments,
      refreshTaAssignments,
      login,
      logout,
      fetchCurrentUser,
      requirePasswordChange,
      markPasswordChanged,
    }
  },
  {
    persist: { pick: ['token', 'user', 'hasTaAssignments'] },
  },
)
