<script setup lang="ts">
/**
 * 頁面層級的訊息框。對應 Figma 元件頁「Banner」（node 758:2437）：
 *   圓角 8、外框 1px、內距 20/12、圖示 24px、間距 12、18px 文字
 *   error   ⊗  白底、點綴色外框、點綴色_深文字（操作失敗）
 *   success ✓  主色_淺底、主色外框（已儲存、已加入）
 *   lock    🔒 輔色_淺底、輔色外框（已發布、不能修改）
 *   info    📌 白底、圖形外框、文字輔色（提示）
 * 欄位底下的錯誤字不要用這個，用欄位元件自己的錯誤顯示。
 *
 * 用法：<AppBanner type="error">儲存失敗，請稍後再試</AppBanner>
 */
import { CheckRingIcon, CloseRingIcon, LockIcon, PinIcon } from '@/components/icons'

defineProps<{ type: 'error' | 'success' | 'lock' | 'info' }>()

const styles = {
  error: 'border-destructive bg-card text-destructive-dark',
  success: 'border-primary bg-primary-light text-foreground',
  lock: 'border-secondary bg-secondary-light text-foreground',
  info: 'border-border bg-card text-muted-foreground',
} as const
const icons = { error: CloseRingIcon, success: CheckRingIcon, lock: LockIcon, info: PinIcon }
</script>

<template>
  <div
    :role="type === 'error' ? 'alert' : 'status'"
    class="flex items-center gap-3 rounded-lg border px-5 py-3 text-body-lg"
    :class="styles[type]"
  >
    <component :is="icons[type]" class="shrink-0" />
    <div class="min-w-0 flex-1"><slot /></div>
  </div>
</template>
