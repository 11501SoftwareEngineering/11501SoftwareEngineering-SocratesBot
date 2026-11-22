<script setup lang="ts" generic="K extends string">
/**
 * 底線分頁。對應 Figma 的「個人報告｜對話紀錄｜全班摘要」「摘要審閱｜學生報告 10」「課程成員 10｜助教管理」：
 * 底下一條 2px 深色線，目前分頁下面是一條 6px 粗線。
 *
 * - 每個分頁有 to → 用網址切換（RouterLink，aria-current="page"）
 * - 沒有 to → 用 v-model 切換（按鈕，aria-pressed）
 * - size="lg"：32px 標題大小（課程頁右側的「課程成員｜助教管理」）
 * - 有數字徽章的分頁比較高：每個分頁都撐滿同一個高度，文字和底線才會對齊
 */
import type { RouteLocationRaw } from 'vue-router'
import CountBadge from '@/components/common/CountBadge.vue'

withDefaults(
  defineProps<{
    items: { key: K; label: string; count?: number; to?: RouteLocationRaw }[]
    label: string
    size?: 'md' | 'lg'
  }>(),
  { size: 'md' },
)
const current = defineModel<K>()
</script>

<template>
  <nav :aria-label="label">
    <ul class="flex border-b-2 border-foreground px-1">
      <li v-for="item in items" :key="item.key" :class="['flex', size === 'lg' && 'flex-1']">
        <component
          :is="item.to ? 'RouterLink' : 'button'"
          v-bind="
            item.to ? { to: item.to } : { type: 'button', 'aria-pressed': item.key === current }
          "
          class="relative flex h-full w-full items-center gap-2 rounded-t px-3 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          :class="[
            size === 'lg'
              ? 'justify-center px-2 pb-4 text-h1-title whitespace-nowrap'
              : 'pb-4 text-header whitespace-nowrap',
            item.key === current
              ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-1 after:h-1.5 after:bg-foreground'
              : 'text-muted-foreground hover:text-foreground',
            size === 'lg' && (item.key === current ? 'font-bold' : 'font-normal'),
          ]"
          :aria-current="item.to && item.key === current ? 'page' : undefined"
          @click="item.to ? undefined : (current = item.key)"
        >
          {{ item.label }}
          <CountBadge v-if="item.count !== undefined" :count="item.count" />
        </component>
      </li>
    </ul>
  </nav>
</template>
