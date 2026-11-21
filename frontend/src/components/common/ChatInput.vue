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
 * - 按 Enter 送出；內容是空白、送出中、或沒有剩餘回合時不能送出
 */
import { computed } from 'vue'
import { MicIcon, SendIcon } from '@/components/icons'

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
    placeholder: '輸入回答...',
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

function handleSend() {
  if (!canSend.value) return
  emit('send', draft.value.trim())
}
</script>

<template>
  <div class="flex w-full justify-center border-t border-secondary bg-background px-4 py-3">
    <div class="flex w-full max-w-[870px] items-center gap-4">
      <form
        class="flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-secondary bg-card px-3 py-2 focus-within:ring-[3px] focus-within:ring-ring/50"
        @submit.prevent="handleSend"
      >
        <button
          v-if="showMic"
          type="button"
          :aria-label="recording ? '停止語音輸入' : '語音輸入'"
          :aria-pressed="recording"
          :disabled="disabled || outOfRounds"
          class="flex size-8 shrink-0 items-center justify-center rounded-full outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
          :class="recording && 'animate-pulse bg-destructive hover:bg-destructive'"
          @click="emit('mic')"
        >
          <MicIcon class="size-4" />
        </button>
        <input
          v-model="draft"
          aria-label="輸入回答"
          :placeholder="
            outOfRounds ? '回合數已用完' : recording ? '請說話…再按一次麥克風結束' : placeholder
          "
          :disabled="disabled || outOfRounds"
          :readonly="recording"
          class="min-w-0 flex-1 bg-transparent text-body-lg text-foreground outline-none placeholder:text-foreground/50 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          aria-label="送出"
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
        <span class="sr-only sm:not-sr-only">剩餘回合數：</span>{{ remaining }}/{{ total }}
      </div>
    </div>
  </div>
</template>
