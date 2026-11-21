<script setup lang="ts">
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
import ModelSelect from '@/components/ai/ModelSelect.vue'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass } from '@/lib/ui'

const queryClient = useQueryClient()
const usage = useQuery({ queryKey: aiKeys.usage, queryFn: aiApi.usage })
const settings = useQuery({ queryKey: aiKeys.settings, queryFn: aiApi.settings })
const models = useQuery({ queryKey: topicKeys.models, queryFn: topicsApi.models })

const number = (n: number | undefined) => (n === undefined ? '—' : n.toLocaleString('en-US'))
const tiles = computed(() => {
  const u = usage.data.value
  return [
    { label: '總 Token', value: number(u?.total_tokens) },
    { label: '請求次數', value: number(u?.request_count) },
    { label: '輸入', value: number(u?.input_tokens) },
    { label: '輸出', value: number(u?.output_tokens) },
  ]
})

const error = ref('')
const setModel = useMutation({
  mutationFn: (modelId: string) => aiApi.setDefaultModel(modelId),
  onSuccess: () => {
    error.value = ''
    void queryClient.invalidateQueries({ queryKey: aiKeys.settings })
  },
  onError: (err) => (error.value = getApiErrorMessage(err, '儲存失敗，請稍後再試')),
})
</script>

<template>
  <section class="flex flex-col gap-2" aria-labelledby="ai-usage-title">
    <h2 id="ai-usage-title" class="text-h1-title text-foreground">AI 模型與用量</h2>
    <div :class="[cardClass, 'flex flex-col gap-3 p-6']">
      <div class="flex items-center justify-between">
        <h3 class="text-header text-foreground">本月用量</h3>
        <Button as-child variant="secondary">
          <RouterLink :to="{ name: 'TeacherAiSettings' }"><SettingIcon /> API 設定</RouterLink>
        </Button>
      </div>
      <p
        v-if="settings.data.value && !settings.data.value.configured"
        class="text-body text-destructive"
      >
        還沒設定 API key，設定後才能使用 AI 功能。
      </p>
      <dl class="grid grid-cols-2 gap-3">
        <div v-for="tile in tiles" :key="tile.label" class="rounded-lg bg-background px-3 py-2">
          <dt class="text-body text-muted-foreground">{{ tile.label }}</dt>
          <dd class="text-h2-title text-foreground">{{ tile.value }}</dd>
        </div>
        <div class="col-span-2 rounded-lg bg-background px-3 py-2">
          <dt class="text-body text-muted-foreground">本月花費</dt>
          <dd class="text-h2-title text-foreground">{{ formatUsd(usage.data.value?.cost_usd) }}</dd>
        </div>
      </dl>
      <ModelSelect
        label="新活動預設模型"
        :models="models.data.value ?? []"
        :model-value="settings.data.value?.default_model?.id ?? ''"
        :disabled="setModel.isPending.value"
        :error="error"
        @update:model-value="(id) => setModel.mutate(id)"
      />
      <RouterLink
        :to="{ name: 'TeacherAiSettings', hash: '#model-prices' }"
        class="flex w-fit items-center gap-1 rounded text-body text-primary-dark outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >查看模型價格 <ExternalIcon class="size-5" aria-hidden="true"
      /></RouterLink>
    </div>
  </section>
</template>
