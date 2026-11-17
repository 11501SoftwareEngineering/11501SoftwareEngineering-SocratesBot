<script setup lang="ts">
/**
 * 顯示一次性初始密碼（建立老師帳號、重設密碼之後）。
 * 後端只會回傳這一次，關掉就看不到了，所以提供「複製」按鈕。
 */
import { computed, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  title: string
  account: string
  name: string
  password: string
}>()

const open = defineModel<boolean>('open', { default: false })
const rows = computed(() => [
  { label: t('auth.account'), value: props.account },
  { label: t('password.teacherName'), value: props.name },
  { label: t('password.initial'), value: props.password },
])
const copied = ref(false)

watch(
  () => props.password,
  () => (copied.value = false),
)

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(
      t('password.clipboard', { account: props.account, password: props.password }),
    )
    copied.value = true
  } catch {
    copied.value = false
  }
}
</script>

<template>
  <!-- Figma「P15_TeacherCreated」：標題 40px；帳號／教師姓名／初始密碼 32px（標籤粗體寬 165px）；
       右側紅字提醒；下方大按鈕「複製帳號與密碼」「完成」 -->
  <Dialog v-model:open="open">
    <DialogContent
      :show-close-button="false"
      class="w-[calc(100%-2rem)] gap-0 rounded-2xl border border-border bg-card px-6 py-[28px] shadow-elevated sm:max-w-[626px] sm:px-[69px]"
    >
      <DialogTitle class="text-center text-page-title font-bold text-foreground">{{
        title
      }}</DialogTitle>
      <DialogDescription class="sr-only">
        {{ t('password.noticeDescription', { name }) }}
      </DialogDescription>
      <dl class="mt-5 flex flex-col pt-[10px] text-h1-title text-foreground">
        <div v-for="row in rows" :key="row.label" class="flex min-h-[77px] items-center gap-2">
          <dt class="w-[165px] shrink-0 font-bold">
            {{ t('common.labelColon', { label: row.label }) }}
          </dt>
          <dd class="min-w-0 flex-1 break-all font-normal">{{ row.value }}</dd>
        </div>
      </dl>
      <p class="pt-1 text-right text-header text-destructive">{{ t('password.giveToTeacher') }}</p>
      <p v-if="copied" role="status" class="mt-2 text-right text-body text-muted-foreground">
        {{ t('password.copiedNotice') }}
      </p>
      <div class="mt-5 flex justify-end gap-5 py-2">
        <Button variant="secondary" size="lg" @click="handleCopy">{{ t('password.copy') }}</Button>
        <Button size="lg" @click="open = false">{{ t('common.done') }}</Button>
      </div>
    </DialogContent>
  </Dialog>
</template>
