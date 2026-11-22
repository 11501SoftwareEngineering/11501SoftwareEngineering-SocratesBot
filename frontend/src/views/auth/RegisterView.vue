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
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const authStore = useAuthStore()
const router = useRouter()

const form = reactive({ account: '', name: '', password: '', confirm: '' })
const errors = reactive({ account: '', name: '', password: '', confirm: '' })
const formError = ref('')

const mutation = useMutation({
  mutationFn: async () => {
    const account = form.account.trim()
    await authApi.register({ account_id: account, password: form.password, name: form.name.trim() })
    return authStore.login({ account_id: account, password: form.password })
  },
  onSuccess: () => router.replace({ name: authStore.homeRoute }),
  onError: (error) => {
    formError.value = getApiErrorMessage(error, t('auth.registerFailed'))
  },
})

function handleSubmit() {
  const account = form.account.trim()
  errors.account = !account
    ? t('auth.accountNameRequired')
    : account.length > 64
      ? t('auth.accountNameTooLong')
      : ''
  const name = form.name.trim()
  errors.name = !name ? t('auth.nameRequired') : name.length > 128 ? t('auth.nameTooLong') : ''
  errors.password =
    form.password.length < 8
      ? t('auth.password.tooShort')
      : form.password.length > 128
        ? t('auth.password.tooLong')
        : ''
  errors.confirm = form.confirm === form.password ? '' : t('auth.password.mismatch')
  formError.value = ''
  if (errors.account || errors.name || errors.password || errors.confirm) return
  mutation.mutate()
}
</script>

<template>
  <AuthCard>
    <!-- Figma「P03_Register」：Logo 210px；標籤寬 165px -->
    <AppLogo :size="210" class="mx-auto" />

    <form class="mt-5 flex flex-col gap-3" novalidate @submit.prevent="handleSubmit">
      <FormField
        v-slot="field"
        :label="t('auth.accountName')"
        :hint="t('auth.accountNameHint')"
        :error="errors.account"
      >
        <Input v-model="form.account" v-bind="field" :id="field.id" autocomplete="username" />
      </FormField>
      <FormField
        v-slot="field"
        :label="t('auth.realName')"
        :hint="t('auth.realNameHint')"
        :error="errors.name"
      >
        <Input v-model="form.name" v-bind="field" :id="field.id" autocomplete="name" />
      </FormField>
      <FormField
        v-slot="field"
        :label="t('auth.password.create')"
        :hint="t('auth.password.hint')"
        :error="errors.password"
      >
        <Input
          v-model="form.password"
          v-bind="field"
          :id="field.id"
          type="password"
          autocomplete="new-password"
        />
      </FormField>
      <FormField
        v-slot="field"
        :label="t('auth.password.confirm')"
        :error="errors.confirm || formError"
      >
        <Input
          v-model="form.confirm"
          v-bind="field"
          :id="field.id"
          type="password"
          autocomplete="new-password"
        />
      </FormField>

      <div class="flex flex-wrap items-center justify-between gap-4">
        <p class="text-body-lg text-foreground">
          {{ t('auth.hasAccount') }}
          <RouterLink
            :to="{ name: 'Login' }"
            class="rounded underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >{{ t('auth.goLogin') }}</RouterLink
          >
        </p>
        <Button type="submit" size="lg" class="ml-auto" :disabled="mutation.isPending.value">
          {{ mutation.isPending.value ? t('auth.registering') : t('auth.register') }}
        </Button>
      </div>
    </form>
  </AuthCard>
</template>
