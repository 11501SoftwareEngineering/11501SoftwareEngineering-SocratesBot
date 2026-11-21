<script setup lang="ts">
/**
 * 課程卡片。對應 Figma 學生首頁（P05）、老師首頁（P09）的課程卡：
 *   第一行：課程名稱（20px）＋課程代碼（小字），右邊「進入課程↗」
 *   第二行：課程描述
 *   第三行：老師名稱（學生看）、👥 學生人數、💬 活動數；右邊放按鈕（編輯、刪除、退出）
 * 整張卡片都可以點進課程。
 */
import type { RouteLocationRaw } from 'vue-router'
import type { CourseSummary } from '@/api/courses'
import CardLink from '@/components/common/CardLink.vue'
import { ChatIcon, GroupIcon } from '@/components/icons'
import { cardClass } from '@/lib/ui'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  course: CourseSummary
  to: RouteLocationRaw
  /** 學生看的卡片顯示老師名稱 */
  showTeacher?: boolean
}>()
</script>

<template>
  <article :class="[cardClass, 'relative flex flex-col gap-2 p-4 hover:border-muted-foreground']">
    <div class="flex items-start justify-between gap-3">
      <div class="flex min-w-0 items-baseline gap-3">
        <h3 class="truncate font-heading text-h2-title text-foreground" :title="course.name">
          {{ course.name }}
        </h3>
        <span class="shrink-0 text-body text-muted-foreground">{{ course.invite_code }}</span>
      </div>
      <CardLink :to="to" stretched :aria-label="t('courses.enterAria', { name: course.name })">{{
        t('courses.enter')
      }}</CardLink>
    </div>
    <p class="truncate text-body-lg text-muted-foreground" :title="course.description ?? ''">
      {{ course.description || t('courses.noDescription') }}
    </p>
    <div class="flex items-center justify-between gap-3">
      <ul class="flex items-center gap-4 text-body-lg text-foreground">
        <li v-if="showTeacher">{{ course.teacher_name }}</li>
        <li v-if="course.student_count != null" class="flex items-center gap-1">
          <GroupIcon /><span class="sr-only">{{ t('courses.students') }}</span
          >{{ course.student_count }}
        </li>
        <li class="flex items-center gap-1">
          <ChatIcon /><span class="sr-only">{{ t('courses.activities') }}</span
          >{{ course.topic_count }}
        </li>
      </ul>
      <div v-if="$slots.actions" class="relative z-10 flex items-center gap-1">
        <slot name="actions" />
      </div>
    </div>
  </article>
</template>
