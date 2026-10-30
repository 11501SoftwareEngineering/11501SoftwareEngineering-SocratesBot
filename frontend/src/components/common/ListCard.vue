<script setup lang="ts">
/**
 * 列表卡片。對應 Figma 元件頁「Card_Course」（node 232:794）。
 *   左邊：標題（H4 20px）＋說明（Body1 18px）；右邊：0～2 個 Small 按鈕
 *   Expand=Yes：標題下方多一段展開內容（例如學生名單）
 *   Highlight=Yes：輔色底，用來標示目前選中的項目
 *   hover（可以點的卡片）：米白底＋文字輔色外框
 *
 * 用法：
 *   <ListCard title="帳號：wang" description="王老師">
 *     <template #actions>
 *       <Button variant="destructive">刪除 <TrashIcon /></Button>
 *     </template>
 *   </ListCard>
 *
 *   可以點的卡片（進入課程）：<ListCard title="哲學概論" :to="`/student/courses/${id}`" />
 *   可以展開的卡片：<ListCard v-model:expanded="open" expandable title="…"><template #details>…</template></ListCard>
 *
 * - 好幾項資訊用 meta 傳陣列：電腦版排成一行，手機版一項一行（Figma 手機版 Card_Course）
 *     <ListCard title="說謊一定是錯的嗎" :meta="['年齡層：13-15', '回合數：5', '已完成人數：3/12']" />
 * - 電腦版標題、說明太長會截斷成「…」（滑鼠移上去看得到完整文字）；手機版最多顯示兩行
 * - 手機寬度時按鈕留在右邊，兩顆按鈕時建議只顯示圖示（文字用 hidden sm:inline 藏起來，記得加 aria-label）
 */
import type { HTMLAttributes } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { cn } from '@/lib/utils'

const props = defineProps<{
  title: string
  description?: string
  /** 多項資訊（電腦版一行、手機版一項一行） */
  meta?: (string | false | null | undefined)[]
  /** 傳入後整張卡片變成連結 */
  to?: RouteLocationRaw
  /** 點卡片可以展開／收合 #details 的內容 */
  expandable?: boolean
  /** 目前選中（Figma Highlight=Yes） */
  highlight?: boolean
  class?: HTMLAttributes['class']
}>()

const expanded = defineModel<boolean>('expanded', { default: false })
const metaItems = computed(() => (props.meta ?? []).filter((m): m is string => !!m))
const showDetails = computed(() => expanded.value || !props.expandable)
const interactive = computed(() => !!props.to || props.expandable)
const titleTag = computed(() => (props.to ? RouterLink : props.expandable ? 'button' : 'p'))
const titleAttrs = computed(() => {
  if (props.to) return { to: props.to }
  if (props.expandable) {
    return {
      type: 'button',
      'aria-expanded': expanded.value,
      onClick: () => (expanded.value = !expanded.value),
    }
  }
  return {}
})
</script>

<template>
  <article
    :class="
      cn(
        'relative flex flex-row justify-between gap-3 rounded-2xl border border-border bg-card p-4 text-card-foreground shadow-elevated transition-colors sm:gap-4',
        $slots.details && showDetails ? 'items-start' : 'items-center',
        interactive &&
          'hover:border-[1.5px] hover:border-muted-foreground hover:bg-background focus-within:ring-[3px] focus-within:ring-ring/50',
        highlight &&
          'border-[1.5px] border-muted-foreground bg-secondary/80 hover:bg-secondary hover:brightness-[0.8]',
        props.class,
      )
    "
  >
    <div class="min-w-0 flex-1 py-[5px]">
      <component
        :is="titleTag"
        v-bind="titleAttrs"
        :title="title"
        class="block w-full text-left text-h2-title text-foreground outline-none max-sm:line-clamp-2 max-sm:break-words sm:truncate"
        :class="interactive && 'after:absolute after:inset-0 after:rounded-2xl'"
      >
        {{ title }}
      </component>
      <ul
        v-if="metaItems.length"
        class="mt-0.5 flex flex-col text-body-lg text-muted-foreground sm:flex-row sm:flex-wrap sm:gap-x-4"
      >
        <li v-for="item in metaItems" :key="item">{{ item }}</li>
      </ul>
      <p
        v-if="description || $slots.description"
        class="mt-0.5 text-body-lg text-muted-foreground max-sm:line-clamp-2 max-sm:break-words sm:truncate"
      >
        <slot name="description">{{ description }}</slot>
      </p>
      <div v-if="$slots.details && showDetails" class="mt-1 text-body-lg text-muted-foreground">
        <slot name="details" />
      </div>
    </div>

    <!-- relative z-10：整張卡片可以點的時候，按鈕仍然點得到 -->
    <div v-if="$slots.actions" class="relative z-10 flex shrink-0 items-center gap-2 sm:gap-4">
      <slot name="actions" />
    </div>
  </article>
</template>
