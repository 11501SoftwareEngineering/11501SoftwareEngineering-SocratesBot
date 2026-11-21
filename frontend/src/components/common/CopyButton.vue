<script setup lang="ts">
/**
 * 複製按鈕（只有圖示）。對應 Figma 元件頁「Copy」（node 699:2194）：
 *   預設文字主色的複製圖示，滑過變文字輔色，複製完成換成 ✓（Check_ring）2 秒。
 *
 * 用法：<CopyButton :text="course.invite_code" :label="t('course.copyCode')" :done-label="t('course.codeCopied')" />
 */
import { ref } from 'vue'
import { CheckRingIcon, CopyHoverIcon, CopyIcon } from '@/components/icons'

const props = defineProps<{ text: string; label: string; doneLabel: string }>()
const emit = defineEmits<{ copied: [] }>()
const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
  } catch {
    return // 瀏覽器不允許存取剪貼簿（例如不是 https）：維持原狀
  }
  copied.value = true
  emit('copied')
  clearTimeout(timer)
  timer = setTimeout(() => (copied.value = false), 2000)
}
</script>

<template>
  <button
    type="button"
    class="group inline-flex size-6 shrink-0 items-center justify-center rounded outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    :aria-label="copied ? doneLabel : label"
    @click="copy"
  >
    <CheckRingIcon v-if="copied" />
    <template v-else>
      <CopyIcon class="group-hover:hidden" />
      <CopyHoverIcon class="hidden group-hover:block" />
    </template>
    <span class="sr-only" aria-live="polite">{{ copied ? doneLabel : '' }}</span>
  </button>
</template>
