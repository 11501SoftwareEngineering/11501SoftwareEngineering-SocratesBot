<script setup lang="ts">
/**
 * 管理員：老師帳號管理。對應 Figma「Admin_Home」（node 171:119）、「AddTeacher」「Comfire」。
 * API：GET/POST /admin/teachers、DELETE /admin/teachers/{id}
 *      ⚠️ 重設密碼 POST /admin/teachers/{id}/reset-password 是前端假設的
 *
 * Figma 的「建立教師帳號」要管理員自己輸入密碼，但後端是自動產生一次性初始密碼，
 * 所以表單改成輸入帳號和姓名，建立後顯示初始密碼。
 */
import { reactive, ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { adminApi, adminKeys, type Teacher, type TeacherPasswordResponse } from '@/api/admin'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import FormDialog from '@/components/common/FormDialog.vue'
import FormField from '@/components/common/FormField.vue'
import ListCard from '@/components/common/ListCard.vue'
import ListSection from '@/components/common/ListSection.vue'
import PasswordNoticeDialog from '@/components/common/PasswordNoticeDialog.vue'
import QueryState from '@/components/common/QueryState.vue'
import { AddRingIcon, RefreshIcon, TrashIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useSearch } from '@/composables/useSearch'
import { formatDate, getApiErrorMessage } from '@/lib/utils'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const queryClient = useQueryClient()
const { data, isPending, error, refetch } = useQuery({
  queryKey: adminKeys.teachers,
  queryFn: adminApi.getTeachers,
})
const { keyword, results } = useSearch(
  () => data.value ?? [],
  (t) => [t.account_id, t.name],
)
const refresh = () => queryClient.invalidateQueries({ queryKey: adminKeys.teachers })

// ----- 新增老師 -----
const createOpen = ref(false)
const form = reactive({ account: '', name: '' })
const errors = reactive({ account: '', name: '', form: '' })

function openCreate() {
  Object.assign(form, { account: '', name: '' })
  Object.assign(errors, { account: '', name: '', form: '' })
  createOpen.value = true
}

// ----- 顯示初始密碼 -----
const notice = ref<(TeacherPasswordResponse & { title: string }) | null>(null)
const noticeOpen = ref(false)
function showPassword(result: TeacherPasswordResponse, title: string) {
  notice.value = { ...result, title }
  noticeOpen.value = true
}

const createMutation = useMutation({
  mutationFn: () =>
    adminApi.createTeacher({ account_id: form.account.trim(), name: form.name.trim() }),
  onSuccess: (result) => {
    createOpen.value = false
    void refresh()
    showPassword(result, t('password.created'))
  },
  onError: (err) => (errors.form = getApiErrorMessage(err, t('admin.createFailed'))),
})

function handleCreate() {
  errors.account = form.account.trim() ? '' : t('auth.accountNameRequired')
  errors.name = form.name.trim() ? '' : t('admin.nameRequired')
  errors.form = ''
  if (errors.account || errors.name) return
  createMutation.mutate()
}

// ----- 重設密碼、刪除 -----
const target = ref<Teacher | null>(null)
const resetOpen = ref(false)
const deleteOpen = ref(false)
const actionError = ref('')

function ask(teacher: Teacher, action: 'reset' | 'delete') {
  target.value = teacher
  actionError.value = ''
  if (action === 'reset') resetOpen.value = true
  else deleteOpen.value = true
}

const resetMutation = useMutation({
  mutationFn: async (teacher: Teacher) => {
    const result = await adminApi.resetTeacherPassword(teacher.id)
    return { account_id: teacher.account_id, name: teacher.name, password: result.password }
  },
  onSuccess: (result) => {
    resetOpen.value = false
    showPassword(result, t('password.reset'))
  },
  onError: (err) => (actionError.value = getApiErrorMessage(err, t('admin.resetFailed'))),
})

const deleteMutation = useMutation({
  mutationFn: (id: string) => adminApi.deleteTeacher(id),
  onSuccess: () => {
    deleteOpen.value = false
    void refresh()
  },
  onError: (err) => (actionError.value = getApiErrorMessage(err, t('errors.deleteFailed'))),
})
</script>

<template>
  <div class="mx-auto w-full max-w-[992px] px-4 py-10 sm:py-12">
    <ListSection
      v-model:search="keyword"
      :title="t('admin.title')"
      :search-label="t('admin.search')"
    >
      <template #actions>
        <Button @click="openCreate"><AddRingIcon /> {{ t('admin.addTeacher') }}</Button>
      </template>

      <QueryState
        :loading="isPending"
        :error="error"
        :empty="results.length === 0"
        :empty-text="keyword ? t('admin.notFound') : t('admin.empty')"
        :error-text="t('admin.loadError')"
        @retry="refetch()"
      >
        <ListCard
          v-for="teacher in results"
          :key="teacher.id"
          :title="t('admin.account', { account: teacher.account_id })"
          :meta="[
            t('admin.name', { name: teacher.name }),
            t('admin.createdAt', { date: formatDate(teacher.created_at) }),
          ]"
        >
          <template #actions>
            <Button
              variant="secondary"
              :aria-label="t('admin.resetAria', { name: teacher.name })"
              @click="ask(teacher, 'reset')"
            >
              <RefreshIcon /> <span class="hidden sm:inline">{{ t('admin.password.reset') }}</span>
            </Button>
            <Button
              variant="destructive"
              :aria-label="t('admin.deleteAria', { name: teacher.name })"
              @click="ask(teacher, 'delete')"
            >
              <TrashIcon /> <span class="hidden sm:inline">{{ t('common.delete') }}</span>
            </Button>
          </template>
        </ListCard>
      </QueryState>
    </ListSection>

    <FormDialog
      v-model:open="createOpen"
      :title="t('admin.createTitle')"
      :loading="createMutation.isPending.value"
      :error="errors.form"
      @submit="handleCreate"
    >
      <FormField
        v-slot="field"
        :label="t('auth.accountName')"
        :hint="t('admin.accountHint')"
        :error="errors.account"
      >
        <Input v-model="form.account" v-bind="field" :id="field.id" autocomplete="off" />
      </FormField>
      <FormField
        v-slot="field"
        :label="t('password.teacherName')"
        :hint="t('admin.nameHint')"
        :error="errors.name"
      >
        <Input v-model="form.name" v-bind="field" :id="field.id" autocomplete="off" />
      </FormField>
    </FormDialog>

    <ConfirmDialog
      centered
      v-model:open="resetOpen"
      :title="t('admin.resetConfirmTitle')"
      :description="t('admin.resetConfirmDescription', { name: target?.name ?? '' })"
      :confirm-text="t('admin.reset')"
      :loading="resetMutation.isPending.value"
      :error="actionError"
      @confirm="target && resetMutation.mutate(target)"
    />

    <ConfirmDialog
      centered
      v-model:open="deleteOpen"
      :title="t('admin.deleteConfirmTitle')"
      :description="t('admin.deleteConfirmDescription', { name: target?.name ?? '' })"
      :confirm-text="t('common.ok')"
      destructive
      :loading="deleteMutation.isPending.value"
      :error="actionError"
      @confirm="target && deleteMutation.mutate(target.id)"
    />

    <PasswordNoticeDialog
      v-if="notice"
      v-model:open="noticeOpen"
      :title="notice.title"
      :account="notice.account_id"
      :name="notice.name"
      :password="notice.password"
    />
  </div>
</template>
