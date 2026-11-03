<script setup lang="ts">
/**
 * 註冊頁（學生自己註冊）。對應 Figma「Register」（node 163:82）。
 * API：POST /auth/register，成功後直接幫他登入。
 *
 * Figma 沒有「姓名」，但後端註冊必填，而且老師的學生名單會顯示姓名，所以加了這個欄位。
 */
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useMutation } from '@tanstack/vue-query'
import { authApi } from '@/api/auth'
import AppLogo from '@/components/common/AppLogo.vue'
import AuthCard from '@/components/common/AuthCard.vue'
import FormField from '@/components/common/FormField.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { HOME_ROUTE, useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const form = reactive({ account: '', name: '', password: '', confirm: '' })
const errors = reactive({ account: '', name: '', password: '', confirm: '' })
const formError = ref('')

const mutation = useMutation({
  mutationFn: async () => {
    const account = form.account.trim()
    await authApi.register({ account, password: form.password, name: form.name.trim() })
    return authStore.login({ account, password: form.password })
  },
  onSuccess: (user) => router.replace({ name: HOME_ROUTE[user.role] }),
  onError: (error) => {
    formError.value = getApiErrorMessage(error, '註冊失敗，請稍後再試')
  },
})

function handleSubmit() {
  const account = form.account.trim()
  errors.account = !account ? '請輸入帳號名稱' : account.length > 64 ? '帳號名稱最多 64 個字' : ''
  const name = form.name.trim()
  errors.name = !name ? '請輸入姓名' : name.length > 128 ? '姓名最多 128 個字' : ''
  errors.password =
    form.password.length < 8
      ? '密碼至少要 8 個字元'
      : form.password.length > 128
        ? '密碼最多 128 個字元'
        : ''
  errors.confirm = form.confirm === form.password ? '' : '兩次輸入的密碼不一樣'
  formError.value = ''
  if (errors.account || errors.name || errors.password || errors.confirm) return
  mutation.mutate()
}
</script>

<template>
  <AuthCard>
    <AppLogo :size="160" class="mx-auto" />

    <form class="mt-8 flex flex-col gap-5" novalidate @submit.prevent="handleSubmit">
      <FormField
        v-slot="field"
        label="帳號名稱"
        hint="登入時使用，最多 64 個字"
        :error="errors.account"
      >
        <Input v-model="form.account" v-bind="field" :id="field.id" autocomplete="username" />
      </FormField>
      <FormField v-slot="field" label="姓名" hint="老師會在學生名單看到" :error="errors.name">
        <Input v-model="form.name" v-bind="field" :id="field.id" autocomplete="name" />
      </FormField>
      <FormField v-slot="field" label="建立密碼" hint="至少 8 個字元" :error="errors.password">
        <Input
          v-model="form.password"
          v-bind="field"
          :id="field.id"
          type="password"
          autocomplete="new-password"
        />
      </FormField>
      <FormField v-slot="field" label="確認密碼" :error="errors.confirm || formError">
        <Input
          v-model="form.confirm"
          v-bind="field"
          :id="field.id"
          type="password"
          autocomplete="new-password"
        />
      </FormField>

      <div class="flex flex-wrap items-center justify-between gap-4">
        <p class="text-body text-foreground">
          已經有帳號了嗎？
          <RouterLink
            :to="{ name: 'Login' }"
            class="rounded underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >點此登入</RouterLink
          >
        </p>
        <Button type="submit" size="lg" class="ml-auto" :disabled="mutation.isPending.value">
          {{ mutation.isPending.value ? '註冊中…' : '註冊' }}
        </Button>
      </div>
    </form>
  </AuthCard>
</template>
