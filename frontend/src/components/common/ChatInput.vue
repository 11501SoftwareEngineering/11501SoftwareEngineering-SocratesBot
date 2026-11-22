<script setup lang="ts">
/**
 * 對話輸入列（對話頁最下方）。對應 Figma 元件頁「輸入對話」（node 229:732）。
 *   白色輸入框：左邊麥克風、右邊送出；最右邊顯示剩餘回合數
 *
 * 用法：
 *   <ChatInput v-model="draft" :remaining="3" :total="5" :sending="isStreaming"
 *     :show-mic="speech.supported" :recording="speech.isListening.value"
 *     @send="handleSend" @mic="speech.toggle()" />
 *
 * - 像 Discord／Claude 一樣的多行輸入：Enter 送出、Shift+Enter 換行，輸入框隨內容長高（最多約 8 行，再多就捲動）
 *   - 中文、日文輸入法選字時按的 Enter 只是確定選字，不會送出
 *   - 手機（觸控螢幕）上 Enter 是換行，用右邊的送出按鈕送出（跟 Discord、Claude 的手機版一樣）
 * - 內容是空白、送出中、或沒有剩餘回合時不能送出
 * - 最多 6000 字（後端 StreamMessageRequest 的上限）
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { MicIcon, SendIcon } from '@/components/icons'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    remaining?: number
    total?: number
    sending?: boolean
    disabled?: boolean
    placeholder?: string
    /** 正在聽（語音輸入中）：麥克風按鈕變色，輸入框暫時不能打字，文字由語音辨識填入 */
    recording?: boolean
    /** 顯示麥克風按鈕（瀏覽器不支援語音辨識時關掉） */
    showMic?: boolean
  }>(),
  {
    sending: false,
    disabled: false,
    recording: false,
    showMic: true,
  },
)

const emit = defineEmits<{ send: [text: string]; mic: [] }>()
const draft = defineModel<string>({ default: '' })

const outOfRounds = computed(() => props.remaining !== undefined && props.remaining <= 0)
const canSend = computed(
  () => !!draft.value.trim() && !props.sending && !props.disabled && !outOfRounds.value,
)

/** 後端一則回答最多 6000 字 */
const MAX_LENGTH = 6000

function handleSend() {
  if (!canSend.value) return
  emit('send', draft.value.trim())
}

const textarea = ref<HTMLTextAreaElement>()
const isTouch = typeof window !== 'undefined' && !!window.matchMedia?.('(pointer: coarse)').matches

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || isTouch) return
  // 輸入法選字中（keyCode 229 是 Safari 的情況）
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  handleSend()
}

/** 依內容調整高度：先縮回再量 scrollHeight，最高由 CSS 的 max-h 限制 */
function resize() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}
// 送出後清空、語音輸入填入文字時也要調整
watch(draft, () => void nextTick(resize))
onMounted(resize)
</script>

<template>
  <div class="flex w-full justify-center border-t border-secondary bg-background px-4 py-3">
    <div class="flex w-full max-w-[870px] items-end gap-4">
      <form
        class="flex min-w-0 flex-1 items-end gap-2 rounded-2xl border border-secondary bg-card px-3 py-2 focus-within:ring-[3px] focus-within:ring-ring/50"
        @submit.prevent="handleSend"
      >
        <button
          v-if="showMic"
          type="button"
          :aria-label="recording ? t('chat.stopVoice') : t('chat.voice')"
          :aria-pressed="recording"
          :disabled="disabled || outOfRounds"
          class="flex size-8 shrink-0 items-center justify-center rounded-full outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
          :class="recording && 'animate-pulse bg-destructive hover:bg-destructive'"
          @click="emit('mic')"
        >
          <MicIcon class="size-4" />
        </button>
        <textarea
          ref="textarea"
          v-model="draft"
          rows="1"
          :maxlength="MAX_LENGTH"
          :aria-label="t('chat.inputLabel')"
          :placeholder="
            outOfRounds
              ? t('chat.outOfTurns')
              : recording
                ? t('chat.listening')
                : (placeholder ?? t('chat.placeholder'))
          "
          :disabled="disabled || outOfRounds"
          :readonly="recording"
          enterkeyhint="send"
          class="max-h-52 min-w-0 flex-1 resize-none self-center bg-transparent py-1 text-body-lg text-foreground outline-none placeholder:text-foreground/50 disabled:cursor-not-allowed"
          @keydown="onKeydown"
        />
        <button
          type="submit"
          :aria-label="t('chat.send')"
          :disabled="!canSend"
          class="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary outline-none hover:brightness-[0.8] focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
        >
          <SendIcon class="size-3.5" />
        </button>
      </form>

      <div
        v-if="remaining !== undefined && total !== undefined"
        class="shrink-0 rounded-2xl border border-secondary bg-secondary px-3 py-2 text-h2-title text-foreground/50"
        aria-live="polite"
      >
        <span class="sr-only sm:not-sr-only">{{ t('chat.remaining') }}</span
        >{{ remaining }}/{{ total }}
      </div>
    </div>
  </div>
</template>
