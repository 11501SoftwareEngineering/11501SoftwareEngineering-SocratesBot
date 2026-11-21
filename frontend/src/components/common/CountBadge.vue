<script setup lang="ts">
/**
 * 數量圓圈。對應 Figma 標題旁的灰色圓（例如「我的課程 10」「學生報告 10」）。
 */
defineProps<{ count: number; label?: string }>()
</script>

<template>
  <span
    class="inline-flex h-[37px] min-w-[37px] items-center justify-center rounded-full bg-border px-1.5 font-heading text-h2-title text-foreground"
    :aria-label="label ? `${label} ${count}` : undefined"
    >{{ count }}</span
  >
</template>
