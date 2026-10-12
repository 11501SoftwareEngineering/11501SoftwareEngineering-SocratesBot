<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useStudentCourse } from '@/composables/useStudentCourse'
import { useAuthStore, type UserRole } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const queryClient = useQueryClient()
const isStudent = computed(() => authStore.isAuthenticated && authStore.userRole === 'STUDENT')
const courseId = computed(() => {
  if (!isStudent.value) return ''
  const value = route.params.courseId ?? route.query.courseId
  return typeof value === 'string' ? value : ''
})
const { data: course } = useStudentCourse(courseId)
const roleLabels: Record<UserRole, string> = { STUDENT: '學生', TEACHER: '老師', ADMIN: '管理員' }

function handleLogout() {
  queryClient.removeQueries({ queryKey: ['student'] })
  authStore.logout()
}
</script>

<template>
  <header
    class="shrink-0 w-full bg-primary px-3 shadow-elevated sm:px-4"
    :class="
      isStudent
        ? 'grid min-h-site-header grid-cols-2 gap-y-3 py-3 lg:h-site-header lg:grid-cols-[1fr_auto_1fr] lg:gap-y-0 lg:py-0'
        : 'flex h-site-header items-center justify-between'
    "
  >
    <RouterLink to="/" class="flex w-fit items-center gap-2.5 self-center">
      <span aria-hidden="true" class="size-site-logo shrink-0 rounded-md bg-background" />
      <span class="whitespace-nowrap font-heading text-h1-title text-primary-foreground"
        >問導魷</span
      >
    </RouterLink>

    <nav
      v-if="isStudent"
      aria-label="學生課程導覽"
      class="col-span-2 row-start-2 flex min-w-0 items-center justify-center gap-8 lg:col-span-1 lg:col-start-2 lg:row-start-1"
    >
      <RouterLink
        :to="{ name: 'StudentCourses' }"
        class="shrink-0 rounded-md text-header text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >我的課程</RouterLink
      >
      <RouterLink
        v-if="courseId"
        :to="{ name: 'StudentCourse', params: { courseId } }"
        :title="course?.name"
        class="min-w-0 max-w-60 truncate rounded-md text-header text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >{{ course?.name ?? '課程' }}</RouterLink
      >
    </nav>

    <div
      v-if="authStore.isAuthenticated"
      class="flex min-w-0 items-center justify-end gap-2.5 self-center"
    >
      <div class="min-w-0 max-w-account text-right text-body-lg text-muted-foreground">
        <p class="truncate" :title="authStore.user?.name">
          {{ authStore.user?.name || authStore.user?.email }}
        </p>
        <p>{{ authStore.userRole ? roleLabels[authStore.userRole] : '' }}</p>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <button
            type="button"
            aria-label="開啟帳號選單"
            class="size-site-logo shrink-0 rounded-full bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          class="w-40 rounded-lg border border-border bg-card shadow-elevated"
        >
          <DropdownMenuItem
            class="cursor-pointer text-body focus:bg-muted focus:text-foreground"
            @select="handleLogout"
            >登出</DropdownMenuItem
          >
        </DropdownMenuContent>
      </DropdownMenu>
    </div>

    <div v-else class="flex items-center gap-0">
      <!-- Registration will link to its page once that route is available. -->
      <Button
        variant="ghost"
        size="sm"
        class="h-navigation min-h-0 rounded-lg border-0 px-3 py-1.5 text-header"
        >註冊</Button
      >
      <Button
        as-child
        variant="secondary"
        size="sm"
        class="h-navigation min-h-0 rounded-lg border-0 px-4 py-1.5 text-header"
      >
        <RouterLink to="/login">登入</RouterLink>
      </Button>
    </div>
  </header>
</template>
