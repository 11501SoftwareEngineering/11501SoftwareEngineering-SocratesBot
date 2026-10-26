<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()

// 依據路由或角色顯示正中央導覽標題（對齊 Figma）
const centerTitle = computed(() => {
  if (route.path.startsWith('/admin') || authStore.userRole === 'ADMIN') {
    return '管理帳號'
  }
  if (route.path.startsWith('/teacher') || authStore.userRole === 'TEACHER') {
    return '我的課程'
  }
  if (route.path.startsWith('/student') || authStore.userRole === 'STUDENT') {
    return '我的課程'
  }
  return ''
})

// 右上角身分顯示文字
const roleDisplay = computed(() => {
  if (authStore.userRole === 'ADMIN') return '身分'
  if (authStore.userRole === 'TEACHER') return '老師'
  if (authStore.userRole === 'STUDENT') return '學生'
  return '身分'
})
</script>

<template>
  <header class="relative flex h-14 w-full items-center justify-between bg-primary px-4 shadow-sm">
    <!-- 左側：魷魚 LOGO + 問導魷 -->
    <RouterLink to="/" class="flex items-center gap-2.5">
      <span class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-background p-1 shadow-sm">
        <!-- Figma 問導魷 SVG Logo（依設計圖重構） -->
        <svg viewBox="0 0 64 64" fill="none" class="size-full">
          <!-- 外圈對話框（圓弧 + 右下角對話尖角） -->
          <path
            d="M19.3 37.7A18 18 0 1 1 46.6 35.5L50.2 44.5L40.5 40.8C38.8 41 37 41.8 35.5 42.8"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <!-- 魷魚頂部頭冠與兩側耳鰭 -->
          <path
            d="M22 23.2C19.2 23.2 18.5 21 20.2 19C23.2 15.5 28.5 12 32 12C35.5 12 40.8 15.5 43.8 19C45.5 21 44.8 23.2 42 23.2"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <!-- 左側臉部輪廓（由頭冠內側延伸至左臉頰） -->
          <path
            d="M24.5 18.5C22 22.5 20.5 26.5 20.8 30C21 33 22.8 35 24.8 35.5"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
          />
          <!-- 右側臉部輪廓延伸至中央主觸手（問號勾造型） -->
          <path
            d="M39.5 18.5C42 22.5 43.5 26.5 43.2 30C42.8 34 40 36.5 36.8 39C33.2 41.8 32 46.5 32 53C32 56.2 34.2 58 36.2 57.5C38.2 57 38.8 54.5 37.2 53C36.2 52.2 35.2 52.5 35 53"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <!-- 左一觸手（向左上捲曲） -->
          <path
            d="M26 34C24.5 37.5 21 40.2 17.8 40C15.5 39.8 14.2 38 14.2 35.5"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
          />
          <!-- 左二觸手（向左延伸微彎） -->
          <path
            d="M29.2 35.5C28 39.5 24.8 43.5 20.5 44.2C18.5 44.5 17 44.2 15.8 43.8"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
          />
          <!-- 左三觸手（向左下彎鉤） -->
          <path
            d="M32.5 34.2C32.2 39.5 28.5 44.5 26.2 49C25.2 51 22.5 51 21.5 49.2"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
          />
          <!-- 右側短觸手（向右下彎鉤） -->
          <path
            d="M39.8 41C40 44.5 40.8 47.8 42.2 49.5C43.5 50.8 45.2 50 46 48.2"
            stroke="hsl(var(--primary))"
            stroke-width="3"
            stroke-linecap="round"
          />
          <!-- 眼睛（與線條同色系） -->
          <circle cx="27.5" cy="27.5" r="2" fill="hsl(var(--primary))" />
          <circle cx="36.5" cy="27.5" r="2" fill="hsl(var(--primary))" />
          <!-- 腮紅 -->
          <ellipse cx="24.5" cy="30.8" rx="2.8" ry="1.5" fill="hsl(var(--destructive))" />
          <ellipse cx="39.5" cy="30.8" rx="2.8" ry="1.5" fill="hsl(var(--destructive))" />
        </svg>
      </span>
      <span class="font-heading text-header font-bold text-primary-foreground">問導魷</span>
    </RouterLink>

    <!-- 正中央：管理帳號（對齊 Figma 置中位置） -->
    <div
      v-if="authStore.isAuthenticated && centerTitle"
      class=" absolute left-1/2 -translate-x-1/2 text-h2-title font-medium text-primary-foreground"
    >
      {{ centerTitle }}
    </div>

    <!-- 右側：已登入顯示「帳戶名稱 / 身分」+ 白色圓形頭像 -->
    <div v-if="authStore.isAuthenticated" class="flex items-center gap-2.5">
      <div class="flex flex-col items-end leading-tight">
        <span class="text-body font-medium text-primary-foreground">
          {{ authStore.user?.name || '帳戶名稱' }}
        </span>
        <span class="text-body text-primary-foreground/80">
          {{ roleDisplay }}
        </span>
      </div>
      <button
        type="button"
        class="size-8 shrink-0 rounded-full bg-background shadow-sm transition hover:opacity-90"
        title="點擊登出"
        @click="authStore.logout()"
      />
    </div>

    <!-- 未登入狀態 -->
    <div v-else class="flex items-center gap-1.5">
      <Button variant="ghost" size="sm">
        註冊
      </Button>
      <Button as-child variant="secondary" size="sm">
        <RouterLink to="/login">
          登入
        </RouterLink>
      </Button>
    </div>
  </header>
</template>