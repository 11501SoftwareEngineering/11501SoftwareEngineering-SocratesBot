<script setup lang="ts">
/**
 * 麵包屑：「我的課程 / 課程名稱 /」。對應 Figma 各頁最上方的 TOP > Header。
 * Figma 每一項後面都有「/」（包含最後一項），下面接頁面大標題。
 *
 * 用法：
 *   <PageBreadcrumbs :items="[{ label: '我的課程', to: { name: 'StudentCourses' } }, { label: '公民思辨' }]" />
 */
import type { RouteLocationRaw } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  items: { label: string; to?: RouteLocationRaw }[]
}>()
</script>

<template>
  <nav :aria-label="t('common.breadcrumb')">
    <ol class="flex flex-wrap items-center gap-2.5 text-header text-muted-foreground">
      <li v-for="(item, i) in items" :key="i" class="flex items-center gap-2.5">
        <RouterLink
          v-if="item.to"
          :to="item.to"
          class="rounded outline-none underline-offset-4 hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >{{ item.label }}</RouterLink
        >
        <span v-else>{{ item.label }}</span>
        <span aria-hidden="true">/</span>
      </li>
    </ol>
  </nav>
</template>
