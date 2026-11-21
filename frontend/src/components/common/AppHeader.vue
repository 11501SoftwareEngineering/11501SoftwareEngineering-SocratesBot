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
import { roleLabel as labelOf } from '@/api/auth'
import AccountBadge from '@/components/common/AccountBadge.vue'
import AppLogo from '@/components/common/AppLogo.vue'
import LanguageSwitcher from '@/components/common/LanguageSwitcher.vue'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { usePasswordDialog } from '@/composables/usePasswordDialog'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const route = useRoute()
const authStore = useAuthStore()
const passwordDialog = usePasswordDialog()

const role = computed(() => (authStore.isAuthenticated ? authStore.userRole : null))
const isTa = computed(() => role.value === 'STUDENT' && authStore.hasTaAssignments)

/** 帳戶選單：助教多「學生課程」、老師多「AI 用量與金鑰」，最後是修改密碼、登出 */
const menuItems = computed(
  () =>
    [
      isTa.value && {
        key: 'student',
        label: t('header.studentCourses'),
        to: { name: 'StudentCourses' } as RouteLocationRaw,
      },
      role.value === 'TEACHER' && {
        key: 'ai',
        label: t('header.aiSettings'),
        to: { name: 'TeacherAiSettings' } as RouteLocationRaw,
      },
      { key: 'password', label: t('header.password.change'), action: () => passwordDialog.open() },
      { key: 'logout', label: t('header.logout'), action: () => authStore.logout() },
    ].filter(Boolean) as {
      key: string
      label: string
      to?: RouteLocationRaw
      action?: () => void
    }[],
)
const homeLink = computed<RouteLocationRaw>(() =>
  role.value ? { name: authStore.homeRoute } : { name: 'Home' },
)

/** 助教在教學端頁面顯示「助教」，在學生頁面顯示「學生」 */
const roleLabel = computed(() =>
  authStore.user?.role === 'STUDENT' && route.meta.teaching
    ? t('roles.TA')
    : labelOf(authStore.user?.role ?? 'STUDENT'),
)
// Figma「帳戶」展開（node 704:2546）：圖形外框底色、圓角 16、內距 8；每一項是 Text 按鈕（Secondary）：
// 20px 文字輔色置中，滑過變文字主色；項目之間有分隔線
const menuItemClass =
  'cursor-pointer justify-center rounded-lg px-1 py-1.5 text-center font-heading text-h2-title text-muted-foreground outline-none focus:bg-transparent focus:text-foreground data-[highlighted]:text-foreground'
</script>

<template>
  <header class="relative z-40 shrink-0 bg-primary shadow-elevated">
    <div class="flex h-site-header items-center gap-3 px-3 sm:px-4">
      <RouterLink
        :to="homeLink"
        class="flex w-fit items-center gap-2.5 rounded-lg outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <AppLogo :size="42" class="rounded-md" />
        <span class="whitespace-nowrap font-heading text-h1-title text-foreground max-sm:hidden">{{
          t('common.appName')
        }}</span>
      </RouterLink>

      <div class="flex min-w-0 flex-1 items-center justify-end gap-3">
        <LanguageSwitcher />

        <DropdownMenu v-if="authStore.user">
          <DropdownMenuTrigger
            class="min-w-0 rounded-full outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            :aria-label="t('header.openAccountMenu')"
          >
            <AccountBadge :name="authStore.user.name" :role-label="roleLabel" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            class="flex min-w-[136px] flex-col gap-1 rounded-2xl border-0 bg-border p-2 shadow-none"
          >
            <template v-for="(item, i) in menuItems" :key="item.key">
              <DropdownMenuSeparator v-if="i > 0" class="mx-0 my-0 h-px bg-muted-foreground/40" />
              <DropdownMenuItem v-if="item.to" as-child :class="menuItemClass">
                <RouterLink :to="item.to">{{ item.label }}</RouterLink>
              </DropdownMenuItem>
              <DropdownMenuItem v-else :class="menuItemClass" @select="item.action?.()">{{
                item.label
              }}</DropdownMenuItem>
            </template>
          </DropdownMenuContent>
        </DropdownMenu>

        <div v-else class="flex items-center gap-1">
          <Button as-child variant="ghost">
            <RouterLink :to="{ name: 'Register' }">{{ t('header.register') }}</RouterLink>
          </Button>
          <Button as-child variant="secondary">
            <RouterLink :to="{ name: 'Login' }">{{ t('header.login') }}</RouterLink>
          </Button>
        </div>
      </div>
    </div>
  </header>
</template>
