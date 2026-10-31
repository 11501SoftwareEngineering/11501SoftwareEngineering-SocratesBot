<script setup lang="ts">
/**
 * 「功能尚未開放」提示卡。後端還沒做好的功能（見 src/config/features.ts）放在原本的位置，
 * 讓使用者知道這裡之後會有東西，而不是以為壞掉了。
 *
 * 用法：<ComingSoon title="AI 對話尚未開放">完成後就能在這裡跟導魷討論。</ComingSoon>
 */
import { Clock } from '@lucide/vue'

defineProps<{ title: string }>()
</script>

<template>
  <div
    role="status"
    class="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-muted-foreground/40 bg-card/60 px-6 py-10 text-center"
  >
    <Clock class="size-10 text-muted-foreground" aria-hidden="true" />
    <p class="text-h2-title leading-normal text-foreground">{{ title }}</p>
    <p v-if="$slots.default" class="max-w-md text-body text-muted-foreground"><slot /></p>
  </div>
</template>
