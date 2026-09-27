import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '@/api/client'

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
    const router = useRouter()

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
      router.push('/login')
    }

    async function fetchCurrentUser() {
      if (!token.value) return
      try {
        const res = await apiClient.get<User>('/users/me')
        user.value = res.data
      } catch (error) {
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
  }
)