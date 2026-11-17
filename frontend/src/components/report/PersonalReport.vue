<script setup lang="ts">
/**
 * 個人報告。對應 Figma「P08_Student_Result_01」（學生看自己的）、「P13_StudentReport」（老師看學生的），兩邊同一個版面：
 *   姓名＋「匿名代碼 · X 回合 · 版本」
 *   目前觀點（左）、觀點狀態標籤（右）
 *   觀點總結（灰底方塊）
 *   觀點變化時間軸：Q1…Qn，每一回合有變化類型標籤、AI 的問題、觀點變化，可以展開「學生回覆」
 *   兩欄：目前立場、最強理由、已檢驗的挑戰、修正或辯護、與探究重點的連結、尚待追問
 *   未完成或證據不足（紅框，證據不足或有限制說明時才出現）
 */
import { computed, ref } from 'vue'
import type { EvidenceQuote, PersonalReport, TimelineEntry } from '@/api/sessions'
import StatusTag from '@/components/common/StatusTag.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  report: PersonalReport
  /** 顯示在最上面的名字（學生看自己的報告時是自己的名字） */
  name: string
  /** 學生原話（message_id → 內容），時間軸展開「學生回覆」時用；沒有就用報告裡的引用 */
  messageText?: Record<string, string>
}>()

const meta = computed(() =>
  [
    props.report.anonymous_id,
    t('report.turns', { n: props.report.completed_turns }),
    t('report.version', { n: props.report.version }),
  ]
    .filter(Boolean)
    .join(' · '),
)

const TONES = ['primary', 'secondary', 'accent'] as const
function toneOf(index: number) {
  return TONES[index % TONES.length]!
}

function quotesOf(entry: TimelineEntry): string[] {
  const evidence = entry.evidence
  const list: (EvidenceQuote | string)[] = Array.isArray(evidence)
    ? evidence
    : evidence
      ? [evidence]
      : []
  return list.map((e) =>
    typeof e === 'string' ? e : (props.messageText?.[e.message_id] ?? e.quote),
  )
}

const open = ref<Record<number, boolean>>({})

const sections = computed(() => [
  { title: t('report.currentStance'), body: props.report.final_viewpoint },
  { title: t('report.strongestReason'), body: props.report.strongest_reason },
  {
    title: t('report.challenges'),
    list: (props.report.challenges ?? []).map(
      (c) => `${c.challenge}${c.responded ? '' : t('report.notResponded')}`,
    ),
  },
  { title: t('report.revision'), body: props.report.revision_or_defense },
  { title: t('report.focusConnection'), body: props.report.focus_connection },
  { title: t('report.openQuestions'), list: props.report.open_questions ?? [] },
])

const EVIDENCE_TEXT = {
  sufficient: '',
  partial: 'report.evidencePartial',
  insufficient: 'report.evidenceInsufficient',
} as const
const gaps = computed(() => {
  const status = props.report.evidence_status
  const key = status ? EVIDENCE_TEXT[status] : ''
  const lead = key ? t(key) : ''
  return [lead, props.report.limitations].filter(Boolean).join('')
})
</script>

<template>
  <article class="flex flex-col gap-6">
    <header class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-4">
        <h2 class="text-h1-title text-foreground">{{ name }}</h2>
        <span
          class="rounded-full border border-border bg-card px-3 py-0.5 text-body text-foreground shadow-elevated"
        >
          {{ meta }}
        </span>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span
          v-if="report.final_viewpoint"
          class="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-0.5 text-body text-foreground shadow-elevated"
        >
          <span class="size-2.5 rounded-full bg-primary" aria-hidden="true" />{{
            report.final_viewpoint
          }}
        </span>
        <StatusTag v-if="report.viewpoint_status" size="sm">{{
          report.viewpoint_status
        }}</StatusTag>
      </div>
    </header>

    <section
      class="rounded-lg bg-border px-3 py-3 shadow-elevated"
      aria-labelledby="report-summary"
    >
      <h3 id="report-summary" class="text-h1-title text-foreground">
        {{ t('report.viewpointSummary') }}
      </h3>
      <p class="text-body-lg text-foreground">{{ report.viewpoint_summary || '—' }}</p>
    </section>

    <section v-if="report.timeline?.length" aria-labelledby="report-timeline">
      <h3 id="report-timeline" class="mb-4 font-heading text-[28px] font-medium text-foreground">
        {{ t('report.timeline') }}
      </h3>
      <ol class="flex flex-col gap-4 border-l-2 border-muted-foreground/60 pl-6">
        <li
          v-for="(entry, i) in report.timeline"
          :key="entry.turn"
          class="relative flex flex-col gap-2"
        >
          <span
            class="absolute top-2 -left-[31px] size-3 rounded-full bg-muted-foreground"
            aria-hidden="true"
          />
          <div class="flex items-center gap-2">
            <span class="text-h2-title font-medium text-foreground">Q{{ entry.turn }}</span>
            <StatusTag v-if="entry.change_type" size="sm" :tone="toneOf(i)">{{
              entry.change_type
            }}</StatusTag>
          </div>
          <p class="text-body font-bold text-foreground">{{ entry.question }}</p>
          <p
            v-if="entry.viewpoint_after"
            class="rounded bg-muted px-3 py-1 text-body-lg text-foreground"
          >
            {{ entry.viewpoint_after }}
          </p>
          <button
            v-if="quotesOf(entry).length"
            type="button"
            class="w-fit rounded text-body text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
            :aria-expanded="!!open[entry.turn]"
            @click="open[entry.turn] = !open[entry.turn]"
          >
            {{ open[entry.turn] ? '▼' : '▶' }} {{ t('report.studentReply') }}
          </button>
          <p v-if="open[entry.turn]" class="text-body text-muted-foreground">
            {{ quotesOf(entry).join('　') }}
          </p>
        </li>
      </ol>
    </section>

    <dl class="grid gap-x-4 sm:grid-cols-2">
      <div
        v-for="section in sections"
        :key="section.title"
        class="border-b border-muted-foreground/60 px-3 py-5"
      >
        <dt class="text-header text-foreground">{{ section.title }}</dt>
        <dd class="mt-2 text-body text-muted-foreground">
          <ul v-if="section.list" class="list-disc pl-5">
            <li v-for="item in section.list" :key="item">{{ item }}</li>
            <li v-if="!section.list.length" class="list-none -ml-5">—</li>
          </ul>
          <template v-else>{{ section.body || '—' }}</template>
        </dd>
      </div>
    </dl>

    <section
      v-if="gaps"
      class="rounded-lg border border-destructive bg-card px-3 py-2"
      aria-labelledby="report-gaps"
    >
      <h3 id="report-gaps" class="text-header text-foreground">{{ t('report.gaps') }}</h3>
      <p class="mt-1 text-body text-muted-foreground">{{ gaps }}</p>
    </section>
  </article>
</template>
