<script setup lang="ts">
/**
 * 文字連結。對應 Figma 元件頁「忘記密碼?」（node 66:123）：22px、底線；
 * 預設文字輔色，滑過變文字主色。麵包屑、課程列表的空狀態都用這個。
 * 滑過另外加一層底色（Foundations「圖形外框」#EBE9E1，圓角 radius/8），讓可以點的範圍更明顯。
 *
 * 用法：
 *   <TextLink :to="{ name: 'StudentCourses' }">我的課程</TextLink>   （站內連結）
 *   <TextLink @click="…">說明</TextLink>                             （沒有 to 就是按鈕）
 *   <TextLink inline @click="…">新增課程</TextLink>                  （在句子裡：字級、顏色跟著句子）
 */
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

const props = defineProps<{ to?: RouteLocationRaw; inline?: boolean }>()

const linkClass = computed(() => [
  '-mx-1 rounded-lg px-1 underline decoration-from-font underline-offset-4 outline-none transition-colors hover:bg-border focus-visible:ring-[3px] focus-visible:ring-ring/50',
  props.inline
    ? 'hover:text-muted-foreground'
    : 'text-header text-muted-foreground hover:text-foreground',
])
</script>

<template>
  <RouterLink v-if="to" :to="to" :class="linkClass"><slot /></RouterLink>
  <button v-else type="button" :class="linkClass"><slot /></button>
</template>
