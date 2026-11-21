<script setup lang="ts">
/**
 * 區塊標題：粗體標題＋數量圓圈，右邊放按鈕。對應 Figma「我的課程 10 ⊕新增課程」「探究活動 10 ⊕新增活動」。
 *
 * 用法：
 *   <SectionHeading title="探究活動" :count="10">
 *     <template #actions><Button>新增活動</Button></template>
 *   </SectionHeading>
 */
import CountBadge from '@/components/common/CountBadge.vue'

withDefaults(defineProps<{ title: string; count?: number; level?: 1 | 2 }>(), { level: 2 })
</script>

<template>
  <div class="flex items-center justify-between gap-4">
    <div class="flex min-w-0 items-center gap-2">
      <component :is="`h${level}`" class="truncate text-h1-title text-foreground">{{
        title
      }}</component>
      <CountBadge v-if="count !== undefined" :count="count" />
    </div>
    <div v-if="$slots.actions" class="flex shrink-0 items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
