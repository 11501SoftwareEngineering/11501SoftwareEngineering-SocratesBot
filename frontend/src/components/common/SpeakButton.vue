<script setup lang="ts">
/**
 * 朗讀按鈕（喇叭圖示）。對應 Figma 元件「sound_max」（node 788:4541）。
 * 用瀏覽器內建語音唸出 text；再按一次停止。瀏覽器不支援時不顯示。
 *
 * 用法：<SpeakButton id="m1" text="你覺得正義是什麼？" />
 */
import { onBeforeUnmount } from 'vue'
import { SoundIcon } from '@/components/icons'
import { useSpeech } from '@/composables/useSpeech'

const props = defineProps<{
  /** 用來分辨是哪一則在朗讀，例如 message_id */
  id: string
  text: string
}>()

const { supported, isSpeaking, toggle, stop } = useSpeech()

// 離開頁面時停止朗讀，不然換頁後還會一直唸
onBeforeUnmount(() => {
  if (isSpeaking(props.id)) stop()
})
</script>

<template>
  <button
    v-if="supported"
    type="button"
    class="rounded outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    :class="isSpeaking(props.id) && 'animate-pulse'"
    :aria-label="isSpeaking(props.id) ? '停止朗讀' : '朗讀這則訊息'"
    :aria-pressed="isSpeaking(props.id)"
    @click="toggle(props.id, props.text)"
  >
    <SoundIcon />
  </button>
</template>
