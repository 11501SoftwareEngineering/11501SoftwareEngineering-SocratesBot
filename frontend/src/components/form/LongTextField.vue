<script setup lang="ts">
/**
 * 多行文字欄位（標題在上面）。對應 Figma「確認活動設定」「新增活動」的 Textarea：
 *   標題（18px）、右邊可以放小按鈕（例如「↻ 重新產生」）
 *   淺底輸入框；maxlength 有設定時下面顯示「XX / 6000」
 *   readonly：已發布的活動，白底、不能改
 */
import { computed, useId } from 'vue'

const props = defineProps<{
  label: string
  maxlength?: number
  rows?: number
  readonly?: boolean
  disabled?: boolean
  error?: string
  placeholder?: string
}>()
const value = defineModel<string>({ default: '' })
const id = useId()
const count = computed(() => value.value.length)
const describedBy = computed(
  () =>
    [props.maxlength ? `${id}-count` : '', props.error ? `${id}-error` : '']
      .filter(Boolean)
      .join(' ') || undefined,
)
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-3">
      <!-- Figma「Textarea」：標籤 H4 20px；框內 18px、內陰影（凹陷）、外框 #EBE9E1、最小高 96 -->
      <label :for="id" class="text-[20px] font-medium leading-none text-foreground">{{
        label
      }}</label>
      <slot name="action" />
    </div>
    <textarea
      :id="id"
      v-model="value"
      :rows="rows ?? 2"
      :maxlength="maxlength"
      :readonly="readonly"
      :disabled="disabled"
      :placeholder="placeholder"
      :aria-invalid="!!error"
      :aria-describedby="describedBy"
      class="min-h-[96px] w-full resize-y rounded-lg border border-border px-4 py-3 text-body-lg text-foreground shadow-input outline-none hover:border-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-[invalid=true]:border-destructive disabled:opacity-60"
      :class="readonly ? 'bg-card' : 'bg-background'"
    />
    <p v-if="error" :id="`${id}-error`" role="alert" class="text-body text-destructive">
      {{ error }}
    </p>
    <p v-if="maxlength" :id="`${id}-count`" class="text-body text-muted-foreground">
      {{ count }} / {{ maxlength }}
    </p>
  </div>
</template>
