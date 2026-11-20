<script setup lang="ts">
import AppBanner from '@/components/common/AppBanner.vue'
/**
 * 老師首頁右邊的「AI 模型與用量」。對應 Figma「P09_Teacher_Home」（node 692:3019）右半邊：
 *   本月用量（右上「API 設定」連到 P14）、總 Token、請求次數、輸入、輸出、本月花費
 *   新活動預設模型（下拉）、查看模型價格（連到 P14 的價格表）
 * API：GET /users/me/ai/usage、GET /users/me/ai/settings、GET /inquiry-models、PATCH /users/me/ai/model
 */
import { computed, ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { aiApi, aiKeys, formatUsd } from '@/api/ai'
import { topicKeys, topicsApi } from '@/api/topics'
import { ExternalIcon, SettingIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import AppSelect from '@/components/form/AppSelect.vue'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass } from '@/lib/ui'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const queryClient = useQueryClient()
const usage = useQuery({ queryKey: aiKeys.usage, queryFn: aiApi.usage })
const settings = useQuery({ queryKey: aiKeys.settings, queryFn: aiApi.settings })
const models = useQuery({ queryKey: topicKeys.models, queryFn: topicsApi.models })
/** 下拉選單的選項（模型 id → 名稱） */
const modelOptions = computed(() =>
  (models.data.value ?? []).map((m) => ({ value: m.model_id, label: m.name })),
)

const number = (n: number | undefined) => (n === undefined ? '—' : n.toLocaleString('en-US'))
const tiles = computed(() => {
  const u = usage.data.value
  return [
    { label: t('ai.totalTokens'), value: number(u?.total_tokens) },
    { label: t('ai.requests'), value: number(u?.request_count) },
    { label: t('ai.input'), value: number(u?.input_tokens) },
    { label: t('ai.output'), value: number(u?.output_tokens) },
  ]
})

const error = ref('')
const setModel = useMutation({
  mutationFn: (modelId: string) => aiApi.setDefaultModel(modelId),
  onSuccess: () => {
    error.value = ''
    void queryClient.invalidateQueries({ queryKey: aiKeys.settings })
  },
  onError: (err) => (error.value = getApiErrorMessage(err, t('errors.saveFailed'))),
})
</script>

<template>
  <section class="flex flex-col gap-2" aria-labelledby="ai-usage-title">
    <h2 id="ai-usage-title" class="text-h1-title text-foreground">{{ t('ai.panelTitle') }}</h2>
    <div :class="[cardClass, 'flex flex-col gap-3 p-6']">
      <div class="flex items-center justify-between">
        <h3 class="text-header text-foreground">{{ t('ai.thisMonth') }}</h3>
        <Button as-child variant="secondary">
          <RouterLink :to="{ name: 'TeacherAiSettings' }"
            ><SettingIcon /> {{ t('ai.apiSettings') }}</RouterLink
          >
        </Button>
      </div>
      <AppBanner v-if="settings.data.value && !settings.data.value.configured" type="info">
        {{ t('ai.noKey') }}
      </AppBanner>
      <dl class="grid grid-cols-2 gap-3">
        <div v-for="tile in tiles" :key="tile.label" class="rounded-lg bg-background px-3 py-2">
          <dt class="text-body text-muted-foreground">{{ tile.label }}</dt>
          <dd class="text-h2-title text-foreground">{{ tile.value }}</dd>
        </div>
        <div class="col-span-2 rounded-lg bg-background px-3 py-2">
          <dt class="text-body text-muted-foreground">{{ t('ai.cost') }}</dt>
          <dd class="text-h2-title text-foreground">{{ formatUsd(usage.data.value?.cost_usd) }}</dd>
        </div>
      </dl>
      <AppSelect
        :label="t('ai.defaultModel')"
        :options="modelOptions"
        :placeholder="t('ai.selectModel')"
        :model-value="settings.data.value?.default_model?.id ?? ''"
        :disabled="setModel.isPending.value"
        :error="error"
        @update:model-value="(id: string) => setModel.mutate(id)"
      />
      <RouterLink
        :to="{ name: 'TeacherAiSettings', hash: '#model-prices' }"
        class="flex w-fit items-center gap-1 rounded text-body text-primary-dark outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >{{ t('ai.viewPrices') }} <ExternalIcon class="size-5" aria-hidden="true"
      /></RouterLink>
    </div>
  </section>
</template>
