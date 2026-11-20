<script setup lang="ts">
/**
 * 成員卡片（課程成員、助教）。對應 Figma 元件「Card_Botton」「Card_TA」：
 *   姓名（20px）＋帳號（18px 輔色字），右邊放按鈕（移除）
 *   #details：卡片下方多一段（例如助教權限）
 */
import { cardClass } from '@/lib/ui'

defineProps<{ name: string; account: string }>()
</script>

<template>
  <!-- Figma「Card_TA」（node 693:4280）：滑過時背景色 #F7F6F2、外框 1.5px 文字輔色 -->
  <article
    :class="[
      cardClass,
      'flex flex-col gap-1 p-4 transition-colors hover:border-[1.5px] hover:border-muted-foreground hover:bg-background',
    ]"
  >
    <div class="flex items-center justify-between gap-3">
      <div class="min-w-0">
        <h3 class="truncate font-heading text-h2-title text-foreground">{{ name }}</h3>
        <p class="truncate text-body-lg text-muted-foreground">{{ account }}</p>
      </div>
      <div v-if="$slots.actions" class="flex shrink-0 items-center gap-1">
        <slot name="actions" />
      </div>
    </div>
    <slot name="details" />
  </article>
</template>
