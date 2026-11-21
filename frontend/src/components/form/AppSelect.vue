<script setup lang="ts" generic="T extends string | number">
/**
 * 下拉選單（標題在上面）。對應 Figma 元件「Select」：淺底、細外框、右邊向下箭頭。
 * 用原生 select，鍵盤、螢幕閱讀器都不用另外處理。
 *
 * 用法：<AppSelect v-model="form.age_band" label="年齡層" :options="AGE_BANDS" />
 */
import { useId } from 'vue'
import { ChevronDownIcon } from '@/components/icons'

defineProps<{
  label: string
  options: { value: T; label: string }[]
  disabled?: boolean
}>()
const value = defineModel<T>({ required: true })
const id = useId()
</script>

<template>
  <div class="flex flex-col gap-2">
    <!-- Figma「Select_Age」「Select_Round」：標籤 H4 20px；框內 18px、內陰影（凹陷）、外框 #EBE9E1 -->
    <label :for="id" class="text-[20px] font-medium leading-none text-foreground">{{
      label
    }}</label>
    <div class="relative">
      <select
        :id="id"
        v-model="value"
        :disabled="disabled"
        class="h-[54px] w-full appearance-none rounded-lg border border-border bg-background pl-4 pr-10 text-body-lg text-foreground shadow-input outline-none hover:border-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-default disabled:bg-card disabled:opacity-100"
      >
        <option v-for="o in options" :key="String(o.value)" :value="o.value">{{ o.label }}</option>
      </select>
      <ChevronDownIcon
        v-if="!disabled"
        class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2"
      />
    </div>
  </div>
</template>
