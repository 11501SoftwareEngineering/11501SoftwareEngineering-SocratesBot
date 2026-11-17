<script setup lang="ts">
/**
 * 介面語言切換（Header 右上角）。對應 Figma 元件「Language」（node 961:2775）：
 * 主色淺底的膠囊按鈕，地球圖示 + 目前語言 + 向下箭頭，點了選正體中文、English、Español。
 */
import { ChevronDownIcon, GlobeIcon } from '@/components/icons'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
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
      class="w-40 rounded-lg border border-border bg-card p-1 shadow-elevated"
    >
      <DropdownMenuRadioGroup
        :model-value="language"
        @update:model-value="(value) => setLanguage(value as Locale)"
      >
        <DropdownMenuRadioItem
          v-for="option in options"
          :key="option.value"
          :value="option.value"
          class="cursor-pointer py-2 text-body-lg focus:bg-muted focus:text-foreground"
        >
          {{ option.label }}
        </DropdownMenuRadioItem>
      </DropdownMenuRadioGroup>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
