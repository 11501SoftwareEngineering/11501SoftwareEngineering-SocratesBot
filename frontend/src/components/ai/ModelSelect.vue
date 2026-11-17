<script setup lang="ts">
/**
 * 模型下拉選單（新活動預設模型）。用原生 select，樣式照 Figma「Select」：淺底、細外框、右邊向下箭頭。
 */
import { useId } from 'vue'
import type { InquiryModel } from '@/api/topics'
import { ChevronDownIcon } from '@/components/icons'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{ label: string; models: InquiryModel[]; disabled?: boolean; error?: string }>()
const value = defineModel<string>({ default: '' })
const id = useId()
</script>

<template>
  <div class="flex flex-col gap-1">
    <label :for="id" class="text-header text-foreground">{{ label }}</label>
    <div class="relative">
      <select
        :id="id"
        v-model="value"
        :disabled="disabled || !models.length"
        class="h-11 w-full appearance-none rounded-lg border border-input bg-background px-3 pr-10 text-body-lg text-foreground shadow-elevated outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-60"
      >
        <option v-if="!value" value="" disabled>{{ t('ai.selectModel') }}</option>
        <option v-for="model in models" :key="model.model_id" :value="model.model_id">
          {{ model.name }}
        </option>
      </select>
      <ChevronDownIcon class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2" />
    </div>
    <p v-if="error" role="alert" class="text-body text-destructive">{{ error }}</p>
  </div>
</template>
