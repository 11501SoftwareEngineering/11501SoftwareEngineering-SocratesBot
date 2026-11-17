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
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const authStore = useAuthStore()
const showForgotHint = ref(false)
const route = useRoute()
const router = useRouter()

const form = reactive({ account: '', password: '' })
const errors = reactive({ account: '', password: '' })
const formError = ref('')

const mutation = useMutation({
  mutationFn: () => authStore.login({ account_id: form.account.trim(), password: form.password }),
  onSuccess: () => {
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    // 只接受站內路徑，避免被導到外部網站
    if (redirect.startsWith('/') && !redirect.startsWith('//')) {
      void router.replace(redirect)
    } else {
      void router.replace({ name: authStore.homeRoute })
    }
  },
  onError: (error) => {
    formError.value = getApiErrorMessage(error, t('auth.loginFailed'))
  },
})

function handleSubmit() {
  errors.account = form.account.trim() ? '' : t('auth.accountRequired')
  errors.password = form.password ? '' : t('auth.password.required')
  formError.value = ''
  if (errors.account || errors.password) return
  mutation.mutate()
}
</script>

<template>
  <AuthCard>
    <!-- Figma「P04_Login」：Logo 290px、上方留 20px；標籤寬 108px、整組往右 34px；欄位間距 39px -->
    <AppLogo :size="290" class="mx-auto mt-5" />

    <p
      v-if="authStore.sessionExpired"
      role="status"
      class="mt-6 rounded-lg bg-secondary/60 px-4 py-2 text-center text-body text-foreground"
    >
      {{ t('auth.sessionExpired') }}
    </p>

    <form
      class="mt-5 flex flex-col gap-[39px] sm:pl-[34px] sm:[--form-label-width:108px]"
      novalidate
      @submit.prevent="handleSubmit"
    >
      <FormField v-slot="field" inline :label="t('auth.account')" :error="errors.account">
        <Input v-model="form.account" v-bind="field" :id="field.id" autocomplete="username" />
      </FormField>
      <FormField
        v-slot="field"
        inline
        :label="t('auth.password.label')"
        :error="errors.password || formError"
      >
        <Input
          v-model="form.password"
          v-bind="field"
          :id="field.id"
          type="password"
          autocomplete="current-password"
        />
      </FormField>

      <div class="-mt-[29px] flex flex-col items-end pt-[10px]">
        <div class="flex items-center gap-4 py-[5px]">
          <Button as-child variant="ghost" size="lg" class="font-medium">
            <RouterLink :to="{ name: 'Register' }">{{ t('auth.register') }}</RouterLink>
          </Button>
          <Button type="submit" size="lg" :disabled="mutation.isPending.value">
            {{ mutation.isPending.value ? t('auth.loggingIn') : t('auth.login') }}
          </Button>
        </div>
        <!-- 後端沒有忘記密碼的 API：點了提示找老師或管理員重設 -->
        <button
          type="button"
          class="rounded text-header text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          :aria-expanded="showForgotHint"
          @click="showForgotHint = !showForgotHint"
        >
          {{ t('auth.password.forgot') }}
        </button>
        <p v-if="showForgotHint" role="status" class="mt-1 text-body text-muted-foreground">
          {{ t('auth.password.forgotHint') }}
        </p>
      </div>
    </form>
  </AuthCard>
</template>
