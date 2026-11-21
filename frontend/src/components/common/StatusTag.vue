<script setup lang="ts">
/**
 * 狀態標籤。對應 Figma 元件「State」（node 719:4710）：
 *   tone="primary"：主色淺底（已發布、已完成、已表達立場）
 *   tone="secondary"：輔色淺底（草稿、尚未開始、進行中）
 *   tone="accent"：點綴色底（Figma State Variant3 #D29E97，例如時間軸的「觀點修正」）
 *   size="sm"：時間軸、報告裡的小標籤
 */
withDefaults(defineProps<{ tone?: 'primary' | 'secondary' | 'accent'; size?: 'md' | 'sm' }>(), {
  tone: 'primary',
  size: 'md',
})
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center justify-center rounded-2xl font-bold whitespace-nowrap text-foreground"
    :class="[
      tone === 'primary' && 'bg-primary-light',
      tone === 'secondary' && 'bg-secondary-light',
      tone === 'accent' && 'bg-destructive',
      size === 'md' ? 'px-4 py-1 text-body-lg' : 'px-2.5 py-0.5 text-sm',
    ]"
    ><slot
  /></span>
</template>
