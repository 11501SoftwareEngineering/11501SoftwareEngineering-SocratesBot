<script setup lang="ts">
/**
 * 還沒做好的頁面先放這個（「製作中」）。
 * 路由一次設定好、各頁面先用這個佔位，之後各頁面的 PR 只需要改自己的檔案，不會互相衝突。
 *
 * 用法：<PagePlaceholder name="老師問題頁面" :issue="65" />
 */
import ComingSoon from '@/components/common/ComingSoon.vue'

defineProps<{
  /** 頁面名稱，例如「老師問題頁面」 */
  name: string
  /** 負責實作這個頁面的 issue 編號 */
  issue?: number
}>()
</script>

<template>
  <div class="mx-auto w-full max-w-[870px] px-4 py-12">
    <ComingSoon :title="`${name}製作中`">
      這個頁面還在開發，請稍後再來看看。
      <template v-if="issue">（issue #{{ issue }}）</template>
    </ComingSoon>
  </div>
</template>
