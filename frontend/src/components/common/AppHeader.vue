<script setup lang="ts">
/**
 * 頁首。對應 Figma 元件頁「Header」（node 206:1422）的四種樣子：
 *   未登入：右邊「註冊」「登入」
 *   管理員：中間「管理帳號」
 *   老師／學生：中間「我的課程」，進到課程裡再多一個「課程名稱」
 *   右邊是帳號資訊，點頭像打開選單（修改密碼、登出）
 * 手機版（Figma「手機」頁）：只留魷魚圖示，導覽收進中間的 ☰ 選單。
 */
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, type RouteLocationRaw } from 'vue-router'
import { ROLE_LABELS } from '@/api/auth'
import AccountBadge from '@/components/common/AccountBadge.vue'
import AppLogo from '@/components/common/AppLogo.vue'
import { MenuIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useStudentCourse, useTeacherCourse } from '@/composables/useCourseDetail'
import { usePasswordDialog } from '@/composables/usePasswordDialog'
import { HOME_ROUTE, useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const passwordDialog = usePasswordDialog()
const menuOpen = ref(false)

watch(
  () => route.fullPath,
  () => (menuOpen.value = false),
)

const role = computed(() => (authStore.isAuthenticated ? authStore.userRole : null))
const courseId = computed(() => {
  const value = route.params.courseId
  return typeof value === 'string' ? value : ''
})

const { data: studentCourse } = useStudentCourse(() =>
  role.value === 'STUDENT' ? courseId.value : '',
)
const { data: teacherCourse } = useTeacherCourse(() =>
  role.value === 'TEACHER' ? courseId.value : '',
)

interface NavItem {
  label: string
  to: RouteLocationRaw
}

const navItems = computed<NavItem[]>(() => {
  if (role.value === 'SUPER_ADMIN') return [{ label: '管理帳號', to: { name: 'AdminTeachers' } }]
  if (role.value === 'STUDENT' || role.value === 'TEACHER') {
    const items: NavItem[] = [{ label: '我的課程', to: { name: HOME_ROUTE[role.value] } }]
    if (courseId.value) {
      const name = role.value === 'STUDENT' ? studentCourse.value?.name : teacherCourse.value?.name
      items.push({
        label: name ?? '課程',
        to: {
          name: role.value === 'STUDENT' ? 'StudentCourse' : 'TeacherCourse',
          params: { courseId: courseId.value },
        },
      })
    }
    return items
  }
  return []
})

const homeLink = computed<RouteLocationRaw>(() =>
  role.value ? { name: HOME_ROUTE[role.value] } : { name: 'Home' },
)
</script>

<template>
  <header class="relative z-40 shrink-0 bg-primary shadow-elevated">
    <div class="grid h-site-header grid-cols-[1fr_auto_1fr] items-center gap-4 px-3 sm:px-4">
      <RouterLink
        :to="homeLink"
        class="flex w-fit items-center gap-2.5 rounded-lg outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <AppLogo :size="42" class="rounded-md" />
        <span class="hidden whitespace-nowrap font-heading text-h1-title text-foreground sm:inline"
          >問導魷</span
        >
      </RouterLink>

      <!-- 電腦版導覽 -->
      <nav v-if="navItems.length" aria-label="主要導覽" class="hidden min-w-0 lg:block">
        <ul class="flex items-center gap-8">
          <li v-for="item in navItems" :key="item.label" class="min-w-0">
            <RouterLink
              :to="item.to"
              :title="item.label"
              class="block max-w-60 truncate rounded-md text-header text-foreground outline-none hover:text-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >{{ item.label }}</RouterLink
            >
          </li>
        </ul>
      </nav>
      <!-- 手機版：☰ 打開導覽 -->
      <button
        v-if="navItems.length"
        type="button"
        class="flex size-10 items-center justify-center rounded-lg outline-none hover:bg-foreground/10 focus-visible:ring-[3px] focus-visible:ring-ring/50 lg:hidden"
        :aria-expanded="menuOpen"
        aria-controls="mobile-nav"
        :aria-label="menuOpen ? '關閉選單' : '開啟選單'"
        @click="menuOpen = !menuOpen"
      >
        <MenuIcon class="size-6" />
      </button>
      <span v-else />

      <div class="flex min-w-0 justify-end">
        <DropdownMenu v-if="authStore.user">
          <DropdownMenuTrigger
            class="min-w-0 rounded-full outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            aria-label="開啟帳號選單"
          >
            <AccountBadge
              :name="authStore.user.name"
              :role-label="ROLE_LABELS[authStore.user.role]"
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            class="w-44 rounded-lg border border-border bg-card p-1 shadow-elevated"
          >
            <DropdownMenuItem
              class="cursor-pointer px-3 py-2 text-body-lg focus:bg-muted focus:text-foreground"
              @select="passwordDialog.open()"
              >修改密碼</DropdownMenuItem
            >
            <DropdownMenuItem
              class="cursor-pointer px-3 py-2 text-body-lg focus:bg-muted focus:text-foreground"
              @select="authStore.logout()"
              >登出</DropdownMenuItem
            >
          </DropdownMenuContent>
        </DropdownMenu>

        <div v-else class="flex items-center gap-1">
          <Button as-child variant="ghost">
            <RouterLink :to="{ name: 'Register' }">註冊</RouterLink>
          </Button>
          <Button as-child variant="secondary">
            <RouterLink :to="{ name: 'Login' }">登入</RouterLink>
          </Button>
        </div>
      </div>
    </div>

    <!-- 手機版展開的導覽（Figma 手機版 Group 13） -->
    <nav
      v-if="menuOpen && navItems.length"
      id="mobile-nav"
      aria-label="主要導覽"
      class="absolute inset-x-0 top-full bg-secondary shadow-elevated lg:hidden"
    >
      <ul class="mx-auto max-w-md divide-y divide-muted-foreground/60 px-8">
        <li v-for="item in navItems" :key="item.label">
          <RouterLink
            :to="item.to"
            class="block truncate py-3 text-center text-header text-muted-foreground outline-none hover:text-foreground focus-visible:text-foreground focus-visible:underline"
            >{{ item.label }}</RouterLink
          >
        </li>
      </ul>
    </nav>
  </header>
</template>
