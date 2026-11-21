/**
 * 假後端：用 MSW 在瀏覽器攔截 /api/v1/... 的請求，回傳假資料。
 * 前端程式完全不用改，後端做好後把 VITE_USE_MOCK 關掉就會打真的 API。
 *
 * 路徑和回傳格式照 docs/API功能規格.md v0.2。
 * 規格還沒定案的地方照前端採用的做法（見 docs/頁面API對照.md），例如：
 *   refine 帶畫面上的 setup、AI 產生的結果不存檔；發布題目帶 setup。
 * 錯誤訊息用後端的英文原文，畫面上會由 lib/utils.ts 翻成中文。
 */
import { delay, http, HttpResponse } from 'msw'
import type { CourseRole, TaPermission } from '@/api/courses'
import type { EndAction } from '@/api/sessions'
import type { TopicSetup } from '@/api/topics'
import { USAGE_STAGES, type UsageStage } from '@/api/ai'
import { mockOpening, mockRefine, mockReply, mockReport, mockSetup } from './ai'
import {
  db,
  DEMO_PASSWORD,
  newId,
  newInviteCode,
  secureRandomString,
  type DbCourse,
  type DbRole,
  type DbSession,
  type DbSummary,
  type DbTopic,
  type DbUser,
} from './db'
import { scenarios, type ApiGroup } from './scenarios'

const BASE = '*/api/v1'

type Method = 'get' | 'post' | 'put' | 'patch' | 'delete'
interface Info {
  request: Request
  params: Record<string, string | undefined>
  /** 情境設成「空資料」時為 true（只有 GET） */
  empty: boolean
}

// ---------- 共用小工具 ----------

function fail(status: number, detail: unknown) {
  return HttpResponse.json({ detail }, { status })
}

function validationError(field: string, msg: string) {
  return fail(422, [{ loc: ['body', field], msg, type: 'value_error' }])
}

const noContent = () => new HttpResponse(null, { status: 204 })

async function body<T>(request: Request): Promise<Partial<T>> {
  try {
    return (await request.json()) as Partial<T>
  } catch {
    return {}
  }
}

const now = () => new Date().toISOString()
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

function tokenFor(user: DbUser) {
  return `mock-token.${user.id}`
}

function userFromRequest(request: Request): DbUser | undefined {
  const header = request.headers.get('Authorization') ?? ''
  const id = header.replace(/^Bearer\s+mock-token\./, '')
  return db.users.find((u) => u.id === id)
}

const PASSWORD_CHANGE_EXEMPT = ['/users/me', '/auth/password', '/auth/logout']

/** 檢查登入與全域角色；回傳錯誤 Response 或使用者 */
function authorize(request: Request, roles?: DbRole[]): DbUser | Response {
  const user = userFromRequest(request)
  if (!user) return fail(401, 'Not authenticated or token expired')
  const path = new URL(request.url).pathname
  if (user.must_change_password && !PASSWORD_CHANGE_EXEMPT.some((p) => path.endsWith(p))) {
    return fail(403, 'Password change required')
  }
  if (roles && !roles.includes(user.role)) {
    if (roles.includes('SUPERADMIN')) return fail(403, 'Admin privileges required')
    if (roles.includes('TEACHER')) return fail(403, 'Teacher privileges required')
    return fail(403, 'Student privileges required')
  }
  return user
}

function route(
  group: ApiGroup | null,
  method: Method,
  path: string,
  resolver: (info: Info) => unknown,
) {
  return http[method](`${BASE}${path}`, async (info) => {
    const mode = group ? scenarios.groups[group] : 'normal'
    await delay(scenarios.latency)
    if (mode === 'pending') await delay('infinite')
    if (mode === 'slow') await delay(3000)
    if (mode === 'error') return fail(500, 'Internal Server Error')
    const params = info.params as Info['params']
    const empty = mode === 'empty' && method === 'get'
    return (await resolver({ request: info.request, params, empty })) as Response
  })
}

function generatePassword() {
  return secureRandomString('abcdefghjkmnpqrstuvwxyz23456789', 10)
}

/** 後端的 role 是陣列（例如管理員是 ["SUPERADMIN", "TEACHER"]） */
function profile(user: DbUser) {
  return {
    account_id: user.account_id,
    name: user.name,
    role: user.role === 'SUPERADMIN' ? ['SUPERADMIN', 'TEACHER'] : [user.role],
    preferred_language: user.preferred_language,
    must_change_password: user.must_change_password,
  }
}

// ---------- 課程身分與權限 ----------

const userById = (id: string) => db.users.find((u) => u.id === id)

function membership(
  user: DbUser,
  course: DbCourse,
): { role: CourseRole; permissions: TaPermission[] } | null {
  if (course.teacher_id === user.id) return { role: 'teacher', permissions: [] }
  const m = db.members.find((x) => x.course_id === course.id && x.user_id === user.id)
  return m ? { role: m.role, permissions: m.role === 'ta' ? [...m.permissions] : [] } : null
}

const studentsOf = (courseId: string) =>
  db.members.filter((m) => m.course_id === courseId && m.role === 'student')

/** 老師，或有指定權限的助教 */
function canDo(
  access: { role: CourseRole; permissions: TaPermission[] },
  permission?: TaPermission,
) {
  if (access.role === 'teacher') return true
  return access.role === 'ta' && !!permission && access.permissions.includes(permission)
}

/** 找課程並確認是成員：回傳 [課程, 身分] 或錯誤 */
function courseFor(user: DbUser, courseId: string | undefined) {
  const course = db.courses.find((c) => c.id === courseId)
  const access = course && membership(user, course)
  if (!course || !access) return fail(404, 'Course not found')
  return [course, access] as const
}

function topicFor(user: DbUser, topicId: string | undefined) {
  const topic = db.topics.find((t) => t.id === topicId)
  if (!topic) return fail(404, 'Topic not found')
  const found = courseFor(user, topic.course_id)
  if (found instanceof Response) return fail(404, 'Topic not found')
  return [topic, found[0], found[1]] as const
}

const sessionsOf = (topicId: string) => db.sessions.filter((s) => s.topic_id === topicId)
/** 對話 API 回傳的狀態是小寫的 outcome（open／completed／…），課程題目列表才用 IN_PROGRESS／COMPLETED */
const dialogueStatus = (session: DbSession) =>
  session.status === 'COMPLETED' ? 'completed' : 'open'
const reportOf = (sessionId: string) => db.reports.find((r) => r.session_id === sessionId)
const turnsOf = (session: DbSession) =>
  session.messages.filter((m) => m.sender === 'student').length

function courseJson(course: DbCourse, access: { role: CourseRole; permissions: TaPermission[] }) {
  const canSeeCount = canDo(access, 'view_members')
  return {
    course_id: course.id,
    name: course.name,
    description: course.description,
    teacher_name: userById(course.teacher_id)?.name ?? '',
    topic_count: db.topics.filter(
      (t) => t.course_id === course.id && (access.role !== 'student' || t.status !== 'setup'),
    ).length,
    my_role: access.role,
    my_permissions: access.permissions,
    invite_code: course.invite_code,
    student_count: canSeeCount ? studentsOf(course.id).length : null,
  }
}

function topicJson(topic: DbTopic, user: DbUser, role: CourseRole) {
  const base = {
    topic_id: topic.id,
    title: topic.setup.topic,
    description: topic.setup.core_question,
    topic_status: topic.status,
    age_band: topic.setup.age_band,
    max_turns: topic.setup.max_turns,
  }
  if (role === 'student') {
    const session = sessionsOf(topic.id).find((s) => s.student_id === user.id)
    return { ...base, session_status: session?.status ?? null, session_id: session?.id ?? null }
  }
  const completed = sessionsOf(topic.id).filter((s) => s.status === 'COMPLETED').length
  return { ...base, answered_count: completed, student_count: studentsOf(topic.course_id).length }
}

function setupJson(topic: DbTopic) {
  return {
    topic_id: topic.id,
    course_id: topic.course_id,
    topic_status: topic.status,
    model_id: topic.model_id,
    setup: { ...topic.setup },
  }
}

const AGE_BANDS = ['13-15', '16-18', 'university_plus']
const MAX_TURNS = [5, 10, 15]

/** 檢查八欄：回傳錯誤 Response 或乾淨的 setup */
function checkSetup(raw: Partial<TopicSetup> | undefined, requireComplete: boolean) {
  if (!raw) return validationError('setup', 'Field required')
  if (!AGE_BANDS.includes(String(raw.age_band)))
    return validationError('age_band', 'Invalid age band')
  if (!MAX_TURNS.includes(Number(raw.max_turns)))
    return validationError('max_turns', 'Invalid max turns')
  const text = (key: keyof TopicSetup) => String(raw[key] ?? '').trim()
  if (requireComplete) {
    for (const key of [
      'topic',
      'core_question',
      'inquiry_focus',
      'background_info',
      'exclusions',
    ] as const) {
      if (!text(key)) return fail(422, { message: 'Setup is incomplete', missing: [key] })
    }
  }
  return {
    age_band: raw.age_band,
    max_turns: Number(raw.max_turns),
    topic: text('topic'),
    core_question: text('core_question'),
    inquiry_focus: text('inquiry_focus'),
    background_info: text('background_info'),
    exclusions: text('exclusions') || '未指定',
    opening_message: text('opening_message'),
  } as TopicSetup
}

function useAi(user: DbUser, stage: UsageStage, input: number, output: number) {
  const settings = aiSettingsOf(user)
  settings.usage[stage].request_count += 1
  settings.usage[stage].input_tokens += input
  settings.usage[stage].output_tokens += output
}

function aiSettingsOf(user: DbUser) {
  let settings = db.aiSettings.find((s) => s.user_id === user.id)
  if (!settings) {
    settings = {
      user_id: user.id,
      api_key: null,
      key_updated_at: null,
      default_model_id: db.models[0]!.model_id,
      usage: {
        setup: { request_count: 0, input_tokens: 0, output_tokens: 0 },
        dialogue: { request_count: 0, input_tokens: 0, output_tokens: 0 },
        report: { request_count: 0, input_tokens: 0, output_tokens: 0 },
        summary: { request_count: 0, input_tokens: 0, output_tokens: 0 },
      },
    }
    db.aiSettings.push(settings)
  }
  return settings
}

function modelRef(modelId: string) {
  const model = db.models.find((m) => m.model_id === modelId)
  return model ? { id: model.model_id, name: model.name } : null
}

function maskKey(key: string | null) {
  return key ? `sk-or-****${key.slice(-4)}` : null
}

// ---------- 摘要 ----------

const summariesOf = (topicId: string) =>
  db.summaries.filter((s) => s.topic_id === topicId).sort((a, b) => a.version - b.version)
const latestSummary = (topicId: string) => summariesOf(topicId).slice(-1)[0]
const publishedSummary = (topicId: string) =>
  summariesOf(topicId).find((s) => s.status === 'published')

function summaryJson(s: DbSummary) {
  return {
    summary_id: `sum-${s.topic_id}-${s.version}`,
    version: s.version,
    summary_status: s.status,
    overview: s.overview,
    viewpoint_summary: s.viewpoint_summary,
    denominator: s.denominator,
    groups: s.groups,
    ungrouped_report_ids: s.ungrouped_report_ids,
    created_at: s.created_at,
    updated_at: s.updated_at,
  }
}

function teacherSummaryJson(topic: DbTopic, summary: DbSummary | undefined) {
  return {
    topic_status: topic.status,
    published_version: publishedSummary(topic.id)?.version ?? null,
    summary: summary ? summaryJson(summary) : null,
  }
}

/** 依報告的最終觀點分群，產生新的摘要草稿 */
function draftSummary(topic: DbTopic, previous: DbSummary | undefined): DbSummary {
  const ready = sessionsOf(topic.id)
    .map((s) => reportOf(s.id))
    .filter((r) => r && !r.failed && r.ready_at <= Date.now())
    .map((r) => r!.report)
  const byView = new Map<string, string[]>()
  for (const report of ready) {
    const key = report.final_viewpoint ?? '未分類'
    byView.set(key, [...(byView.get(key) ?? []), report.report_id])
  }
  const total = ready.length
  const groups = [...byView.entries()].map(([name, ids], i) => ({
    group_id: `g-${topic.id}-${i + 1}`,
    name,
    conditions: `${ids.length} 位同學的最終立場是「${name}」`,
    count: ids.length,
    percentage: total ? Math.round((ids.length / total) * 100) : 0,
    report_ids: ids,
  }))
  const at = now()
  return {
    topic_id: topic.id,
    version: (previous?.version ?? 0) + 1,
    status: 'draft',
    overview: `全班 ${total} 位同學完成探究，分成 ${groups.length} 種觀點。`,
    viewpoint_summary:
      groups.map((g) => `${g.name}（${g.count} 人）`).join('、') || '目前還沒有可以整理的報告。',
    denominator: total,
    groups,
    ungrouped_report_ids: [],
    created_at: at,
    updated_at: at,
  }
}

// ---------- 對話 ----------

/** 對話完成。跟真後端一樣，不會自動產生個人報告（要等 POST /sessions/{id}/report） */
export function completeSession(session: DbSession) {
  session.status = 'COMPLETED'
  session.awaiting_end_consent = false
  session.completed_at = now()
}

/**
 * 開始產生個人報告（POST /sessions/{id}/report，老師的重新產生也用這個）。
 * 跟真後端一樣：正在產生或已完成就沿用那一筆；還沒有報告或上次失敗才重新產生。
 */
export function startSessionReport(session: DbSession) {
  const existing = reportOf(session.id)
  if (existing) {
    if (existing.failed) {
      existing.failed = false
      existing.ready_at = Date.now() + 4000
    }
    return
  }
  const topic = db.topics.find((t) => t.id === session.topic_id)!
  const index = db.sessions.filter((s) => s.topic_id === topic.id).indexOf(session) + 1
  db.reports.push({
    session_id: session.id,
    // 報告要等 4 秒才「產生完成」，前端可以看到「產生中」的畫面
    ready_at: Date.now() + 4000,
    failed: false,
    report: mockReport({
      sessionId: session.id,
      topic,
      messages: session.messages,
      anonymousId: `學生 ${String.fromCharCode(64 + Math.min(index, 26))}`,
      completedAt: session.completed_at ?? now(),
    }),
  })
}

/** 沒有報告（還沒人開始產生）時回 null */
function reportJson(sessionId: string) {
  const report = reportOf(sessionId)
  if (!report) return null
  if (report.failed) return { report_status: 'failed', report: null }
  if (report.ready_at > Date.now()) return { report_status: 'processing', report: null }
  return { report_status: 'ready', report: report.report }
}

// ---------- 路由 ----------

export const handlers = [
  // ===== 登入、註冊、帳號 =====
  route('auth', 'post', '/auth/register', async ({ request }) => {
    const data = await body<{ account_id: string; password: string; name: string }>(request)
    const account = (data.account_id ?? '').trim()
    if (!account) return validationError('account_id', 'Field required')
    if (!(data.name ?? '').trim()) return validationError('name', 'Field required')
    if ((data.password ?? '').length < 8)
      return validationError('password', 'String should have at least 8 characters')
    if (db.users.some((u) => u.account_id === account)) return fail(400, 'Account already exists')
    const user: DbUser = {
      id: newId('u'),
      account_id: account,
      name: (data.name ?? '').trim(),
      password: data.password ?? '',
      role: 'USER',
      must_change_password: false,
      preferred_language: 'zh-TW',
      created_at: now(),
    }
    db.users.push(user)
    return HttpResponse.json(
      { account_id: user.account_id, name: user.name, role: ['USER'], message: 'Registered' },
      { status: 201 },
    )
  }),

  route('auth', 'post', '/auth/login', async ({ request }) => {
    const data = await body<{ account_id: string; password: string }>(request)
    const user = db.users.find((u) => u.account_id === (data.account_id ?? '').trim())
    if (!user || user.password !== data.password) return fail(401, 'Invalid account or password')
    return HttpResponse.json(profile(user), {
      headers: { Authorization: `Bearer ${tokenFor(user)}` },
    })
  }),

  route('auth', 'post', '/auth/logout', () => HttpResponse.json({ ok: true })),

  route('auth', 'get', '/users/me', ({ request }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    return HttpResponse.json(profile(user))
  }),

  route('auth', 'put', '/auth/password', async ({ request }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const data = await body<{ old_password: string; new_password: string }>(request)
    if (data.old_password !== user.password) return fail(400, 'Old password is incorrect')
    if ((data.new_password ?? '').length < 8) {
      return validationError('new_password', 'String should have at least 8 characters')
    }
    user.password = data.new_password ?? DEMO_PASSWORD
    user.must_change_password = false
    return HttpResponse.json({ message: 'Password updated' })
  }),

  route('auth', 'patch', '/users/me/preferences', async ({ request }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const data = await body<{ preferred_language: string }>(request)
    const lang = data.preferred_language
    if (lang !== 'zh-TW' && lang !== 'en' && lang !== 'es') return fail(400, 'Invalid language')
    user.preferred_language = lang
    return HttpResponse.json({ preferred_language: lang, message: 'Preferences updated' })
  }),

  // ===== 管理員 =====
  route('admin', 'get', '/admin/teachers', ({ request, empty }) => {
    const user = authorize(request, ['SUPERADMIN'])
    if (user instanceof Response) return user
    const teachers = empty ? [] : db.users.filter((u) => u.role === 'TEACHER')
    return HttpResponse.json(
      teachers.map((t) => ({
        id: t.id,
        account_id: t.account_id,
        name: t.name,
        created_at: t.created_at,
      })),
    )
  }),

  route('admin', 'post', '/admin/teachers', async ({ request }) => {
    const admin = authorize(request, ['SUPERADMIN'])
    if (admin instanceof Response) return admin
    const data = await body<{ account_id: string; name: string }>(request)
    const account = (data.account_id ?? '').trim()
    if (!account) return validationError('account_id', 'Field required')
    if (!(data.name ?? '').trim()) return validationError('name', 'Field required')
    if (db.users.some((u) => u.account_id === account)) return fail(409, 'Account already exists')
    const password = generatePassword()
    db.users.push({
      id: newId('u'),
      account_id: account,
      name: (data.name ?? '').trim(),
      password,
      role: 'TEACHER',
      must_change_password: true,
      preferred_language: 'zh-TW',
      created_at: now(),
    })
    return HttpResponse.json(
      {
        account_id: account,
        name: (data.name ?? '').trim(),
        role: ['TEACHER'],
        password,
        message: 'Teacher created',
      },
      { status: 201 },
    )
  }),

  route('admin', 'delete', '/admin/teachers/:teacherId', ({ request, params }) => {
    const admin = authorize(request, ['SUPERADMIN'])
    if (admin instanceof Response) return admin
    const index = db.users.findIndex((u) => u.id === params.teacherId && u.role === 'TEACHER')
    if (index < 0) return fail(404, 'Teacher not found')
    db.users.splice(index, 1)
    return noContent()
  }),

  route('admin', 'post', '/admin/teachers/:teacherId/reset-password', ({ request, params }) => {
    const admin = authorize(request, ['SUPERADMIN'])
    if (admin instanceof Response) return admin
    const teacher = db.users.find((u) => u.id === params.teacherId && u.role === 'TEACHER')
    if (!teacher) return fail(404, 'Teacher not found')
    teacher.password = generatePassword()
    teacher.must_change_password = true
    return HttpResponse.json({ password: teacher.password, message: 'Password reset' })
  }),

  // ===== 課程 =====
  route('courses', 'get', '/courses', ({ request, empty }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    if (empty) return HttpResponse.json([])
    const list = db.courses
      .map((c) => [c, membership(user, c)] as const)
      .filter(([, access]) => access)
      .map(([c, access]) => courseJson(c, access!))
    return HttpResponse.json(list)
  }),

  route('courses', 'post', '/courses', async ({ request }) => {
    const user = authorize(request, ['TEACHER', 'SUPERADMIN'])
    if (user instanceof Response) return user
    const data = await body<{ name: string; description: string }>(request)
    const name = (data.name ?? '').trim()
    if (!name) return validationError('name', 'Field required')
    const course: DbCourse = {
      id: newId('c'),
      name,
      description: (data.description ?? '').trim(),
      invite_code: newInviteCode(),
      teacher_id: user.id,
      created_at: now(),
    }
    db.courses.push(course)
    return HttpResponse.json(
      { ...courseJson(course, { role: 'teacher', permissions: [] }), message: 'Course created' },
      { status: 201 },
    )
  }),

  route('courses', 'get', '/courses/:courseId', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    const [course, access] = found
    const { topic_count: _count, student_count: _students, ...json } = courseJson(course, access)
    const settings =
      access.role === 'student' ? null : aiSettingsOf(userById(course.teacher_id) ?? user)
    return HttpResponse.json({
      ...json,
      default_model: settings ? modelRef(settings.default_model_id) : null,
    })
  }),

  route('courses', 'put', '/courses/:courseId', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    const [course, access] = found
    if (access.role !== 'teacher') return fail(403, 'Not the course teacher')
    const data = await body<{ name: string; description: string }>(request)
    const name = (data.name ?? '').trim()
    if (!name) return validationError('name', 'Field required')
    course.name = name
    course.description = (data.description ?? '').trim()
    return HttpResponse.json({
      course_id: course.id,
      name: course.name,
      description: course.description,
      invite_code: course.invite_code,
      message: 'Course updated',
    })
  }),

  route('courses', 'delete', '/courses/:courseId', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const course = db.courses.find((c) => c.id === params.courseId)
    if (!course) return noContent()
    if (course.teacher_id !== user.id) return fail(403, 'Not the course teacher')
    const topicIds = db.topics.filter((t) => t.course_id === course.id).map((t) => t.id)
    const sessionIds = db.sessions.filter((s) => topicIds.includes(s.topic_id)).map((s) => s.id)
    db.reports = db.reports.filter((r) => !sessionIds.includes(r.session_id))
    db.sessions = db.sessions.filter((s) => !topicIds.includes(s.topic_id))
    db.summaries = db.summaries.filter((s) => !topicIds.includes(s.topic_id))
    db.topics = db.topics.filter((t) => t.course_id !== course.id)
    db.members = db.members.filter((m) => m.course_id !== course.id)
    db.courses = db.courses.filter((c) => c.id !== course.id)
    return noContent()
  }),

  route('courses', 'post', '/courses/join', async ({ request }) => {
    const user = authorize(request, ['USER'])
    if (user instanceof Response) return user
    const data = await body<{ invite_code: string }>(request)
    const code = (data.invite_code ?? '').trim().toUpperCase()
    if (!/^[A-Z2-9]{8}$/.test(code)) return validationError('invite_code', 'Invalid invite code')
    const course = db.courses.find((c) => c.invite_code === code)
    if (!course) return fail(404, 'Course not found')
    const access = membership(user, course)
    if (access?.role === 'student') return fail(400, 'Already enrolled in this course')
    if (access) return fail(400, 'Already a teacher or TA of this course')
    db.members.push({
      course_id: course.id,
      user_id: user.id,
      role: 'student',
      permissions: [],
      joined_at: now(),
    })
    return HttpResponse.json(
      {
        course_id: course.id,
        name: course.name,
        invite_code: course.invite_code,
        my_role: 'student',
        message: 'Joined',
      },
      { status: 201 },
    )
  }),

  route('courses', 'delete', '/courses/:courseId/member', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const m = db.members.find((x) => x.course_id === params.courseId && x.user_id === user.id)
    if (m && m.role !== 'student') return fail(403, 'Teachers and TAs cannot leave this way')
    db.members = db.members.filter((x) => x !== m)
    return noContent()
  }),

  route('topics', 'get', '/courses/:courseId/topics', ({ request, params, empty }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    const [course, access] = found
    const topics = empty
      ? []
      : db.topics
          .filter(
            (t) => t.course_id === course.id && (access.role !== 'student' || t.status !== 'setup'),
          )
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map((t) => topicJson(t, user, access.role))
    return HttpResponse.json({
      course_id: course.id,
      name: course.name,
      invite_code: course.invite_code,
      my_role: access.role,
      my_permissions: access.permissions,
      topics,
    })
  }),

  // ===== 課程名單、助教 =====
  route('members', 'get', '/courses/:courseId/members', ({ request, params, empty }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    const [course, access] = found
    const role = new URL(request.url).searchParams.get('role')
    if (role && role !== 'student' && role !== 'ta') return validationError('role', 'Invalid role')
    const allowed = role === 'student' ? canDo(access, 'view_members') : access.role === 'teacher'
    if (!allowed) return fail(403, 'Not allowed')
    const list = empty
      ? []
      : db.members
          .filter((m) => m.course_id === course.id && (!role || m.role === role))
          .map((m) => {
            const u = userById(m.user_id)
            return {
              user_id: m.user_id,
              account_id: u?.account_id ?? '',
              name: u?.name ?? '',
              role: m.role,
              joined_at: m.joined_at,
              permissions: m.role === 'ta' ? m.permissions : [],
            }
          })
    return HttpResponse.json(list)
  }),

  route('members', 'delete', '/courses/:courseId/students/:userId', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    if (found[1].role !== 'teacher') return fail(403, 'Not the course teacher')
    db.members = db.members.filter(
      (m) =>
        !(m.course_id === params.courseId && m.user_id === params.userId && m.role === 'student'),
    )
    return noContent()
  }),

  route('members', 'post', '/courses/:courseId/tas', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    const [course, access] = found
    if (access.role !== 'teacher') return fail(403, 'Course teacher required')
    const data = await body<{
      account_id: string
      permissions?: TaPermission[] | null
      check?: boolean
    }>(request)
    const account = (data.account_id ?? '').trim()
    if (!account) return validationError('account_id', 'Field required')
    const target = db.users.find((u) => u.account_id === account)
    if (!target) return fail(404, 'Account not found')
    if (target.role === 'SUPERADMIN') return fail(400, 'Admins cannot be TAs')
    if (target.role !== 'USER') return fail(400, 'Teacher accounts cannot be TAs')
    const existing = db.members.find((m) => m.course_id === course.id && m.user_id === target.id)
    if (existing?.role === 'ta') return fail(400, 'Already a TA of this course')
    const ALL: TaPermission[] = ['edit_topics', 'view_reports', 'edit_summary', 'view_members']
    // 沒給權限 = 四項全開（跟真後端一樣）
    const permissions = data.permissions ? ALL.filter((p) => data.permissions!.includes(p)) : ALL
    // check: true 只檢查、不寫入，回傳姓名給確認視窗
    if (data.check)
      return HttpResponse.json({
        user_id: target.id,
        account_id: target.account_id,
        name: target.name,
        permissions,
        message: 'TA can be assigned',
      })
    if (existing) {
      existing.role = 'ta'
      existing.permissions = permissions
    } else {
      db.members.push({
        course_id: course.id,
        user_id: target.id,
        role: 'ta',
        permissions,
        joined_at: now(),
      })
    }
    return HttpResponse.json(
      {
        user_id: target.id,
        account_id: target.account_id,
        name: target.name,
        permissions,
        message: 'TA added',
      },
      { status: 201 },
    )
  }),

  route('members', 'put', '/courses/:courseId/tas/:userId', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    if (found[1].role !== 'teacher') return fail(403, 'Not the course teacher')
    const ta = db.members.find(
      (m) => m.course_id === params.courseId && m.user_id === params.userId && m.role === 'ta',
    )
    if (!ta) return fail(404, 'TA not found')
    const data = await body<{ permissions: TaPermission[] }>(request)
    ta.permissions = data.permissions ?? []
    return HttpResponse.json({
      user_id: ta.user_id,
      permissions: ta.permissions,
      message: 'Permissions updated',
    })
  }),

  route('members', 'delete', '/courses/:courseId/tas/:userId', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    if (found[1].role !== 'teacher') return fail(403, 'Not the course teacher')
    const index = db.members.findIndex(
      (m) => m.course_id === params.courseId && m.user_id === params.userId && m.role === 'ta',
    )
    if (index < 0) return fail(404, 'TA not found')
    db.members.splice(index, 1)
    return noContent()
  }),

  // ===== 題目：建立、設定、發布 =====
  route('topics', 'get', '/inquiry-models', ({ request }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    return HttpResponse.json(db.models)
  }),

  route('setup', 'post', '/courses/:courseId/topics', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = courseFor(user, params.courseId)
    if (found instanceof Response) return found
    const [course, access] = found
    if (!canDo(access, 'edit_topics')) return fail(403, 'Not allowed')
    const data = await body<{
      age_band: string
      max_turns: number
      course_description: string
      model_id: string
    }>(request)
    if (!AGE_BANDS.includes(String(data.age_band)))
      return validationError('age_band', 'Invalid age band')
    if (!MAX_TURNS.includes(Number(data.max_turns)))
      return validationError('max_turns', 'Invalid max turns')
    const description = (data.course_description ?? '').trim()
    if (!description) return validationError('course_description', 'Field required')
    if (description.length > 6000) return validationError('course_description', 'Too long')
    await sleep(2500)
    const teacher = userById(course.teacher_id) ?? user
    const topic: DbTopic = {
      id: newId('t'),
      course_id: course.id,
      status: 'setup',
      course_description: description,
      model_id: data.model_id || aiSettingsOf(teacher).default_model_id,
      setup: mockSetup(description, data.age_band as never, Number(data.max_turns) as never),
      created_at: now(),
    }
    db.topics.push(topic)
    useAi(teacher, 'setup', 1800, 700)
    return HttpResponse.json(setupJson(topic), { status: 201 })
  }),

  route('topics', 'delete', '/topics/:topicId', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    if (found[2].role !== 'teacher') return fail(403, 'Not the course teacher')
    const topicId = found[0].id
    const sessionIds = db.sessions.filter((s) => s.topic_id === topicId).map((s) => s.id)
    db.reports = db.reports.filter((r) => !sessionIds.includes(r.session_id))
    db.sessions = db.sessions.filter((s) => s.topic_id !== topicId)
    db.summaries = db.summaries.filter((s) => s.topic_id !== topicId)
    db.topics = db.topics.filter((t) => t.id !== topicId)
    return noContent()
  }),

  route('setup', 'get', '/topics/:topicId/setup', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    if (!canDo(found[2], 'edit_topics')) return fail(403, 'Not allowed')
    return HttpResponse.json(setupJson(found[0]))
  }),

  route('setup', 'put', '/topics/:topicId/setup', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (!canDo(access, 'edit_topics')) return fail(403, 'Not allowed')
    if (topic.status !== 'setup') return fail(400, 'Topic is not in setup')
    const data = await body<{ setup: TopicSetup }>(request)
    const setup = checkSetup(data.setup, false)
    if (setup instanceof Response) return setup
    topic.setup = setup
    return HttpResponse.json({ ...setupJson(topic), message: 'Setup saved' })
  }),

  route('setup', 'post', '/topics/:topicId/setup/refine', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, course, access] = found
    if (!canDo(access, 'edit_topics')) return fail(403, 'Not allowed')
    if (topic.status !== 'setup') return fail(400, 'Topic is not in setup')
    const data = await body<{ setup: TopicSetup; feedback: string }>(request)
    const feedback = (data.feedback ?? '').trim()
    if (!feedback) return validationError('feedback', 'Field required')
    const current = checkSetup(data.setup ?? topic.setup, false)
    if (current instanceof Response) return current
    await sleep(2000)
    useAi(userById(course.teacher_id) ?? user, 'setup', 1500, 600)
    // 只回傳結果、不存檔
    return HttpResponse.json({ ...setupJson(topic), setup: mockRefine(current, feedback) })
  }),

  route('setup', 'post', '/topics/:topicId/setup/opening-message', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, course, access] = found
    if (!canDo(access, 'edit_topics')) return fail(403, 'Not allowed')
    if (topic.status !== 'setup') return fail(400, 'Topic is not in setup')
    const data = await body<{ setup: TopicSetup }>(request)
    const setup = checkSetup(data.setup, false)
    if (setup instanceof Response) return setup
    await sleep(1200)
    useAi(userById(course.teacher_id) ?? user, 'setup', 600, 120)
    return HttpResponse.json({ opening_message: mockOpening(setup) })
  }),

  route('setup', 'post', '/topics/:topicId/publish', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (access.role !== 'teacher') return fail(403, 'Not the course teacher')
    if (topic.status !== 'setup') return fail(400, 'Topic is not in setup')
    const data = await body<{ setup: TopicSetup }>(request)
    const setup = checkSetup(data.setup, true)
    if (setup instanceof Response) return setup
    topic.setup = setup
    topic.status = 'conversation'
    return HttpResponse.json({ ...setupJson(topic), message: 'Topic published' })
  }),

  route('chat', 'get', '/topics/:topicId/explanation', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (access.role === 'student' && topic.status === 'setup') return fail(404, 'Topic not found')
    return HttpResponse.json({
      topic_id: topic.id,
      title: topic.setup.topic,
      background: topic.setup.background_info,
      key_terms: [],
    })
  }),

  // ===== 對話 =====
  route('chat', 'post', '/topics/:topicId/sessions', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (access.role !== 'student') return fail(403, 'Course membership required')
    if (topic.status === 'setup') return fail(404, 'Topic is still in setup')
    // 跟真後端一樣：已經有對話就直接回傳那一段（不會報錯）
    const existing = sessionsOf(topic.id).find((s) => s.student_id === user.id)
    if (existing)
      return HttpResponse.json({
        session_id: existing.id,
        topic_id: topic.id,
        session_status: dialogueStatus(existing),
      })
    if (topic.status === 'summary') return fail(400, 'Topic is in summary')
    const session: DbSession = {
      id: newId('ss'),
      topic_id: topic.id,
      student_id: user.id,
      status: 'IN_PROGRESS',
      awaiting_end_consent: false,
      messages: [
        {
          id: newId('m'),
          sender: 'ai',
          content: topic.setup.opening_message || mockOpening(topic.setup),
          created_at: now(),
        },
      ],
      completed_at: null,
    }
    db.sessions.push(session)
    return HttpResponse.json(
      { session_id: session.id, topic_id: topic.id, session_status: dialogueStatus(session) },
      { status: 201 },
    )
  }),

  route('chat', 'get', '/sessions/:sessionId/messages', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const session = db.sessions.find((s) => s.id === params.sessionId)
    if (!session) return fail(404, 'Session not found')
    if (session.student_id !== user.id) return fail(404, 'Session not found')
    const topic = db.topics.find((t) => t.id === session.topic_id)
    return HttpResponse.json({
      messages: session.messages.map((m) => ({
        message_id: m.id,
        sender: m.sender,
        content: m.content,
        created_at: m.created_at,
      })),
      session_status: dialogueStatus(session),
      max_turns: topic?.setup.max_turns ?? 5,
      completed_turns: turnsOf(session),
      goal_reached: session.awaiting_end_consent || session.status === 'COMPLETED',
      awaiting_end_consent: session.awaiting_end_consent,
    })
  }),

  route('chat', 'post', '/sessions/:sessionId/messages/stream', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const session = db.sessions.find((s) => s.id === params.sessionId)
    if (!session) return fail(404, 'Session not found')
    if (session.student_id !== user.id) return fail(404, 'Session not found')
    const topic = db.topics.find((t) => t.id === session.topic_id)
    if (!topic) return fail(404, 'Session not found')
    if (session.status === 'COMPLETED' || topic.status === 'summary')
      return fail(409, 'Dialogue is not accepting replies')
    const data = await body<{ content: string; request_id: string }>(request)
    const content = (data.content ?? '').trim()
    if (!content) return validationError('content', 'Field required')
    if (content.length > 6000) return validationError('content', 'Too long')

    session.awaiting_end_consent = false
    session.messages.push({ id: newId('m'), sender: 'student', content, created_at: now() })
    const turns = turnsOf(session)
    const max = topic.setup.max_turns
    const isLast = turns >= max
    // AI 組還沒定「達成目標提早結束」的規則，假後端只在回合用完時結束（awaiting_end_consent 一律 false）
    const reply = mockReply(content, turns, isLast)
    const messageId = newId('m')
    const teacher = userById(db.courses.find((c) => c.id === topic.course_id)?.teacher_id ?? '')

    const encoder = new TextEncoder()
    const speed = scenarios.typingSpeed
    const stream = new ReadableStream({
      async start(controller) {
        for (let i = 0; i < reply.length; i += 2) {
          controller.enqueue(encoder.encode(`data: ${reply.slice(i, i + 2)}\n\n`))
          await sleep(speed * 2)
        }
        session.messages.push({ id: messageId, sender: 'ai', content: reply, created_at: now() })
        if (teacher) useAi(teacher, 'dialogue', 400, 120)
        if (isLast) completeSession(session)
        const done = {
          message_id: messageId,
          completed_turns: turns,
          is_completed: isLast,
          awaiting_end_consent: false,
        }
        controller.enqueue(encoder.encode(`event: done\ndata: ${JSON.stringify(done)}\n\n`))
        controller.close()
      },
    })
    return new HttpResponse(stream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    })
  }),

  route('chat', 'post', '/sessions/:sessionId/end', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const session = db.sessions.find((s) => s.id === params.sessionId)
    if (!session) return fail(404, 'Session not found')
    if (session.student_id !== user.id) return fail(404, 'Session not found')
    if (session.status === 'COMPLETED') return fail(409, 'Dialogue is not accepting replies')
    const data = await body<{ action: EndAction }>(request)
    if (data.action === 'complete') {
      if (!session.awaiting_end_consent) return fail(409, 'Inquiry goal is not met')
      completeSession(session)
    } else if (data.action === 'continue') {
      session.awaiting_end_consent = false
    } else if (data.action === 'abandon') {
      // 假後端放棄後直接刪掉，方便重新體驗（真後端會留著、狀態 abandoned，不能再回答）
      db.sessions = db.sessions.filter((s) => s !== session)
      return HttpResponse.json({
        session_id: session.id,
        session_status: 'abandoned',
        message: 'Dialogue abandoned',
      })
    } else {
      return validationError('action', 'Invalid action')
    }
    return HttpResponse.json({
      session_id: session.id,
      session_status: dialogueStatus(session),
      message: 'OK',
    })
  }),

  // ===== 個人報告 =====
  // 錯誤碼照真後端：查無對話或不是本人 404、對話未完成 409、還沒開始產生報告 404
  route('reports', 'get', '/sessions/:sessionId/report', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const session = db.sessions.find((s) => s.id === params.sessionId)
    if (!session || session.student_id !== user.id) return fail(404, 'Session not found')
    if (session.status !== 'COMPLETED') return fail(409, 'Dialogue is not completed')
    const json = reportJson(session.id)
    if (!json) return fail(404, 'Report not found')
    return HttpResponse.json(json)
  }),

  route('reports', 'post', '/sessions/:sessionId/report', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const session = db.sessions.find((s) => s.id === params.sessionId)
    if (!session || session.student_id !== user.id) return fail(404, 'Session not found')
    if (session.status !== 'COMPLETED') return fail(409, 'Dialogue is not completed')
    startSessionReport(session)
    return HttpResponse.json(reportJson(session.id))
  }),

  route('reports', 'get', '/topics/:topicId/reports', ({ request, params, empty }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, course, access] = found
    if (!canDo(access, 'view_reports')) return fail(403, 'Not allowed')
    const sessions = sessionsOf(topic.id).filter((s) => s.status === 'COMPLETED')
    // 學生還沒開始產生報告的對話不算在「產生中／失敗」裡（跟真後端一樣）
    const withReports = sessions.flatMap((session) => {
      const json = reportJson(session.id)
      return json ? [{ session, json }] : []
    })
    const statuses = withReports.map(({ json }) => json)
    // 格式照真後端：每一筆是 { report_status, report, student_display_name }，產生中、失敗的也會列出
    return HttpResponse.json({
      class_size: studentsOf(course.id).length,
      completed_count: sessions.length,
      ready_count: statuses.filter((s) => s.report_status === 'ready').length,
      processing_count: statuses.filter(
        (s) => s.report_status === 'processing' || s.report_status === 'pending',
      ).length,
      failed_count: statuses.filter((s) => s.report_status === 'failed').length,
      reports: empty
        ? []
        : withReports.map(({ session, json }) => ({
            report_status: json.report_status,
            report: json.report,
            student_display_name: userById(session.student_id)?.name ?? '',
          })),
    })
  }),

  route('reports', 'post', '/topics/:topicId/reports/:sessionId', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const session = db.sessions.find(
      (s) => s.id === params.sessionId && s.topic_id === params.topicId,
    )
    if (!session) return fail(404, 'Session not found')
    if (session.status !== 'COMPLETED') return fail(409, 'Dialogue is not completed')
    startSessionReport(session)
    return HttpResponse.json(reportJson(session.id))
  }),

  // ===== 全班摘要 =====
  route('summary', 'get', '/topics/:topicId/summary', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (!canDo(access, 'edit_summary') && !canDo(access, 'view_reports'))
      return fail(403, 'Not allowed')
    const raw = new URL(request.url).searchParams.get('version')
    if (raw === null) return HttpResponse.json(teacherSummaryJson(topic, latestSummary(topic.id)))
    const version = Number(raw)
    if (!Number.isInteger(version) || version < 1)
      return validationError('version', 'Invalid version')
    const summary = summariesOf(topic.id).find((s) => s.version === version)
    if (!summary) return fail(404, 'Summary version not found')
    return HttpResponse.json(teacherSummaryJson(topic, summary))
  }),

  route('summary', 'post', '/topics/:topicId/summary', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, course, access] = found
    if (topic.status === 'setup') return fail(400, 'Topic is still in setup')
    const allowed =
      topic.status === 'conversation' ? access.role === 'teacher' : canDo(access, 'edit_summary')
    if (!allowed) return fail(403, 'Not allowed')
    await sleep(2500)
    const draft = draftSummary(topic, latestSummary(topic.id))
    if (!draft.denominator) return fail(400, 'No ready reports')
    topic.status = 'summary'
    db.summaries.push(draft)
    useAi(userById(course.teacher_id) ?? user, 'summary', 2600, 700)
    return HttpResponse.json(teacherSummaryJson(topic, draft))
  }),

  route('summary', 'patch', '/topics/:topicId/summary', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (!canDo(access, 'edit_summary')) return fail(403, 'Not allowed')
    const latest = latestSummary(topic.id)
    if (!latest) return fail(404, 'Summary not found')
    const data = await body<{ overview: string; viewpoint_summary: string }>(request)
    const overview = (data.overview ?? '').trim()
    const viewpoint = (data.viewpoint_summary ?? '').trim()
    if (!overview) return validationError('overview', 'Field required')
    if (!viewpoint) return validationError('viewpoint_summary', 'Field required')
    let target = latest
    if (overview !== latest.overview || viewpoint !== latest.viewpoint_summary) {
      target = {
        ...latest,
        version: latest.version + 1,
        overview,
        viewpoint_summary: viewpoint,
        updated_at: now(),
      }
      db.summaries.push(target)
    }
    target.status = 'draft'
    return HttpResponse.json({ summary: summaryJson(target) })
  }),

  route('summary', 'post', '/topics/:topicId/summary/review', async ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (access.role !== 'teacher') return fail(403, 'Not the course teacher')
    const latest = latestSummary(topic.id)
    if (!latest) return fail(404, 'Summary not found')
    const data = await body<{ overview: string; viewpoint_summary: string }>(request)
    const overview = (data.overview ?? '').trim()
    const viewpoint = (data.viewpoint_summary ?? '').trim()
    if (!overview || !viewpoint) return validationError('viewpoint_summary', 'Field required')
    let target = latest
    if (overview !== latest.overview || viewpoint !== latest.viewpoint_summary) {
      target = {
        ...latest,
        version: latest.version + 1,
        overview,
        viewpoint_summary: viewpoint,
        updated_at: now(),
      }
      db.summaries.push(target)
    }
    for (const s of summariesOf(topic.id)) {
      if (s !== target && s.status === 'reviewed') s.status = 'withdrawn'
    }
    target.status = 'reviewed'
    return HttpResponse.json({
      version: target.version,
      summary_status: 'reviewed',
      message: 'Reviewed',
    })
  }),

  route('summary', 'post', '/topics/:topicId/summary/publish', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (access.role !== 'teacher') return fail(403, 'Not the course teacher')
    const latest = latestSummary(topic.id)
    if (!latest) return fail(404, 'Summary not found')
    if (latest.status !== 'reviewed') {
      return fail(400, {
        version: latest.version,
        summary_status: latest.status,
        message: 'Latest version is not reviewed',
      })
    }
    for (const s of summariesOf(topic.id)) {
      if (s.status === 'published') s.status = 'withdrawn'
    }
    latest.status = 'published'
    return HttpResponse.json({
      version: latest.version,
      summary_status: 'published',
      message: 'Published',
    })
  }),

  route('summary', 'post', '/topics/:topicId/summary/withdraw', ({ request, params }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const [topic, , access] = found
    if (access.role !== 'teacher') return fail(403, 'Not the course teacher')
    const published = publishedSummary(topic.id)
    if (!published) return fail(404, 'No published summary')
    published.status = 'withdrawn'
    return HttpResponse.json({ summary_status: 'withdrawn', message: 'Withdrawn' })
  }),

  route('summary', 'get', '/topics/:topicId/summary/published', ({ request, params, empty }) => {
    const user = authorize(request)
    if (user instanceof Response) return user
    const found = topicFor(user, params.topicId)
    if (found instanceof Response) return found
    const published = publishedSummary(found[0].id)
    if (!published || empty) return HttpResponse.json({ summary: null })
    const grouped = published.groups.reduce((n, g) => n + g.count, 0)
    const ungrouped = Math.max(0, published.denominator - grouped)
    return HttpResponse.json({
      summary: {
        overview: published.overview,
        viewpoint_summary: published.viewpoint_summary,
        groups: published.groups.map(({ name, conditions, count, percentage }) => ({
          name,
          conditions,
          count,
          percentage,
        })),
        ungrouped_count: ungrouped,
        ungrouped_percentage: published.denominator
          ? Math.round((ungrouped / published.denominator) * 100)
          : 0,
        denominator: published.denominator,
      },
    })
  }),

  // ===== AI 金鑰與用量 =====
  route('ai', 'get', '/users/me/ai/usage', ({ request, empty }) => {
    const user = authorize(request, ['TEACHER', 'SUPERADMIN'])
    if (user instanceof Response) return user
    const settings = aiSettingsOf(user)
    const model = db.models.find((m) => m.model_id === settings.default_model_id) ?? db.models[0]!
    const cost = (input: number, output: number) =>
      (input * model.input_price_usd + output * model.output_price_usd) / 1_000_000
    const stages = USAGE_STAGES.map(({ value }) => {
      const u = empty
        ? { request_count: 0, input_tokens: 0, output_tokens: 0 }
        : settings.usage[value]
      return {
        stage: value,
        request_count: u.request_count,
        total_tokens: u.input_tokens + u.output_tokens,
        input_tokens: u.input_tokens,
        output_tokens: u.output_tokens,
        cost_usd: u.request_count ? cost(u.input_tokens, u.output_tokens) : null,
      }
    })
    const input = stages.reduce((n, s) => n + s.input_tokens, 0)
    const output = stages.reduce((n, s) => n + s.output_tokens, 0)
    const requests = stages.reduce((n, s) => n + s.request_count, 0)
    return HttpResponse.json({
      month: now().slice(0, 7),
      total_tokens: input + output,
      input_tokens: input,
      output_tokens: output,
      request_count: requests,
      by_stage: stages,
      cost_usd: requests ? cost(input, output) : null,
      cost_source: requests ? 'estimate' : null,
      updated_at: requests ? now() : null,
    })
  }),

  route('ai', 'get', '/users/me/ai/settings', ({ request }) => {
    const user = authorize(request, ['TEACHER', 'SUPERADMIN'])
    if (user instanceof Response) return user
    const settings = aiSettingsOf(user)
    return HttpResponse.json({
      configured: !!settings.api_key,
      masked_key: maskKey(settings.api_key),
      updated_at: settings.key_updated_at,
      default_model: modelRef(settings.default_model_id),
    })
  }),

  route('ai', 'put', '/users/me/ai/api-key', async ({ request }) => {
    const user = authorize(request, ['TEACHER', 'SUPERADMIN'])
    if (user instanceof Response) return user
    const data = await body<{ api_key: string }>(request)
    const key = (data.api_key ?? '').trim()
    if (!/^sk-or-\S{8,}$/.test(key)) return validationError('api_key', 'Invalid API key format')
    const settings = aiSettingsOf(user)
    settings.api_key = key
    settings.key_updated_at = now()
    return HttpResponse.json({
      configured: true,
      masked_key: maskKey(key),
      updated_at: settings.key_updated_at,
    })
  }),

  route('ai', 'delete', '/users/me/ai/api-key', ({ request }) => {
    const user = authorize(request, ['TEACHER', 'SUPERADMIN'])
    if (user instanceof Response) return user
    const settings = aiSettingsOf(user)
    settings.api_key = null
    settings.key_updated_at = now()
    return noContent()
  }),

  route('ai', 'patch', '/users/me/ai/model', async ({ request }) => {
    const user = authorize(request, ['TEACHER', 'SUPERADMIN'])
    if (user instanceof Response) return user
    const data = await body<{ model_id: string }>(request)
    const model = modelRef(data.model_id ?? '')
    if (!model) return validationError('model_id', 'Invalid model')
    aiSettingsOf(user).default_model_id = model.id
    return HttpResponse.json({ default_model: model, message: 'Default model updated' })
  }),
]
