<script setup lang="ts">
/**
 * 登入頁。對應 Figma「Login」（node 125:62）。
 * API：POST /auth/login（token 在回應的 Authorization header）
 */
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useMutation } from '@tanstack/vue-query'
import AppLogo from '@/components/common/AppLogo.vue'
import AuthCard from '@/components/common/AuthCard.vue'
import FormField from '@/components/common/FormField.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { HOME_ROUTE, useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({ account: '', password: '' })
const errors = reactive({ account: '', password: '' })
const formError = ref('')
const showForgotHint = ref(false)

const mutation = useMutation({
  mutationFn: () => authStore.login({ account: form.account.trim(), password: form.password }),
  onSuccess: (user) => {
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    // 只接受站內路徑，避免被導到外部網站
    if (redirect.startsWith('/') && !redirect.startsWith('//')) {
      void router.replace(redirect)
    } else {
      void router.replace({ name: HOME_ROUTE[user.role] })
    }
  },
  onError: (error) => {
    formError.value = getApiErrorMessage(error, '登入失敗，請稍後再試')
  },
})

function handleSubmit() {
  errors.account = form.account.trim() ? '' : '請輸入帳號'
  errors.password = form.password ? '' : '請輸入密碼'
  formError.value = ''
  if (errors.account || errors.password) return
  mutation.mutate()
}
</script>

<template>
  <AuthCard>
    <AppLogo :size="200" class="mx-auto" />

    <p
      v-if="authStore.sessionExpired"
      role="status"
      class="mt-6 rounded-lg bg-secondary/60 px-4 py-2 text-center text-body text-foreground"
    >
      登入已過期，請重新登入
    </p>

    <form class="mt-8 flex flex-col gap-5" novalidate @submit.prevent="handleSubmit">
      <FormField v-slot="field" label="帳號" :error="errors.account">
        <Input v-model="form.account" v-bind="field" :id="field.id" autocomplete="username" />
      </FormField>
      <FormField v-slot="field" label="密碼" :error="errors.password || formError">
        <Input
          v-model="form.password"
          v-bind="field"
          :id="field.id"
          type="password"
          autocomplete="current-password"
        />
      </FormField>

      <div class="flex items-center justify-end gap-4">
        <Button as-child variant="ghost" size="lg" class="font-medium">
          <RouterLink :to="{ name: 'Register' }">註冊</RouterLink>
        </Button>
        <Button type="submit" size="lg" :disabled="mutation.isPending.value">
          {{ mutation.isPending.value ? '登入中…' : '登入' }}
        </Button>
      </div>
      <div class="text-right">
        <button
          type="button"
          class="rounded text-body text-foreground underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
          :aria-expanded="showForgotHint"
          @click="showForgotHint = !showForgotHint"
        >
          忘記密碼?
        </button>
        <p v-if="showForgotHint" class="mt-1 text-body text-muted-foreground">
          請聯絡老師或管理員協助重設密碼。
        </p>
      </div>
    </form>
  </AuthCard>
</template>
