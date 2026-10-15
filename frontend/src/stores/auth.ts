import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/api/client'
import { queryClient } from '@/queryClient'
import router from '@/router'

export type UserRole = 'STUDENT' | 'TEACHER' | 'ADMIN'

export interface User {
  id: string
  email: string
  name: string
  role: UserRole
}

export const useAuthStore = defineStore(
  'auth',
  () => {
    const token = ref<string | null>(null)
    const user = ref<User | null>(null)

    const isAuthenticated = computed(() => !!token.value)
    const userRole = computed(() => user.value?.role || null)

    function setAuth(newToken: string, userData: User) {
      token.value = newToken
      user.value = userData
      localStorage.setItem('access_token', newToken)
    }

    function logout() {
      token.value = null
      user.value = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('auth')
      // Clear queries and mutations, and cancel pending queries before changing accounts.
      queryClient.clear()
      return router.replace('/login')
    }

    async function fetchCurrentUser() {
      if (!token.value) return
      try {
        const res = await apiClient.get<User>('/users/me')
        user.value = res.data
      } catch {
        logout()
      }
    }

    return {
      token,
      user,
      isAuthenticated,
      userRole,
      setAuth,
      logout,
      fetchCurrentUser,
    }
  },
  {
    persist: true,
  },
)
