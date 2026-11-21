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

  it('個人報告：結束對話不會自動產生，要 POST 才開始；重複 POST 沿用同一份', async () => {
    const { token } = await login('s004')
    const { data: session } = await call('/topics/t-ai/sessions', { method: 'POST', token })
    const path = `/sessions/${session.session_id}/report`
    expect((await call(path, { token })).res.status).toBe(409)
    expect((await call(path, { method: 'POST', token })).res.status).toBe(409)

    completeSession(db.sessions.find((s) => s.id === session.session_id)!)
    const before = await call(path, { token })
    expect(before.res.status).toBe(404)
    expect(before.data.detail).toBe('Report not found')

    const started = await call(path, { method: 'POST', token })
    expect(started.data).toMatchObject({ report_status: 'processing', report: null })
    const readyAt = db.reports.find((r) => r.session_id === session.session_id)!.ready_at
    await call(path, { method: 'POST', token })
    expect(db.reports.filter((r) => r.session_id === session.session_id)).toHaveLength(1)
    expect(db.reports.find((r) => r.session_id === session.session_id)!.ready_at).toBe(readyAt)
    expect((await call(path, { token })).data.report_status).toBe('processing')

    const other = await login('s005')
    expect((await call(path, { token: other.token })).res.status).toBe(404)
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

  it('Debug「讓全班完成」：每位學生都有完成的對話', async () => {
    finishTopicForClass('t-ai')
    const { token } = await login('wang')
    const { data } = await call('/courses/c-phil/topics', { token })
    const topic = data.topics.find((t: { topic_id: string }) => t.topic_id === 't-ai')
    expect(topic).toMatchObject({ answered_count: 10, student_count: 10 })
  })
})
