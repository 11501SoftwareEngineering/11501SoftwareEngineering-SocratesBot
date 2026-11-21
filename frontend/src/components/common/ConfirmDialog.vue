<script setup lang="ts">
/**
 * 確認對話框：刪除、退出課程這類「做了就回不去」的操作，一定要先問一次。
 *
 * 用法：
 *   const deleteOpen = ref(false)
 *   const deleting = ref<Teacher | null>(null)
 *   function askDelete(t: Teacher) { deleting.value = t; deleteOpen.value = true }
 *
 *   <ConfirmDialog
 *     v-model:open="deleteOpen"
 *     title="確定要刪除這位老師嗎？"
 *     :description="`刪除後「${deleting?.name}」將無法登入，這個動作無法復原。`"
 *     confirm-text="刪除" destructive
 *     :loading="deleteMutation.isPending.value"
 *     @confirm="deleteMutation.mutate(deleting!.id, { onSuccess: () => (deleteOpen = false) })"
 *   />
 *
 * - loading 時按鈕會變成「處理中…」並且不能再按，避免重複送出
 * - 按 Esc、點背景或「取消」都會關閉
 * - 開啟時焦點會移到對話框裡，關閉後回到原本的按鈕（reka-ui 自動處理）
 */
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

withDefaults(
  defineProps<{
    title: string
    description?: string
    confirmText?: string
    cancelText?: string
    /** 危險操作（刪除）：確認按鈕改用紅色 */
    destructive?: boolean
    loading?: boolean
    /** 操作失敗時顯示的錯誤訊息 */
    error?: string
    /** 管理員頁的舊版樣式（Figma「P15_Confirm」）：置中、大按鈕 */
    centered?: boolean
    /**
     * 確認鈕放左邊、取消鈕改成主色放右邊。Figma「P11_Confirm」離開提醒：左「離開」（紅）右「留下」（主色）
     */
    confirmFirst?: boolean
  }>(),
  {
    confirmText: '確定',
    cancelText: '取消',
    destructive: false,
    loading: false,
    centered: false,
    confirmFirst: false,
  },
)

const open = defineModel<boolean>('open', { default: false })
defineEmits<{ confirm: [] }>()
</script>

<template>
  <!--
    版面對應 Figma「P11_Confirm」「P10_AddTA_Confirm」「P14_RemoveKey」：
    寬 404、內距 32、間距 16；標題 22px、說明 18px 輔色，靠左；右下小按鈕「取消」「確認」。
    centered 時對應管理員的「P15_Confirm」：置中標題＋說明，下方大按鈕。
  -->
  <Dialog v-model:open="open">
    <DialogContent
      :show-close-button="false"
      class="w-[calc(100%-2rem)] rounded-2xl border-0 bg-card p-8 shadow-elevated sm:max-w-[404px]"
      :class="centered ? 'gap-6' : 'gap-4'"
    >
      <DialogHeader
        :class="centered ? 'gap-3 text-center sm:text-center' : 'gap-4 text-left sm:text-left'"
      >
        <DialogTitle
          :class="
            centered
              ? 'text-h1-title font-bold text-foreground'
              : 'text-header font-medium text-foreground'
          "
          >{{ title }}</DialogTitle
        >
        <DialogDescription
          v-if="description || $slots.default"
          as="div"
          class="text-body-lg text-muted-foreground"
        >
          <slot>{{ description }}</slot>
        </DialogDescription>
      </DialogHeader>

      <p
        v-if="error"
        role="alert"
        class="text-body text-destructive"
        :class="centered && 'text-center'"
      >
        {{ error }}
      </p>

      <DialogFooter
        class="flex-row gap-3"
        :class="centered ? 'justify-center gap-4 sm:justify-center' : 'justify-end sm:justify-end'"
      >
        <DialogClose as-child>
          <Button
            :variant="confirmFirst ? 'default' : 'secondary'"
            :size="centered ? 'lg' : 'sm'"
            :class="confirmFirst && 'order-last'"
            :disabled="loading"
            >{{ cancelText }}</Button
          >
        </DialogClose>
        <Button
          :variant="destructive ? 'destructive' : 'default'"
          :size="centered ? 'lg' : 'sm'"
          :disabled="loading"
          @click="$emit('confirm')"
        >
          {{ loading ? '處理中…' : confirmText }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
