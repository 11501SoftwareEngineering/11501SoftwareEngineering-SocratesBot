<script setup lang="ts">
/**
 * 核取方塊。對應 Figma 元件頁「核取方塊」（node 343:1332），
 * 使用設計稿匯出的勾選／未勾選圖示。
 *
 * 用法：
 *   <AppCheckbox v-model="isAnonymous" label="匿名分享我的結論" />
 *
 * - 點文字也能切換；空白鍵可以切換（用原生 checkbox，鍵盤和螢幕報讀器都支援）
 * - 文字用 label 屬性傳，不用 slot：label 和 checkbox 用 for / id 明確綁在一起，
 *   靜態檢查（SonarCloud 無障礙規則）才看得出這個 label 有文字、有對應的控制項
 */
import { useId } from 'vue'
import { CheckboxCheckedIcon, CheckboxUncheckedIcon } from '@/components/icons'

defineProps<{ label: string; disabled?: boolean }>()
const checked = defineModel<boolean>({ default: false })
const id = useId()
</script>

<template>
  <label
    :for="id"
    class="inline-flex cursor-pointer items-center gap-2 text-body-lg text-foreground select-none has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50"
  >
    <span
      class="relative inline-flex size-6 shrink-0 rounded-md has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50"
    >
      <input
        :id="id"
        v-model="checked"
        type="checkbox"
        :disabled="disabled"
        class="peer absolute inset-0 size-full cursor-[inherit] opacity-0"
      />
      <CheckboxCheckedIcon v-if="checked" class="size-6" />
      <CheckboxUncheckedIcon v-else class="size-6" />
    </span>
    {{ label }}
  </label>
</template>
