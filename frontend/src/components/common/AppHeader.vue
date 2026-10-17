<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <header
    class="flex h-site-header shrink-0 w-full items-center justify-between bg-primary px-3 shadow-elevated sm:px-4"
  >
    <RouterLink to="/" class="flex items-center gap-2.5">
      <span aria-hidden="true" class="size-site-logo shrink-0 rounded-md bg-background" />
      <span class="font-heading text-h1-title text-primary-foreground">問導魷</span>
    </RouterLink>

    <div v-if="authStore.isAuthenticated" class="flex items-center gap-3">
      <span class="text-sm text-primary-foreground">{{ authStore.user?.name }}</span>
      <span class="rounded-full bg-background/60 px-2 py-0.5 text-xs text-foreground">
        {{ authStore.userRole }}
      </span>
      <Button
        variant="secondary"
        size="sm"
        class="h-navigation min-h-0 rounded-lg border-0 px-4 py-1.5 text-header"
        @click="authStore.logout()"
      >
        登出
      </Button>
    </div>

    <div v-else class="flex items-center gap-0">
      <!-- TODO(前端組): 目前還沒有 /register 頁面與路由，先用一般按鈕佔位，
           等註冊頁做好之後，改成 <Button as-child><RouterLink to="/register">。 -->
      <Button
        variant="ghost"
        size="sm"
        class="h-navigation min-h-0 rounded-lg border-0 px-3 py-1.5 text-header"
      >
        註冊
      </Button>
      <Button
        as-child
        variant="secondary"
        size="sm"
        class="h-navigation min-h-0 rounded-lg border-0 px-4 py-1.5 text-header"
      >
        <RouterLink to="/login"> 登入 </RouterLink>
      </Button>
    </div>
  </header>
</template>
