<script setup lang="ts">
/**
 * 顯示一次性初始密碼（建立老師帳號、重設密碼之後）。
 * 後端只會回傳這一次，關掉就看不到了，所以提供「複製」按鈕。
 */
import { computed, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

const props = defineProps<{
  title: string
  account: string
  name: string
  password: string
}>()

const open = defineModel<boolean>('open', { default: false })
const rows = computed(() => [
  { label: '帳號', value: props.account },
  { label: '教師姓名', value: props.name },
  { label: '初始密碼', value: props.password },
])
const copied = ref(false)

watch(
  () => props.password,
  () => (copied.value = false),
)

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(`帳號：${props.account}\n初始密碼：${props.password}`)
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
        請把帳號和初始密碼交給{{ name }}，這組密碼只會顯示這一次。
      </DialogDescription>
      <dl class="mt-5 flex flex-col pt-[10px] text-h1-title text-foreground">
        <div v-for="row in rows" :key="row.label" class="flex min-h-[77px] items-center gap-2">
          <dt class="w-[165px] shrink-0 font-bold">{{ row.label }}：</dt>
          <dd class="min-w-0 flex-1 break-all font-normal">{{ row.value }}</dd>
        </div>
      </dl>
      <p class="pt-1 text-right text-header text-destructive">請將帳號密碼交給老師</p>
      <p v-if="copied" role="status" class="mt-2 text-right text-body text-muted-foreground">
        已複製帳號與密碼
      </p>
      <div class="mt-5 flex justify-end gap-5 py-2">
        <Button variant="secondary" size="lg" @click="handleCopy">複製帳號與密碼</Button>
        <Button size="lg" @click="open = false">完成</Button>
      </div>
    </DialogContent>
  </Dialog>
</template>
