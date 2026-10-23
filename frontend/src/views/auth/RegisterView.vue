<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { getApiErrorMessage } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const router = useRouter()

const account = ref('')
const name = ref('')
const password = ref('')
const confirmPassword = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const isSubmitting = ref(false)

async function handleRegister() {
  errorMessage.value = ''
  successMessage.value = ''

  // 檢查密碼長度
  if (password.value.length < 8) {
    errorMessage.value = '密碼至少需要 8 個字'
    return
  }

  // 檢查兩次密碼是否一致
  if (password.value !== confirmPassword.value) {
    errorMessage.value = '兩次輸入的密碼不一致'
    return
  }

  isSubmitting.value = true
  try {
    await authApi.register({
      account: account.value,
      password: password.value,
      name: name.value,
    })

    // 顯示成功訊息並延遲跳轉回登入頁
    successMessage.value = '註冊成功，請登入'
    setTimeout(() => {
      router.push('/login')
    }, 1500)
  } catch (err) {
    errorMessage.value = getApiErrorMessage(err)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="flex items-center justify-center bg-background px-4 py-12">
    <div
      class="w-full max-w-[500px] flex flex-col items-center gap-8 rounded-2xl border border-border bg-card px-10 py-12 shadow-elevated"
    >
      <!-- Logo 區 -->
      <div class="flex justify-center w-full">
        <img src="@/assets/logo.svg" alt="Logo" class="h-32 w-32 object-contain" />
      </div>

      <!-- 註冊表單 -->
      <form class="flex w-full flex-col gap-6" @submit.prevent="handleRegister">
        <!-- 帳號名稱欄位 -->
        <div class="flex items-center gap-4">
          <label
            for="register-account"
            class="w-24 shrink-0 font-heading text-lg font-medium text-foreground text-right"
            >帳號名稱：</label
          >
          <Input
            id="register-account"
            v-model="account"
            class="flex-1 shadow-input"
            placeholder="請輸入帳號"
            autocomplete="username"
            required
          />
        </div>

        <!-- 姓名欄位 -->
        <div class="flex items-center gap-4">
          <label
            for="register-name"
            class="w-24 shrink-0 font-heading text-lg font-medium text-foreground text-right"
            >姓名：</label
          >
          <Input
            id="register-name"
            v-model="name"
            class="flex-1 shadow-input"
            placeholder="請輸入真實姓名"
            required
          />
        </div>

        <!-- 建立密碼欄位 -->
        <div class="flex items-center gap-4">
          <label
            for="register-password"
            class="w-24 shrink-0 font-heading text-lg font-medium text-foreground text-right"
            >建立密碼：</label
          >
          <Input
            id="register-password"
            v-model="password"
            type="password"
            class="flex-1 shadow-input"
            placeholder="至少 8 個字"
            autocomplete="new-password"
            required
          />
        </div>

        <!-- 確認密碼欄位 -->
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-4">
            <label
              for="register-confirm-password"
              class="w-24 shrink-0 font-heading text-lg font-medium text-foreground text-right"
              >確認密碼：</label
            >
            <Input
              id="register-confirm-password"
              v-model="confirmPassword"
              type="password"
              class="flex-1 shadow-input"
              placeholder="請再次輸入密碼"
              autocomplete="new-password"
              required
            />
          </div>
          <p v-if="errorMessage" class="w-full text-right text-sm text-destructive pr-1 pt-1">
            {{ errorMessage }}
          </p>
          <p v-if="successMessage" class="w-full text-right text-sm text-green-600 pr-1 pt-1">
            {{ successMessage }}
          </p>
        </div>

        <!-- 底部連結與按鈕區 -->
        <div class="flex w-full items-end justify-between pt-4">
          <router-link to="/login" class="text-sm text-muted-foreground hover:underline pb-2">
            已經有帳號了嗎？ 點此登入
          </router-link>

          <Button type="submit" size="lg" class="w-24" :disabled="isSubmitting">
            {{ isSubmitting ? '註冊中...' : '註冊' }}
          </Button>
        </div>
      </form>
    </div>
  </div>
</template>
