<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const account = ref('')
const password = ref('')
const errorMessage = ref('')
const isSubmitting = ref(false)

async function handleLogin() {
  errorMessage.value = ''
  isSubmitting.value = true
  try {
    const res = await authApi.login({ account: account.value, password: password.value })
    authStore.setAuth(res.data.access_token, {
      id: res.data.account,
      email: res.data.account,
      name: res.data.name,
      role: res.data.role,
    })
    if (res.data.role === 'STUDENT') router.push('/student/courses')
    else if (res.data.role === 'TEACHER') router.push('/teacher/dashboard')
    else router.push('/admin/users')
  } catch (err) {
    errorMessage.value = '帳號或密碼錯誤'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-background px-4">
    <div class="w-full max-w-[500px] flex flex-col items-center gap-8 rounded-2xl border border-border bg-card px-10 py-12 shadow-elevated">
      
      <!-- Logo 區 -->
      <div class="flex justify-center w-full">
        <img src="@/assets/LOGO.svg" alt="Logo" class="h-32 w-32 object-contain" />
      </div>

      <!-- 登入表單 -->
      <form class="flex w-full flex-col gap-6" @submit.prevent="handleLogin">
        
        <!-- 帳號欄位 -->
        <div class="flex items-center gap-4">
          <label for="login-account" class="w-16 shrink-0 font-heading text-lg font-medium text-foreground text-right">帳號：</label>
          <Input id="login-account" v-model="account" class="flex-1 shadow-input" placeholder="請輸入帳號" autocomplete="username" />
        </div>

        <!-- 密碼欄位 -->
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-4">
            <label for="login-password" class="w-16 shrink-0 font-heading text-lg font-medium text-foreground text-right">密碼：</label>
            <Input id="login-password" v-model="password" type="password" class="flex-1 shadow-input" placeholder="請輸入密碼" autocomplete="current-password" />
          </div>
          <p v-if="errorMessage" class="w-full text-right text-sm text-destructive pr-1">
            {{ errorMessage }}
          </p>
        </div>

        <!-- 按鈕與忘記密碼區 -->
        <div class="flex w-full flex-col items-end gap-2 pt-4">
          <div class="flex items-center gap-4">
            <!-- 加入 @click 觸發切換至註冊頁面 -->
            <Button type="button" variant="ghost" class="text-muted-foreground hover:text-primary" @click="router.push('/register')">
              註冊
            </Button>
            <Button type="submit" size="lg" class="w-24 bg-primary text-primary-foreground shadow-elevated hover:opacity-90" :disabled="isSubmitting">
              {{ isSubmitting ? '登入中...' : '登入' }}
            </Button>
          </div>
          <button type="button" class="text-sm text-muted-foreground hover:underline pr-2">
            忘記密碼?
          </button>
        </div>

      </form>
    </div>
  </div>
</template>