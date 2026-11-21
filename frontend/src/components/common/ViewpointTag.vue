<script setup lang="ts">
/**
 * 觀點標籤（可點選篩選）。對應 Figma 元件頁「tag」（node 725:2132）：
 *   左邊 15px 色點、文字 18px、內距 16/4、圓角 32、外陰影
 *   Default 白底；hover 背景色 #F7F6F2；selected 底色圖形外框、外框 2px 文字輔色、右邊 ⊗
 *
 * 用法：<ViewpointTag :label="g.name" :color="groupColor(i)" :selected="…" @click="…" />
 */
import { CloseRingIcon } from '@/components/icons'

defineProps<{ label: string; color: string; selected?: boolean }>()
</script>

<template>
  <button
    type="button"
    class="flex w-full items-center gap-2 overflow-hidden rounded-[32px] px-4 py-1 text-body-lg text-foreground shadow-elevated outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50"
    :class="
      selected
        ? 'border-2 border-muted-foreground bg-border'
        : 'border border-border bg-card hover:bg-background'
    "
    :aria-pressed="selected"
  >
    <span
      class="size-[15px] shrink-0 rounded-full"
      :style="{ backgroundColor: color }"
      aria-hidden="true"
    />
    <span class="min-w-0 flex-1 truncate text-left" :title="label">{{ label }}</span>
    <CloseRingIcon v-if="selected" class="size-6 shrink-0" />
  </button>
</template>
