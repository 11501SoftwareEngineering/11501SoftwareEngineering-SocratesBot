<script setup lang="ts">
/**
 * 介面語言切換（Header 右上角）。對應 Figma 元件「Language」（node 961:2775）：
 * 主色淺底的膠囊按鈕，地球圖示 + 目前語言 + 向下箭頭，點了選正體中文、English、Español。
 * 選單（Lang=…, State=Open）：寬 150、白底、圓角 8、內距 6；每項內距 10/8、左邊 16px 的勾，選中的項目底色 #F7F6F2。
 */
import { DropdownMenuItemIndicator, DropdownMenuRadioItem } from 'reka-ui'
import { CheckIcon, ChevronDownIcon, GlobeIcon } from '@/components/icons'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useUiLanguage } from '@/composables/useUiLanguage'
import type { Locale } from '@/i18n'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const { language, label, options, setLanguage } = useUiLanguage()
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger
      class="flex items-center gap-1.5 rounded-2xl bg-primary-light py-1.5 pr-2.5 pl-3 text-body-lg whitespace-nowrap text-foreground outline-none hover:brightness-95 focus-visible:ring-[3px] focus-visible:ring-ring/50"
      :aria-label="t('language.switcher', { label })"
    >
      <GlobeIcon />
      <span class="hidden sm:inline">{{ label }}</span>
      <ChevronDownIcon class="size-4" />
    </DropdownMenuTrigger>
    <DropdownMenuContent
      align="end"
      class="flex w-[150px] flex-col gap-0.5 rounded-lg border border-border bg-card p-1.5 shadow-elevated"
    >
      <DropdownMenuRadioGroup
        :model-value="language"
        @update:model-value="(value) => setLanguage(value as Locale)"
      >
        <DropdownMenuRadioItem
          v-for="option in options"
          :key="option.value"
          :value="option.value"
          class="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-2 text-body-lg text-foreground outline-none select-none data-[highlighted]:bg-background data-[state=checked]:bg-background"
        >
          <span class="flex size-4 shrink-0 items-center justify-center">
            <DropdownMenuItemIndicator><CheckIcon /></DropdownMenuItemIndicator>
          </span>
          {{ option.label }}
        </DropdownMenuRadioItem>
      </DropdownMenuRadioGroup>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
