<script setup lang="ts" generic="T extends string | number">
/**
 * 下拉選單（標題在上面）。對應 Figma 元件頁「Select」（node 758:2318）與展開的樣子
 * 「Select_Age」「Select_Round」（node 971:2976 / 971:3061）：
 *   框：圓角 8、內距 左 16／右 12／上下 12、背景色 #F7F6F2、外框 #EBE9E1、內陰影（凹陷）、18px 文字、↓ 箭頭
 *   Hover／展開：外框 1.5px 文字輔色；展開時箭頭朝上
 *   Disabled：外框輔色、沒有內陰影和箭頭
 *   選單：白底、外框 #EBE9E1、圓角 8、內距 6、外陰影；每項內距 10、圓角 6、左邊 16px 的勾；選中的項目底色 #F7F6F2
 * 用 reka-ui 的 Select（鍵盤、螢幕閱讀器都處理好了），外觀照 Figma。
 *
 * 用法：<AppSelect v-model="form.age_band" label="年齡層" :options="AGE_BANDS" />
 */
import { useId } from 'vue'
import {
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { CheckIcon, ChevronDownIcon } from '@/components/icons'

defineProps<{
  label: string
  options: { value: T; label: string }[]
  disabled?: boolean
  /** 還沒選（值不在選項裡）時顯示的提示文字 */
  placeholder?: string
  error?: string
}>()
const value = defineModel<T>({ required: true })
const id = useId()
</script>

<template>
  <div class="flex flex-col gap-2">
    <label :for="id" class="text-[20px] font-medium leading-none text-foreground">{{
      label
    }}</label>
    <SelectRoot v-model="value" :disabled="disabled">
      <SelectTrigger
        :id="id"
        :aria-invalid="error ? true : undefined"
        class="group flex h-[54px] w-full items-center gap-2 rounded-lg border border-border bg-background pl-4 pr-3 text-left text-body-lg text-foreground shadow-input outline-none hover:border-[1.5px] hover:border-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 data-[state=open]:border-[1.5px] data-[state=open]:border-muted-foreground data-[disabled]:cursor-default data-[disabled]:border-secondary data-[disabled]:shadow-none data-[placeholder]:text-muted-foreground"
      >
        <SelectValue :placeholder="placeholder" class="min-w-0 flex-1 truncate" />
        <SelectIcon v-if="!disabled" as-child>
          <ChevronDownIcon class="transition-transform group-data-[state=open]:rotate-180" />
        </SelectIcon>
      </SelectTrigger>
      <SelectPortal>
        <SelectContent
          position="popper"
          :side-offset="8"
          class="z-50 max-h-[var(--reka-select-content-available-height)] w-[var(--reka-select-trigger-width)] overflow-hidden rounded-lg border border-border bg-card p-1.5 shadow-elevated"
        >
          <SelectViewport class="flex flex-col gap-0.5">
            <SelectItem
              v-for="o in options"
              :key="String(o.value)"
              :value="o.value"
              class="flex cursor-pointer items-center gap-2 rounded-md p-2.5 text-body-lg text-foreground outline-none select-none data-[highlighted]:bg-background data-[state=checked]:bg-background"
            >
              <span class="flex size-4 shrink-0 items-center justify-center">
                <SelectItemIndicator><CheckIcon /></SelectItemIndicator>
              </span>
              <SelectItemText>{{ o.label }}</SelectItemText>
            </SelectItem>
          </SelectViewport>
        </SelectContent>
      </SelectPortal>
    </SelectRoot>
    <p v-if="error" role="alert" class="text-body text-destructive-dark">{{ error }}</p>
  </div>
</template>
