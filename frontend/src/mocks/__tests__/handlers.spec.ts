import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { setupServer } from 'msw/node'
import { finishTopicForClass } from '../actions'
import { completeSession, handlers } from '../handlers'
import { db, resetDb } from '../db'
import { resetScenarios, scenarios } from '../scenarios'

const server = setupServer(...handlers)
const API = 'http://localhost:8000/api/v1'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())
beforeEach(() => {
  resetDb()
  resetScenarios()
  scenarios.latency = 0
  scenarios.typingSpeed = 0
})
afterEach(() => server.resetHandlers())

async function call(path: string, init: RequestInit & { token?: string } = {}) {
  const headers = new Headers(init.headers)
  if (init.token) headers.set('Authorization', `Bearer ${init.token}`)
  if (init.body) headers.set('Content-Type', 'application/json')
  const res = await fetch(`${API}${path}`, { ...init, headers })
  const text = await res.text()
  return { res, data: text ? JSON.parse(text) : null }
}

async function login(account: string, password = 'password123') {
  const { res, data } = await call('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ account_id: account, password }),
  })
  return { res, data, token: (res.headers.get('Authorization') ?? '').replace('Bearer ', '') }
}

describe('假後端（v0.2）', () => {
  it('登入用 account_id，token 放在 Authorization header', async () => {
    const { res, data, token } = await login('wang')
    expect(res.status).toBe(200)
    expect(token).toMatch(/^mock-token\./)
    expect(data).toMatchObject({ account_id: 'wang', role: ['TEACHER'] })
  })

  it('需要改密碼的老師，改完之前其他 API 會回 403', async () => {
    const { token } = await login('chen')
    const before = await call('/courses', { token })
    expect(before.res.status).toBe(403)
    const changed = await call('/auth/password', {
      method: 'PUT',
      token,
      body: JSON.stringify({ old_password: 'password123', new_password: 'newpassword1' }),
    })
    expect(changed.res.status).toBe(200)
    expect((await call('/courses', { token })).res.status).toBe(200)
  })

  it('課程列表依身分回傳 my_role；學生看不到學生人數', async () => {
    const teacher = await login('wang')
    const { data: courses } = await call('/courses', { token: teacher.token })
    expect(courses[0]).toMatchObject({ my_role: 'teacher', student_count: 10 })
    const ta = await login('s011')
    const { data: taCourses } = await call('/courses', { token: ta.token })
    expect(taCourses.find((c: { course_id: string }) => c.course_id === 'c-phil')).toMatchObject({
      my_role: 'ta',
      my_permissions: ['view_members', 'view_reports'],
    })
    const student = await login('s001')
    const { data: mine } = await call('/courses', { token: student.token })
    expect(mine[0].student_count).toBeNull()
  })

  it('學生看不到草稿（setup）的活動', async () => {
    const { token } = await login('s001')
    const { data } = await call('/courses/c-phil/topics', { token })
    expect(data.topics.map((t: { topic_status: string }) => t.topic_status)).not.toContain('setup')
    const teacher = await login('wang')
    const { data: all } = await call('/courses/c-phil/topics', { token: teacher.token })
    expect(all.topics.map((t: { topic_status: string }) => t.topic_status)).toContain('setup')
  })

  it('refine 帶畫面上的 setup，結果只回傳、不存檔；發布帶 setup 才存', async () => {
    const { token } = await login('wang')
    const { data: before } = await call('/topics/t-free/setup', { token })
    const edited = { ...before.setup, core_question: '畫面上改過、還沒存的問題' }
    const { data: refined } = await call('/topics/t-free/setup/refine', {
      method: 'POST',
      token,
      body: JSON.stringify({ setup: edited, feedback: '精簡一點' }),
    })
    expect(refined.setup.core_question).toBe('畫面上改過、還沒存的問題')
    const { data: saved } = await call('/topics/t-free/setup', { token })
    expect(saved.setup.core_question).toBe(before.setup.core_question)
    const { data: published } = await call('/topics/t-free/publish', {
      method: 'POST',
      token,
      body: JSON.stringify({ setup: edited }),
    })
    expect(published).toMatchObject({ topic_status: 'conversation' })
    expect(published.setup.core_question).toBe('畫面上改過、還沒存的問題')
  })

  it('情境：空資料、錯誤只影響指定的 API 群組', async () => {
    const { token } = await login('s001')
    scenarios.groups.courses = 'empty'
    expect((await call('/courses', { token })).data).toEqual([])
    scenarios.groups.courses = 'error'
    expect((await call('/courses', { token })).res.status).toBe(500)
    expect((await call('/users/me', { token })).res.status).toBe(200)
  })

  it('對話串流：逐段回傳文字，done 事件帶 completed_turns', async () => {
    const { token } = await login('s004')
    const { data: session } = await call('/topics/t-ai/sessions', { method: 'POST', token })
    const res = await fetch(`${API}/sessions/${session.session_id}/messages/stream`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: '我覺得要看情況', request_id: 'r1' }),
    })
    expect(res.headers.get('Content-Type')).toContain('text/event-stream')
    const text = await res.text()
    expect(text).toContain('data: ')
    const done = JSON.parse(text.split('event: done\ndata: ')[1] ?? '{}')
    expect(done).toMatchObject({ completed_turns: 1, is_completed: false })
    const { data: history } = await call(`/sessions/${session.session_id}/messages`, { token })
    expect(history).toMatchObject({ completed_turns: 1, max_turns: 10 })
    expect(history.messages).toHaveLength(3)
  })

  it('個人報告：結束對話時自動開始產生；POST 沿用同一份、GET 輪詢', async () => {
    const { token } = await login('s004')
    const { data: session } = await call('/topics/t-ai/sessions', { method: 'POST', token })
    const path = `/sessions/${session.session_id}/report`
    expect((await call(path, { token })).res.status).toBe(409)
    expect((await call(path, { method: 'POST', token })).data.detail).toBe(
      'Dialogue is not report-eligible',
    )

    completeSession(db.sessions.find((s) => s.id === session.session_id)!)
    expect((await call(path, { token })).data).toMatchObject({ report_status: 'processing' })
    const readyAt = db.reports.find((r) => r.session_id === session.session_id)!.ready_at
    await call(path, { method: 'POST', token })
    expect(db.reports.filter((r) => r.session_id === session.session_id)).toHaveLength(1)
    expect(db.reports.find((r) => r.session_id === session.session_id)!.ready_at).toBe(readyAt)

    const other = await login('s005')
    expect((await call(path, { token: other.token })).res.status).toBe(404)
  })

  it('結束規則：達成目標問學生、回答 3 次後可以提早結束、回合用完自動結束', async () => {
    const { token } = await login('s004')
    const { data: session } = await call('/topics/t-ai/sessions', { method: 'POST', token })
    const id = session.session_id
    const send = async (content: string) => {
      const res = await fetch(`${API}/sessions/${id}/messages/stream`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, request_id: crypto.randomUUID() }),
      })
      const text = await res.text()
      return JSON.parse(text.split('event: done\ndata: ')[1]!.split('\n')[0]!)
    }
    const end = (action: string) =>
      call(`/sessions/${id}/end`, { method: 'POST', token, body: JSON.stringify({ action }) })

    await send('短')
    expect((await end('finish')).data.detail).toBe('Finish early requires three student answers')
    expect((await end('complete')).data.detail).toBe('Inquiry goal is not met')
    await send('短')
    const third = await send('我覺得要看情況，因為說謊可能會破壞彼此的信任')
    expect(third).toMatchObject({
      session_status: 'open',
      awaiting_end_consent: true,
      goal_reached: true,
      can_finish_early: true,
    })
    expect((await end('continue')).data).toMatchObject({ session_status: 'open' })
    const { data: history } = await call(`/sessions/${id}/messages`, { token })
    expect(history).toMatchObject({ awaiting_end_consent: false, goal_reached: true })

    const max = db.topics.find((t) => t.id === 't-ai')!.setup.max_turns
    let last = third
    for (let turn = 4; turn <= max; turn += 1) last = await send('短')
    expect(last).toMatchObject({
      session_status: 'ended',
      ending_reason: 'turn_limit',
      report_eligible: true,
      awaiting_end_consent: false,
      is_completed: false,
    })
    expect((await end('continue')).data.detail).toBe('Dialogue has already ended')
    const { data: report } = await call(`/sessions/${id}/report`, { token })
    expect(report.report_status).toBe('processing')
  })

  it('提早結束：沒達成目標也有報告，證據標成部分不足', async () => {
    const { token } = await login('s004')
    const { data: session } = await call('/topics/t-ai/sessions', { method: 'POST', token })
    const dbSession = db.sessions.find((s) => s.id === session.session_id)!
    for (let i = 0; i < 3; i += 1) {
      dbSession.messages.push({ id: `x${i}`, sender: 'student', content: '短', created_at: '' })
    }
    const { data } = await call(`/sessions/${session.session_id}/end`, {
      method: 'POST',
      token,
      body: JSON.stringify({ action: 'finish' }),
    })
    expect(data).toMatchObject({
      session_status: 'ended',
      ending_reason: 'student_requested_stop',
      goal_reached: false,
      report_eligible: true,
    })
    const report = db.reports.find((r) => r.session_id === session.session_id)!.report
    expect(report).toMatchObject({
      completion_reason: 'student_requested_stop',
      goal_reached: false,
      evidence_status: 'partial',
    })
    expect(report.limitations).toBeTruthy()
  })

  it('老師結束對話（#272）：要確認進行中的對話；沒回答的學生也有報告但不算進分母', async () => {
    const student = await login('s004')
    const { data: session } = await call('/topics/t-ai/sessions', {
      method: 'POST',
      token: student.token,
    })
    const { token } = await login('wang')
    const status = await call('/topics/t-ai/conversation-status', { token })
    expect(status.data).toMatchObject({ topic_status: 'conversation', confirmation_required: true })
    expect(status.data.open_dialogue_count).toBeGreaterThan(0)
    expect((await call('/topics/t-ai/summary', { method: 'POST', token })).res.status).toBe(409)

    const unconfirmed = await call('/topics/t-ai/end-conversation', {
      method: 'POST',
      token,
      body: JSON.stringify({}),
    })
    expect(unconfirmed.res.status).toBe(409)
    expect(unconfirmed.data.detail.code).toBe('open_dialogues_confirmation_required')

    const ended = await call('/topics/t-ai/end-conversation', {
      method: 'POST',
      token,
      body: JSON.stringify({ confirm_open_dialogues: true }),
    })
    expect(ended.data).toMatchObject({
      topic_status: 'summary',
      stage2_closed: true,
      open_dialogue_count: 0,
      preparation_status: 'processing',
    })
    expect((await call('/topics/t-ai/summary', { token })).data).toMatchObject({
      summary: null,
      preparation_status: 'processing',
    })

    // 時間快轉：報告和摘要都整理好
    for (const r of db.reports) r.ready_at = 0
    db.topics.find((t) => t.id === 't-ai')!.preparation!.ready_at = 0
    const summary = await call('/topics/t-ai/summary', { token })
    expect(summary.data.preparation_status).toBe('ready')
    const report = await call(`/sessions/${session.session_id}/report`, { token: student.token })
    expect(report.data.report).toMatchObject({
      completed_turns: 0,
      evidence_status: 'insufficient',
      completion_reason: 'teacher_ended_stage2',
      timeline: [],
    })
    const reportIds = summary.data.summary.groups.flatMap(
      (g: { report_ids: string[] }) => g.report_ids,
    )
    expect(reportIds).not.toContain(report.data.report.report_id)
  })

  it('摘要：審閱帶文字、只發布最新的已審閱版本；學生看得到發布版', async () => {
    const { token } = await login('wang')
    const { data: latest } = await call('/topics/t-lie/summary', { token })
    expect(latest).toMatchObject({
      published_version: 1,
      summary: { version: 2, summary_status: 'draft' },
    })
    const blocked = await call('/topics/t-lie/summary/publish', { method: 'POST', token })
    expect(blocked.res.status).toBe(400)
    const text = { overview: '新的總覽', viewpoint_summary: latest.summary.viewpoint_summary }
    const { data: reviewed } = await call('/topics/t-lie/summary/review', {
      method: 'POST',
      token,
      body: JSON.stringify(text),
    })
    expect(reviewed).toMatchObject({ version: 3, summary_status: 'reviewed' })
    const { data: published } = await call('/topics/t-lie/summary/publish', {
      method: 'POST',
      token,
    })
    expect(published).toMatchObject({ version: 3, summary_status: 'published' })
    const student = await login('s001')
    const { data: pub } = await call('/topics/t-lie/summary/published', { token: student.token })
    expect(pub.summary.overview).toBe('新的總覽')
  })

  it('對話 API 回小寫狀態（open／completed）；再進入同一題沿用同一段對話', async () => {
    const { token } = await login('s004')
    const { data: created } = await call('/topics/t-ai/sessions', { method: 'POST', token })
    expect(created.session_status).toBe('open')
    const again = await call('/topics/t-ai/sessions', { method: 'POST', token })
    expect(again.data).toMatchObject({ session_id: created.session_id, session_status: 'open' })
    completeSession(db.sessions.find((s) => s.id === created.session_id)!)
    const { data: history } = await call(`/sessions/${created.session_id}/messages`, { token })
    expect(history.session_status).toBe('completed')
    const reply = await call(`/sessions/${created.session_id}/messages/stream`, {
      method: 'POST',
      token,
      body: JSON.stringify({ content: '再說一句', request_id: 'r2' }),
    })
    expect(reply.res.status).toBe(409)
    expect(reply.data.detail).toBe('Dialogue is not accepting replies')
  })

  it('全班報告：每一筆是 { report_status, report, student_display_name }', async () => {
    finishTopicForClass('t-ai')
    const { token } = await login('wang')
    const { data } = await call('/topics/t-ai/reports', { token })
    expect(data).not.toHaveProperty('groups')
    expect(data.reports.length).toBeGreaterThan(0)
    expect(Object.keys(data.reports[0]).sort()).toEqual([
      'report',
      'report_status',
      'student_display_name',
    ])
  })

  it('指派助教：check: true 只回傳姓名、不寫入；不能指派的帳號回錯誤', async () => {
    const { token } = await login('wang')
    const before = db.members.filter((m) => m.course_id === 'c-phil' && m.role === 'ta').length
    const checked = await call('/courses/c-phil/tas', {
      method: 'POST',
      token,
      body: JSON.stringify({ account_id: 's001', check: true }),
    })
    expect(checked.res.status).toBe(200)
    expect(checked.data).toMatchObject({ account_id: 's001', message: 'TA can be assigned' })
    expect(checked.data.name).toBeTruthy()
    expect(db.members.filter((m) => m.course_id === 'c-phil' && m.role === 'ta')).toHaveLength(
      before,
    )
    const teacher = await call('/courses/c-phil/tas', {
      method: 'POST',
      token,
      body: JSON.stringify({ account_id: 'chen', check: true }),
    })
    expect(teacher.data.detail).toBe('Teacher accounts cannot be TAs')
    const already = await call('/courses/c-phil/tas', {
      method: 'POST',
      token,
      body: JSON.stringify({ account_id: 's011', check: true }),
    })
    expect(already.data.detail).toBe('Already a TA of this course')
  })

  it('課程列表跟真後端一樣回傳舊的 status：老師結束對話後還是 IN_PROGRESS', async () => {
    const student = await login('s004')
    await call('/topics/t-ai/sessions', { method: 'POST', token: student.token })
    const { token } = await login('wang')
    await call('/topics/t-ai/end-conversation', {
      method: 'POST',
      token,
      body: JSON.stringify({ confirm_open_dialogues: true }),
    })
    const { data } = await call('/courses/c-phil/topics', { token: student.token })
    const topic = data.topics.find((t: { topic_id: string }) => t.topic_id === 't-ai')
    expect(topic).toMatchObject({ topic_status: 'summary', session_status: 'IN_PROGRESS' })
    expect(topic.session_id).toBeTruthy()
  })

  it('Debug「讓全班完成」：每位學生都有完成的對話', async () => {
    finishTopicForClass('t-ai')
    const { token } = await login('wang')
    const { data } = await call('/courses/c-phil/topics', { token })
    const topic = data.topics.find((t: { topic_id: string }) => t.topic_id === 't-ai')
    expect(topic).toMatchObject({ answered_count: 10, student_count: 10 })
  })
})
