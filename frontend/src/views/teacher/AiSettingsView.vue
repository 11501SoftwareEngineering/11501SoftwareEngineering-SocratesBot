<script setup lang="ts">
/**
 * 老師：AI 用量與金鑰。對應 Figma「P14_Teacher_AI」（node 750:2506）、「P14_NoKey」（1022:3121）、
 * 「P14_RemoveKey」（750:2599）。
 *   本月用量：月份、更新時間、「更新」；總 Token／輸入／輸出／請求次數／本月花費；各階段用量；新活動預設模型
 *   API key：已設定（遮罩後的 key）／尚未設定；輸入新的 key、儲存、移除（先確認）
 *   模型價格（#model-prices，老師首頁的「查看模型價格」會連到這裡；捲動在 router 的 scrollBehavior）
 * API：GET /users/me/ai/usage、GET /users/me/ai/settings、PUT/DELETE /users/me/ai/api-key、
 *      PATCH /users/me/ai/model、GET /inquiry-models
 */
import { computed, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { aiApi, aiKeys, formatUsd, USAGE_STAGES } from '@/api/ai'
import { topicKeys, topicsApi } from '@/api/topics'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import PageTitle from '@/components/common/PageTitle.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import ModelSelect from '@/components/ai/ModelSelect.vue'
import { RefreshIcon, SpinnerIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass, pageClass } from '@/lib/ui'

const queryClient = useQueryClient()
const usage = useQuery({ queryKey: aiKeys.usage, queryFn: aiApi.usage })
const settings = useQuery({ queryKey: aiKeys.settings, queryFn: aiApi.settings })
const models = useQuery({ queryKey: topicKeys.models, queryFn: topicsApi.models })

const num = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-US'))
const hasUsage = computed(() => !!usage.data.value?.request_count)
const month = computed(() => {
  const [y, m] = (usage.data.value?.month ?? '').split('-')
  return y && m ? `${y} 年 ${Number(m)} 月` : ''
})
const updatedAt = computed(() => {
  const at = usage.data.value?.updated_at
  if (!at) return '尚無資料'
  const d = new Date(at)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `更新時間 ${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
})
const tiles = computed(() => {
  const u = hasUsage.value ? usage.data.value : undefined
  return [
    { label: '總 Token', value: num(u?.total_tokens) },
    { label: '輸入', value: num(u?.input_tokens) },
    { label: '輸出', value: num(u?.output_tokens) },
    { label: '請求次數', value: num(u?.request_count) },
    { label: '本月花費', value: formatUsd(u?.cost_usd) },
  ]
})
const stages = computed(() =>
  USAGE_STAGES.map(({ value, label }) => {
    const s = usage.data.value?.by_stage.find((x) => x.stage === value)
    const used = !!s?.request_count
    return {
      label,
      input: used ? num(s?.input_tokens) : '—',
      output: used ? num(s?.output_tokens) : '—',
      count: used ? num(s?.request_count) : '—',
    }
  }),
)

// 預設模型
const modelError = ref('')
const setModel = useMutation({
  mutationFn: (modelId: string) => aiApi.setDefaultModel(modelId),
  onSuccess: () => {
    modelError.value = ''
    void queryClient.invalidateQueries({ queryKey: aiKeys.settings })
  },
  onError: (err) => (modelError.value = getApiErrorMessage(err, '儲存失敗，請稍後再試')),
})
const defaultModelId = computed(() => settings.data.value?.default_model?.id ?? '')

// API key
const newKey = ref('')
const keyError = ref('')
const keyNotice = ref('')
const saveKey = useMutation({
  mutationFn: () => aiApi.setApiKey(newKey.value.trim()),
  onSuccess: () => {
    newKey.value = ''
    keyError.value = ''
    keyNotice.value = 'API key 已儲存'
    void queryClient.invalidateQueries({ queryKey: aiKeys.settings })
  },
  onError: (err) => {
    keyNotice.value = ''
    const status = isAxiosError(err) ? err.response?.status : undefined
    keyError.value =
      status === 400 || status === 422
        ? 'API key 格式不正確，OpenRouter 的 key 是 sk-or- 開頭'
        : getApiErrorMessage(err, '儲存失敗，請稍後再試')
  },
})
const removeOpen = ref(false)
const removeKey = useMutation({
  mutationFn: aiApi.removeApiKey,
  onSuccess: () => {
    removeOpen.value = false
    keyError.value = ''
    keyNotice.value = 'API key 已移除'
    void queryClient.invalidateQueries({ queryKey: aiKeys.settings })
  },
  onError: (err) => {
    removeOpen.value = false
    keyError.value = getApiErrorMessage(err, '移除失敗，請稍後再試')
  },
})
watch(newKey, () => (keyError.value = ''))
function submitKey() {
  if (!newKey.value.trim()) {
    keyError.value = '請輸入 API key'
    return
  }
  saveKey.mutate()
}
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      title="AI 用量與金鑰"
      :breadcrumbs="[{ label: '我的課程', to: { name: 'TeacherCourses' } }]"
    />

    <!-- 本月用量 -->
    <section
      :class="[cardClass, 'mt-[23px] flex flex-col gap-4 p-[30px]']"
      aria-labelledby="usage-title"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h2 id="usage-title" class="flex items-baseline gap-3 text-h2-title text-foreground">
          本月用量 <span class="text-body text-muted-foreground">{{ month }}</span>
        </h2>
        <div class="flex items-center gap-3">
          <span class="text-body text-muted-foreground">{{ updatedAt }}</span>
          <Button variant="secondary" :disabled="usage.isFetching.value" @click="usage.refetch()">
            <SpinnerIcon v-if="usage.isFetching.value" class="animate-spin" />
            <RefreshIcon v-else />
            更新
          </Button>
        </div>
      </div>
      <p v-if="usage.error.value" role="alert" class="text-body text-destructive">
        {{ getApiErrorMessage(usage.error.value, '無法取得用量') }}
      </p>
      <dl class="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <div v-for="t in tiles" :key="t.label" class="rounded-lg bg-background px-4 py-3">
          <dt class="text-body text-muted-foreground">{{ t.label }}</dt>
          <dd class="text-h2-title text-foreground">{{ t.value }}</dd>
        </div>
      </dl>

      <h3 class="text-body-lg font-medium text-foreground">各階段用量</h3>
      <table class="w-full text-left text-body text-foreground">
        <thead class="text-muted-foreground">
          <tr>
            <th scope="col" class="w-1/4 py-1 font-normal">階段</th>
            <th scope="col" class="w-1/4 py-1 font-normal">輸入</th>
            <th scope="col" class="w-1/4 py-1 font-normal">輸出</th>
            <th scope="col" class="w-1/4 py-1 font-normal">次數</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in stages" :key="s.label">
            <th scope="row" class="py-1 font-normal">{{ s.label }}</th>
            <td class="py-1">{{ s.input }}</td>
            <td class="py-1">{{ s.output }}</td>
            <td class="py-1">{{ s.count }}</td>
          </tr>
        </tbody>
      </table>

      <div class="flex flex-wrap items-end gap-4">
        <ModelSelect
          class="w-full max-w-[420px]"
          label="新活動預設模型"
          :models="models.data.value ?? []"
          :model-value="defaultModelId"
          :disabled="setModel.isPending.value"
          :error="modelError"
          @update:model-value="(id) => setModel.mutate(id)"
        />
        <a
          href="#model-prices"
          class="mb-2 rounded text-body text-muted-foreground outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >往下滑可查看模型價格</a
        >
      </div>
    </section>

    <!-- API key -->
    <section :class="[cardClass, 'mt-6 flex flex-col gap-4 p-[30px]']" aria-labelledby="key-title">
      <h2 id="key-title" class="text-h2-title text-foreground">API key</h2>
      <p
        v-if="settings.data.value"
        class="flex flex-wrap items-center gap-3 text-body text-foreground"
      >
        <template v-if="settings.data.value.configured">
          <StatusTag>已設定</StatusTag>
          <span>{{ settings.data.value.masked_key }}</span>
        </template>
        <template v-else>
          <StatusTag tone="secondary">尚未設定</StatusTag>
          <span>設定 API key 後才能使用 AI 功能</span>
        </template>
      </p>
      <form class="flex flex-col gap-3" @submit.prevent="submitKey">
        <label for="api-key" class="sr-only">
          {{ settings.data.value?.configured ? '輸入新的 API key' : '輸入 OpenRouter API key' }}
        </label>
        <Input
          id="api-key"
          v-model="newKey"
          type="password"
          autocomplete="off"
          class="h-12 text-body-lg"
          :placeholder="
            settings.data.value?.configured ? '輸入新的 API key' : '輸入 OpenRouter API key'
          "
          :aria-invalid="!!keyError"
          :aria-describedby="keyError ? 'api-key-error' : undefined"
        />
        <p v-if="keyError" id="api-key-error" role="alert" class="text-body text-destructive">
          {{ keyError }}
        </p>
        <p v-else-if="keyNotice" role="status" class="text-body text-primary-dark">
          {{ keyNotice }}
        </p>
        <div class="flex justify-end gap-3">
          <Button
            v-if="settings.data.value?.configured"
            type="button"
            variant="destructive"
            :disabled="removeKey.isPending.value"
            @click="removeOpen = true"
            >移除</Button
          >
          <Button type="submit" :disabled="saveKey.isPending.value">
            {{ saveKey.isPending.value ? '儲存中…' : '儲存' }}
          </Button>
        </div>
      </form>
    </section>

    <!-- 模型價格 -->
    <section
      id="model-prices"
      :class="[cardClass, 'mt-6 flex scroll-mt-6 flex-col gap-3 p-[30px]']"
      aria-labelledby="prices-title"
    >
      <h2 id="prices-title" class="text-h2-title text-foreground">模型價格</h2>
      <p class="text-body text-muted-foreground">價格為示範資料，實際費用以 OpenRouter 為準</p>
      <div class="overflow-x-auto">
        <table class="w-full min-w-[640px] text-left text-body text-foreground">
          <thead class="text-muted-foreground">
            <tr>
              <th scope="col" class="py-2 font-normal">模型</th>
              <th scope="col" class="py-2 font-normal">說明</th>
              <th scope="col" class="py-2 font-normal">每百萬輸入</th>
              <th scope="col" class="py-2 font-normal">每百萬輸出</th>
              <th scope="col" class="py-2"><span class="sr-only">預設</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in models.data.value ?? []" :key="m.model_id">
              <th scope="row" class="py-2 pr-4 font-normal">{{ m.name }}</th>
              <td class="py-2 pr-4">{{ m.description }}</td>
              <td class="py-2 pr-4">{{ formatUsd(m.input_price_usd) }}</td>
              <td class="py-2 pr-4">{{ formatUsd(m.output_price_usd) }}</td>
              <td class="py-2 text-right">
                <StatusTag v-if="m.model_id === defaultModelId" size="sm">目前預設</StatusTag>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ConfirmDialog
      v-model:open="removeOpen"
      title="移除 API key？"
      description="移除之後要重新設定才能使用 AI"
      confirm-text="移除"
      destructive
      :loading="removeKey.isPending.value"
      @confirm="removeKey.mutate()"
    />
  </div>
</template>
