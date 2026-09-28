<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth'

// 對應 Figma「Login_test」畫面（node 125:62）。
// 這版是照 Login_test 的 auto layout 結構重刻的：卡片內用 flex 分成
// 「Logo 區 / 欄位區 / 按鈕區」三段，欄位區整體往左內縮一點（對應 Figma 的 pl-34），
// 按鈕跟忘記密碼則整組靠右對齊（對應 Figma 的 items-end）。
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
    errorMessage.value = getApiErrorMessage(err, '帳號或密碼錯誤')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="flex justify-center px-4 py-12">
    <div class="flex w-full max-w-[626px] flex-col items-center gap-5 rounded-2xl border border-border bg-card px-[68px] py-[27px] shadow-elevated">
      <!-- TODO(設計組): Figma 現在放的是正式的吉祥物截圖，麻煩請輸出透明背景的 SVG/PNG
           圖檔給前端，換掉下面這個佔位方塊。 -->
      <div class="flex w-full justify-center pt-[30px]">
        <div class="flex h-44 w-44 items-center justify-center rounded-lg bg-muted text-sm text-muted-foreground">
          Logo 佔位
        </div>
      </div>

      <form class="flex w-full flex-col gap-8" @submit.prevent="handleLogin">
        <div class="flex w-full flex-col gap-8 pl-8">
          <div class="flex w-full items-center gap-4">
            <label for="login-account" class="w-[108px] shrink-0 font-heading text-h1-title text-foreground">帳號：</label>
            <Input id="login-account" v-model="account" class="flex-1" placeholder="請輸入帳號" autocomplete="username" />
          </div>

          <div class="flex w-full flex-col gap-1">
            <div class="flex w-full items-center gap-4">
              <label for="login-password" class="w-[108px] shrink-0 font-heading text-h1-title text-foreground">密碼：</label>
              <Input id="login-password" v-model="password" type="password" class="flex-1" placeholder="請輸入密碼" autocomplete="current-password" />
            </div>
            <p v-if="errorMessage" class="w-full text-right text-h2-title text-destructive">
              {{ errorMessage }}
            </p>
          </div>
        </div>

        <div class="flex w-full flex-col items-end gap-2 pt-2">
          <div class="flex items-center gap-4">
            <Button type="button" variant="ghost" size="lg">
              註冊
            </Button>
            <Button type="submit" size="lg" :disabled="isSubmitting">
              {{ isSubmitting ? '登入中...' : '登入' }}
            </Button>
          </div>

          <!-- TODO(前端組): 忘記密碼流程還沒有對應頁面/API，先放可 hover 的文字佔位。
               Figma 這裡 hover 時「顏色不變、只加底線」，所以用 hover:underline，
               不要加 hover:text-* 之類會變色的 class。 -->
          <button type="button" class="text-h2-title text-muted-foreground hover:underline">
            忘記密碼?
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
