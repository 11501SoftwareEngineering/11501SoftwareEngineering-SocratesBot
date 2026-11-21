<script setup lang="ts">
/**
 * 頁首。對應 Figma「Header/Course」（例如 P10-1 的 node 206:1572）：
 *   左邊：魷魚圖示＋「問導魷」（回首頁）
 *   右邊：介面語言（正體中文）、帳號（名稱／身分／頭像）
 *         帳號選單：助教「學生課程」、老師「AI 用量與金鑰」、修改密碼、登出
 *   沒登入：語言、「註冊」「登入」
 * 照 Figma 頁首不放導覽：Logo 回自己的首頁，頁內用麵包屑回上一層；
 * 助教切到學生課程、老師的 AI 用量與金鑰放在帳號選單（Prototype 的帳號選單也有這兩項）。
 */
import { computed } from 'vue'
import { RouterLink, useRoute, type RouteLocationRaw } from 'vue-router'
import { ROLE_LABELS } from '@/api/auth'
import AccountBadge from '@/components/common/AccountBadge.vue'
import AppLogo from '@/components/common/AppLogo.vue'
import LanguageSwitcher from '@/components/common/LanguageSwitcher.vue'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { usePasswordDialog } from '@/composables/usePasswordDialog'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()
const passwordDialog = usePasswordDialog()

const role = computed(() => (authStore.isAuthenticated ? authStore.userRole : null))
const isTa = computed(() => role.value === 'STUDENT' && authStore.hasTaAssignments)
const homeLink = computed<RouteLocationRaw>(() =>
  role.value ? { name: authStore.homeRoute } : { name: 'Home' },
)

/** 助教在教學端頁面顯示「助教」，在學生頁面顯示「學生」 */
const roleLabel = computed(() =>
  authStore.user?.role === 'STUDENT' && route.meta.teaching
    ? '助教'
    : ROLE_LABELS[authStore.user?.role ?? 'STUDENT'],
)
const menuItemClass = 'cursor-pointer px-3 py-2 text-body-lg focus:bg-muted focus:text-foreground'
</script>

<template>
  <header class="relative z-40 shrink-0 bg-primary shadow-elevated">
    <div class="flex h-site-header items-center gap-3 px-3 sm:px-4">
      <RouterLink
        :to="homeLink"
        class="flex w-fit items-center gap-2.5 rounded-lg outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <AppLogo :size="42" class="rounded-md" />
        <span class="whitespace-nowrap font-heading text-h1-title text-foreground max-sm:hidden"
          >問導魷</span
        >
      </RouterLink>

      <div class="flex min-w-0 flex-1 items-center justify-end gap-3">
        <LanguageSwitcher />

        <DropdownMenu v-if="authStore.user">
          <DropdownMenuTrigger
            class="min-w-0 rounded-full outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            aria-label="開啟帳號選單"
          >
            <AccountBadge :name="authStore.user.name" :role-label="roleLabel" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            class="w-44 rounded-lg border border-border bg-card p-1 shadow-elevated"
          >
            <DropdownMenuItem v-if="isTa" as-child :class="menuItemClass">
              <RouterLink :to="{ name: 'StudentCourses' }">學生課程</RouterLink>
            </DropdownMenuItem>
            <DropdownMenuItem v-if="role === 'TEACHER'" as-child :class="menuItemClass">
              <RouterLink :to="{ name: 'TeacherAiSettings' }">AI 用量與金鑰</RouterLink>
            </DropdownMenuItem>
            <DropdownMenuItem :class="menuItemClass" @select="passwordDialog.open()"
              >修改密碼</DropdownMenuItem
            >
            <DropdownMenuItem :class="menuItemClass" @select="authStore.logout()"
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
  </header>
</template>
