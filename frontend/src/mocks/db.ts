/**
 * 假後端的資料庫（只存在瀏覽器裡），欄位照 docs/API功能規格.md v0.2。
 * 資料存在 localStorage，重新整理不會不見；Debug 面板的「重置假資料」會回到初始狀態。
 * API 回傳格式在 handlers.ts 轉換。
 */
import { reactive, watch } from 'vue'
import type { AgeBand, MaxTurns, TaPermission, TopicStatus } from '@/api/courses'
import type { TopicSetup } from '@/api/topics'
import type { PersonalReport } from '@/api/sessions'
import type { SummaryStatus } from '@/api/summaries'
import type { UsageStage } from '@/api/ai'
import { mockReport, mockSetup, mockTranscript } from './ai'

export type DbRole = 'USER' | 'TEACHER' | 'SUPERADMIN'

export interface DbUser {
  id: string
  account_id: string
  name: string
  password: string
  role: DbRole
  must_change_password: boolean
  preferred_language: 'zh-TW' | 'en' | 'es'
  created_at: string
}

export interface DbCourse {
  id: string
  name: string
  description: string
  invite_code: string
  teacher_id: string
  created_at: string
}

/** 課程成員：學生或助教（老師記在 DbCourse.teacher_id） */
export interface DbMember {
  course_id: string
  user_id: string
  role: 'student' | 'ta'
  permissions: TaPermission[]
  joined_at: string
}

export interface DbTopic {
  id: string
  course_id: string
  status: TopicStatus
  course_description: string
  model_id: string
  setup: TopicSetup
  created_at: string
}

export interface DbMessage {
  id: string
  sender: 'ai' | 'student'
  content: string
  created_at: string
}

export interface DbSession {
  id: string
  topic_id: string
  student_id: string
  /**
   * 假後端簡化：只要結束了（達成目標後結束、回合用完、提早結束）都記成 COMPLETED，
   * 用 ending_reason 分辨；對話 API 回傳時再換成 completed／ended（見 handlers 的 dialogueStatus）
   */
  status: 'IN_PROGRESS' | 'COMPLETED'
  awaiting_end_consent: boolean
  /** AI 判斷達成過目標（一旦達成就一直是 true，跟真後端一樣） */
  goal_reached?: boolean
  /** goal_reached（達成目標後選結束）｜turn_limit（回合用完）｜student_requested_stop（提早結束） */
  ending_reason?: 'goal_reached' | 'turn_limit' | 'student_requested_stop' | null
  messages: DbMessage[]
  completed_at: string | null
}

export interface DbReport {
  session_id: string
  /** 報告產生完成的時間（毫秒）；還沒到就回 processing */
  ready_at: number
  failed: boolean
  report: PersonalReport
}

export interface DbSummary {
  topic_id: string
  version: number
  status: SummaryStatus
  overview: string
  viewpoint_summary: string
  denominator: number
  groups: {
    group_id: string
    name: string
    conditions: string
    count: number
    percentage: number
    report_ids: string[]
  }[]
  ungrouped_report_ids: string[]
  created_at: string
  updated_at: string
}

export interface DbAiSettings {
  user_id: string
  api_key: string | null
  key_updated_at: string | null
  default_model_id: string
  usage: Record<UsageStage, { request_count: number; input_tokens: number; output_tokens: number }>
}

export interface DbModel {
  model_id: string
  name: string
  description: string
  provider_id: string
  input_price_usd: number
  output_price_usd: number
}

export interface Db {
  users: DbUser[]
  courses: DbCourse[]
  members: DbMember[]
  topics: DbTopic[]
  sessions: DbSession[]
  reports: DbReport[]
  summaries: DbSummary[]
  aiSettings: DbAiSettings[]
  models: DbModel[]
}

/** 所有假帳號的密碼都一樣，方便 Demo */
export const DEMO_PASSWORD = 'password123'

let counter = 0
export function newId(prefix: string) {
  counter += 1
  return `${prefix}-${Date.now().toString(36)}-${counter}`
}

/**
 * 0 到 n-1 之間均勻分布的安全亂數。
 * 直接拿 `亂數 % n` 會稍微偏向較小的數（CodeQL js/biased-cryptographic-random 會擋），
 * 所以落在最後那段湊不滿 n 的範圍就丟掉重抽（rejection sampling）。
 */
export function secureRandomInt(n: number) {
  const limit = 2 ** 32 - (2 ** 32 % n)
  const buffer = new Uint32Array(1)
  for (;;) {
    crypto.getRandomValues(buffer)
    const value = buffer[0] ?? 0
    if (value >= limit) continue
    return value % n
  }
}

/**
 * 用安全的亂數（crypto.getRandomValues）從 chars 裡挑 length 個字。
 * 密碼、課程代碼不能用 Math.random()：它的結果可以被預測（SonarCloud 也會擋）。
 */
export function secureRandomString(chars: string, length: number) {
  return Array.from({ length }, () => chars[secureRandomInt(chars.length)]).join('')
}

export function newInviteCode() {
  // 跟後端一樣：8 個字元，不含容易看錯的 I、L、O、0、1
  return secureRandomString('ABCDEFGHJKMNPQRSTUVWXYZ23456789', 8)
}

export const day = (n: number, hour = 1) => new Date(Date.UTC(2026, 8, 1 + n, hour)).toISOString()

const STUDENT_NAMES = [
  '王小明',
  '林怡君',
  '陳冠宇',
  '張雅婷',
  '李承翰',
  '黃詩涵',
  '吳柏翰',
  '劉品妤',
  '蔡宗翰',
  '楊子晴',
  '許家豪',
  '鄭心怡',
]

function user(id: string, account_id: string, name: string, role: DbRole, n: number): DbUser {
  return {
    id,
    account_id,
    name,
    password: DEMO_PASSWORD,
    role,
    must_change_password: false,
    preferred_language: 'zh-TW',
    created_at: day(n),
  }
}

export const MODELS: DbModel[] = [
  {
    model_id: 'openai/gpt-6-luna',
    name: 'GPT-6 Luna',
    description: '回覆穩定、適合一般課堂',
    provider_id: 'openai',
    input_price_usd: 0.4,
    output_price_usd: 1.6,
  },
  {
    model_id: 'anthropic/claude-sonnet-5.5',
    name: 'Claude Sonnet 5.5',
    description: '擅長追問與長篇推理',
    provider_id: 'anthropic',
    input_price_usd: 3,
    output_price_usd: 15,
  },
  {
    model_id: 'google/gemini-3-flash',
    name: 'Gemini 3 Flash',
    description: '速度快、價格低',
    provider_id: 'google',
    input_price_usd: 0.1,
    output_price_usd: 0.4,
  },
  {
    model_id: 'meta/llama-5-70b',
    name: 'Llama 5 70B',
    description: '開源模型，價格最低',
    provider_id: 'meta',
    input_price_usd: 0.05,
    output_price_usd: 0.2,
  },
]

interface SeedTopic {
  id: string
  course_id: string
  status: TopicStatus
  title: string
  question: string
  age_band: AgeBand
  max_turns: MaxTurns
  n: number
}

const SEED_TOPICS: SeedTopic[] = [
  {
    id: 't-lie',
    course_id: 'c-phil',
    status: 'summary',
    title: '善意的謊言',
    question: '為了不讓別人難過而說謊，可以被接受嗎？',
    age_band: '16-18',
    max_turns: 5,
    n: 10,
  },
  {
    id: 't-ai',
    course_id: 'c-phil',
    status: 'conversation',
    title: '人工智慧的責任',
    question: 'AI 做錯決定時，應該由誰負責？',
    age_band: '16-18',
    max_turns: 10,
    n: 12,
  },
  {
    id: 't-free',
    course_id: 'c-phil',
    status: 'setup',
    title: '自由意志與道德責任',
    question: '如果我們的選擇早就被決定了，還需要為行為負責嗎？',
    age_band: '16-18',
    max_turns: 10,
    n: 14,
  },
  {
    id: 't-speech',
    course_id: 'c-civic',
    status: 'conversation',
    title: '言論自由的界線',
    question: '網路上的言論，應該有界線嗎？',
    age_band: '13-15',
    max_turns: 5,
    n: 13,
  },
  {
    id: 't-fair',
    course_id: 'c-ethic',
    status: 'conversation',
    title: '公平是什麼',
    question: '每個人分到一樣多，就是公平嗎？',
    age_band: '13-15',
    max_turns: 5,
    n: 15,
  },
]

/** 善意的謊言：各學生的觀點（決定報告內容和摘要分組） */
const LIE_STANCES = [
  'support',
  'support',
  'conditional',
  'conditional',
  'conditional',
  'oppose',
  'oppose',
  'conditional',
] as const

export function createSeed(): Db {
  const users: DbUser[] = [
    user('u-admin', 'admin', '系統管理員', 'SUPERADMIN', 0),
    user('u-wang', 'wang', '王老師', 'TEACHER', 1),
    user('u-lin', 'lin', '林老師', 'TEACHER', 2),
    user('u-chen', 'chen', '陳老師', 'TEACHER', 3),
    ...STUDENT_NAMES.map((name, i) =>
      user(`u-s${i + 1}`, `s${String(i + 1).padStart(3, '0')}`, name, 'USER', 4 + i),
    ),
  ]
  const chen = users.find((u) => u.id === 'u-chen')
  if (chen) chen.must_change_password = true

  const courses: DbCourse[] = [
    {
      id: 'c-phil',
      name: '哲學概論',
      description: '從日常問題出發，練習提問與論證。',
      invite_code: 'PHSP3456',
      teacher_id: 'u-wang',
      created_at: day(5),
    },
    {
      id: 'c-civic',
      name: '公民與社會',
      description: '討論公共議題，理解不同立場。',
      invite_code: 'CVCS5678',
      teacher_id: 'u-wang',
      created_at: day(6),
    },
    {
      id: 'c-ethic',
      name: '倫理學入門',
      description: '什麼是對的事？從生活中的兩難開始想。',
      invite_code: 'ETHC7892',
      teacher_id: 'u-lin',
      created_at: day(7),
    },
  ]

  // 哲學概論：s001–s010 是學生，s011 是助教；s012 還沒加入（可以用 PHSP3456 加入）
  const members: DbMember[] = []
  const student = (course_id: string, i: number, n: number): DbMember => ({
    course_id,
    user_id: `u-s${i}`,
    role: 'student',
    permissions: [],
    joined_at: day(n),
  })
  for (let i = 1; i <= 10; i += 1) members.push(student('c-phil', i, 8))
  members.push({
    course_id: 'c-phil',
    user_id: 'u-s11',
    role: 'ta',
    permissions: ['view_members', 'view_reports'],
    joined_at: day(8),
  })
  for (let i = 1; i <= 8; i += 1) members.push(student('c-civic', i, 9))
  for (let i = 6; i <= 12; i += 1) members.push(student('c-ethic', i, 9))

  const topics: DbTopic[] = SEED_TOPICS.map((t) => ({
    id: t.id,
    course_id: t.course_id,
    status: t.status,
    course_description: `${t.title}：${t.question}`,
    model_id: MODELS[0]!.model_id,
    setup: {
      ...mockSetup(`${t.title}。${t.question}`, t.age_band, t.max_turns),
      topic: t.title,
      core_question: t.question,
    },
    created_at: day(t.n),
  }))

  const sessions: DbSession[] = []
  const reports: DbReport[] = []
  const addSession = (
    topic: DbTopic,
    i: number,
    turns: number,
    completed: boolean,
    stance = '',
  ) => {
    const id = `ss-${topic.id}-${i}`
    const messages = mockTranscript(topic.setup, turns, day(topic.id === 't-lie' ? 11 : 13, 2 + i))
    sessions.push({
      id,
      topic_id: topic.id,
      student_id: `u-s${i}`,
      status: completed ? 'COMPLETED' : 'IN_PROGRESS',
      awaiting_end_consent: false,
      messages,
      completed_at: completed ? day(11, 3 + i) : null,
    })
    if (completed) {
      reports.push({
        session_id: id,
        ready_at: 0,
        failed: false,
        report: mockReport({
          sessionId: id,
          topic,
          messages,
          anonymousId: `學生 ${String.fromCharCode(64 + i)}`,
          completedAt: day(11, 3 + i),
          stance,
        }),
      })
    }
  }

  // 善意的謊言（已進入摘要）：s001–s008 完成，s009 沒做完
  const lie = topics.find((t) => t.id === 't-lie')!
  LIE_STANCES.forEach((stance, idx) => addSession(lie, idx + 1, 5, true, stance))
  addSession(lie, 9, 2, false)
  // 人工智慧的責任（對話中）：s002 完成、s001 進行中
  const ai = topics.find((t) => t.id === 't-ai')!
  addSession(ai, 2, 6, true, 'conditional')
  addSession(ai, 1, 2, false)
  addSession(ai, 3, 3, false)

  const reportId = (i: number) =>
    reports.find((r) => r.session_id === `ss-t-lie-${i}`)!.report.report_id
  const group = (group_id: string, name: string, conditions: string, ids: number[]) => ({
    group_id,
    name,
    conditions,
    count: ids.length,
    percentage: Math.round((ids.length / 8) * 100),
    report_ids: ids.map(reportId),
  })
  const groups = [
    group('g-support', '善意謊言可以接受', '出發點是保護對方、而且傷害很小時', [1, 2]),
    group('g-conditional', '要看情況決定', '取決於對方之後會不會知道、知道後的感受', [3, 4, 5, 8]),
    group('g-oppose', '說謊就是不對', '長期會破壞信任，應該找誠實又溫和的說法', [6, 7]),
  ]
  const summaries: DbSummary[] = [
    {
      topic_id: 't-lie',
      version: 1,
      status: 'published',
      overview: '全班 8 位同學完成探究，多數認為善意的謊言「要看情況」。',
      viewpoint_summary:
        '同學大多同意說謊有代價，但在「保護對方感受」和「維持信任」之間有不同取捨：有人認為只要傷害很小就可以接受，也有人堅持應該找誠實但溫和的說法。',
      denominator: 8,
      groups,
      ungrouped_report_ids: [],
      created_at: day(12, 2),
      updated_at: day(12, 3),
    },
    {
      topic_id: 't-lie',
      version: 2,
      status: 'draft',
      overview: '全班 8 位同學完成探究，半數認為善意的謊言「要看情況」。',
      viewpoint_summary:
        '同學大多同意說謊有代價，但在「保護對方感受」和「維持信任」之間有不同取捨。支持的同學強調出發點；反對的同學擔心謊言被發現後，信任比原本的傷害更難修復；要看情況的同學則提出「對方之後會不會知道」作為判斷標準。',
      denominator: 8,
      groups,
      ungrouped_report_ids: [],
      created_at: day(13, 2),
      updated_at: day(13, 2),
    },
  ]

  const aiSettings: DbAiSettings[] = [
    {
      user_id: 'u-wang',
      api_key: 'sk-or-v1-demo-0000000000000000000003F9A',
      key_updated_at: day(4),
      default_model_id: MODELS[0]!.model_id,
      usage: {
        setup: { request_count: 18, input_tokens: 21400, output_tokens: 9800 },
        dialogue: { request_count: 352, input_tokens: 61800, output_tokens: 18350 },
        report: { request_count: 36, input_tokens: 9800, output_tokens: 3300 },
        summary: { request_count: 6, input_tokens: 3200, output_tokens: 800 },
      },
    },
  ]

  return {
    users,
    courses,
    members,
    topics,
    sessions,
    reports,
    summaries,
    aiSettings,
    models: MODELS,
  }
}

// 資料格式改了就把版本加一，舊的假資料會自動丟掉
const STORAGE_KEY = 'socratesbot-mock-db-v3'

function load(): Db {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as Db
  } catch {
    // localStorage 不能用（無痕模式等）就用初始資料
  }
  return createSeed()
}

export const db = reactive<Db>(load())

watch(
  db,
  () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(db))
    } catch {
      // 存不了就算了，只影響重新整理後的資料
    }
  },
  { deep: true },
)

export function resetDb() {
  Object.assign(db, createSeed())
}
