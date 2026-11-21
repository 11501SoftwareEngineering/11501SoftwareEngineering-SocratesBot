<script setup lang="ts">
/**
 * 多行文字欄位。對應 Figma 元件頁「Textarea」（node 758:2358）：
 *   head：標題 H4 20px，右邊可選的動作（↻ 圖示 20px + 16px 主色_深文字，例如「重新產生」）
 *   box：最小高 96、圓角 8、內距 16/12、背景色 #F7F6F2、外框 #EBE9E1、內陰影（凹陷）
 *     - Error：外框 1.5px 點綴色
 *     - Disabled（唯讀，例如已發布的活動）：外框輔色、沒有內陰影
 *   foot：左邊提示／錯誤文字（16px，錯誤用點綴色_深），右邊字數「0 / 6000」
 *
 * 用法：
 *   <LongTextField v-model="text" label="開場白" action-label="重新產生" @action="regenerate" />
 */
import { computed, useId } from 'vue'
import { RefreshIcon, SpinnerIcon } from '@/components/icons'

const props = defineProps<{
  label: string
  /** 標題只給螢幕閱讀器（畫面上已經有標題時用） */
  hideLabel?: boolean
  hint?: string
  maxlength?: number
  rows?: number
  readonly?: boolean
  disabled?: boolean
  error?: string
  placeholder?: string
  /** 標題右邊的動作文字（Figma showAction）；按下去觸發 action 事件 */
  actionLabel?: string
  actionAriaLabel?: string
  actionPending?: boolean
}>()
const emit = defineEmits<{ action: [] }>()
const value = defineModel<string>({ default: '' })
const id = useId()
// 防呆：外面傳 null 進來也不會壞
const count = computed(() => value.value?.length ?? 0)
const locked = computed(() => props.readonly || props.disabled)
const footText = computed(() => props.error || props.hint)
const describedBy = computed(() => (footText.value || props.maxlength ? `${id}-foot` : undefined))
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      class="flex items-center justify-between gap-3"
      :class="hideLabel && !actionLabel && 'hidden'"
    >
      <label
        :for="id"
        class="text-[20px] font-medium leading-none text-foreground"
        :class="hideLabel && 'sr-only'"
        >{{ label }}</label
      >
      <button
        v-if="actionLabel && !readonly"
        type="button"
        class="flex items-center gap-1 rounded text-body text-primary-dark outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
        :disabled="disabled || actionPending"
        :aria-label="actionAriaLabel"
        @click="emit('action')"
      >
        <SpinnerIcon v-if="actionPending" class="size-5 animate-spin" />
        <RefreshIcon v-else class="size-5" />
        {{ actionLabel }}
      </button>
    </div>
    <label v-if="hideLabel && !actionLabel" :for="id" class="sr-only">{{ label }}</label>
    <textarea
      :id="id"
      v-model="value"
      :rows="rows ?? 2"
      :maxlength="maxlength"
      :readonly="readonly"
      :disabled="disabled"
      :placeholder="placeholder"
      :aria-invalid="error ? true : undefined"
      :aria-describedby="describedBy"
      class="min-h-[96px] w-full resize-y rounded-lg border bg-background px-4 py-3 text-body-lg text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      :class="
        locked
          ? 'border-secondary'
          : error
            ? 'border-[1.5px] border-destructive shadow-input'
            : 'border-border shadow-input hover:border-muted-foreground'
      "
    />
    <div
      v-if="footText || maxlength"
      :id="`${id}-foot`"
      class="flex items-start gap-4 text-body"
      :class="error ? 'text-destructive-dark' : 'text-muted-foreground'"
    >
      <p class="min-w-0 flex-1" :role="error ? 'alert' : undefined">{{ footText }}</p>
      <p v-if="maxlength" class="shrink-0 whitespace-nowrap">{{ count }} / {{ maxlength }}</p>
    </div>
  </div>
</template>
