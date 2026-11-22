<script setup lang="ts">
/**
 * 修改密碼。對應 Figma「Common_ChangePassword」（node 699:2152）。從帳號選單打開。
 *
 * 老師帳號第一次登入（must_change_password）時強制打開，改完才能用其他功能（後端也會擋）：
 * 對應 Figma「Common_FirstLoginPassword」（node 1022:3084）：只有新密碼、確認密碼，按鈕是「登出」「確認」。
 * 原密碼用登入時輸入的初始密碼；重新整理後記憶體裡沒有了，才會多出「原密碼」欄位。
 */
import { computed, reactive, ref, watch } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import { authApi } from '@/api/auth'
import FormDialog from '@/components/common/FormDialog.vue'
import FormField from '@/components/common/FormField.vue'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{ forced?: boolean }>()
const open = defineModel<boolean>('open', { default: false })

const authStore = useAuthStore()
const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const errors = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const formError = ref('')

// 三個欄位都是密碼框，只差標籤、提示和瀏覽器自動填入的種類
const allFields = computed(
  () =>
    [
      { key: 'oldPassword', label: t('password.old'), autocomplete: 'current-password' },
      {
        key: 'newPassword',
        label: t('password.new'),
        hint: t('password.hint'),
        autocomplete: 'new-password',
      },
      { key: 'confirm', label: t('password.confirm'), autocomplete: 'new-password' },
    ] as const,
)

/** 第一次登入、而且記得初始密碼：不用再問原密碼 */
const firstLogin = computed(() => props.forced && !!authStore.initialPassword)
const fields = computed(() =>
  allFields.value.filter((f) => !(firstLogin.value && f.key === 'oldPassword')),
)
const done = ref(false)

watch(open, (isOpen) => {
  if (!isOpen) return
  Object.assign(form, { oldPassword: '', newPassword: '', confirm: '' })
  Object.assign(errors, { oldPassword: '', newPassword: '', confirm: '' })
  formError.value = ''
  done.value = false
})

const mutation = useMutation({
  mutationFn: () =>
    authApi.changePassword({
      old_password: firstLogin.value ? (authStore.initialPassword ?? '') : form.oldPassword,
      new_password: form.newPassword,
    }),
  onSuccess: () => {
    authStore.markPasswordChanged()
    open.value = false
  },
  onError: (error) => {
    formError.value = getApiErrorMessage(error, t('password.failed'))
  },
})

function handleSubmit() {
  errors.oldPassword = firstLogin.value || form.oldPassword ? '' : t('password.oldRequired')
  errors.newPassword = form.newPassword.length >= 8 ? '' : t('password.tooShort')
  errors.confirm = form.confirm === form.newPassword ? '' : t('password.mismatch')
  formError.value = ''
  if (errors.oldPassword || errors.newPassword || errors.confirm) return
  mutation.mutate()
}
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="forced ? t('password.firstLoginTitle') : t('password.changeTitle')"
    :submit-text="t('common.ok')"
    :cancel-text="forced ? t('header.logout') : t('common.cancel')"
    :dismissible="!forced"
    :loading="mutation.isPending.value"
    :error="formError"
    @submit="handleSubmit"
    @cancel="authStore.logout()"
  >
    <FormField
      v-for="f in fields"
      :key="f.key"
      v-slot="field"
      :label="f.label"
      :hint="'hint' in f ? f.hint : undefined"
      :error="errors[f.key]"
    >
      <Input
        v-model="form[f.key]"
        v-bind="field"
        :id="field.id"
        type="password"
        :autocomplete="f.autocomplete"
      />
    </FormField>
  </FormDialog>
</template>
