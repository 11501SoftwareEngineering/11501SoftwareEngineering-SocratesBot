<script setup lang="ts">
/**
 * 頁面上方：麵包屑 → 大標題（40px）→ 說明。對應 Figma 各頁的「TOP」區塊。
 *
 * 用法：
 *   <PageTitle :breadcrumbs="[{ label: '我的課程', to: { name: 'StudentCourses' } }]" title="哲學概論"
 *     description="從日常問題出發…">
 *     <template #after-title>（標題右邊的東西，例如課程代碼、草稿標籤）</template>
 *   </PageTitle>
 */
import type { RouteLocationRaw } from 'vue-router'
import PageBreadcrumbs from '@/components/common/PageBreadcrumbs.vue'

defineProps<{
  title: string
  breadcrumbs?: { label: string; to?: RouteLocationRaw }[]
  description?: string | null
}>()
</script>

<template>
  <header class="flex flex-col gap-2">
    <PageBreadcrumbs v-if="breadcrumbs?.length" :items="breadcrumbs" />
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
      <h1 class="text-page-title text-foreground">{{ title }}</h1>
      <slot name="after-title" />
    </div>
    <p v-if="description" class="text-header text-muted-foreground">{{ description }}</p>
  </header>
</template>
