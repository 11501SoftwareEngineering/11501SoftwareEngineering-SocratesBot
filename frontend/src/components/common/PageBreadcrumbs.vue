<script setup lang="ts">
/**
 * 麵包屑：「我的課程 / 課程名稱 /」。對應 Figma 元件頁「TOP」（node 1169:3313）的 Header：
 * 每一項是文字連結元件（TextLink，底線），後面都有「/」（包含最後一項），項目之間 10px。
 *
 * 用法：
 *   <PageBreadcrumbs :items="[{ label: '我的課程', to: { name: 'StudentCourses' } }, { label: '公民思辨' }]" />
 */
import type { RouteLocationRaw } from 'vue-router'
import { useI18n } from 'vue-i18n'
import TextLink from '@/components/common/TextLink.vue'

const { t } = useI18n()

defineProps<{
  items: { label: string; to?: RouteLocationRaw }[]
}>()
</script>

<template>
  <nav :aria-label="t('common.breadcrumb')">
    <ol class="flex flex-wrap items-center gap-2.5 text-header text-muted-foreground">
      <li v-for="(item, i) in items" :key="i" class="flex items-center gap-2.5">
        <TextLink v-if="item.to" :to="item.to">{{ item.label }}</TextLink>
        <span v-else>{{ item.label }}</span>
        <span aria-hidden="true">/</span>
      </li>
    </ol>
  </nav>
</template>
