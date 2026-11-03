import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { setupServer } from 'msw/node'
import { addManyConclusions, finishTopicForClass } from '../actions'
import { handlers } from '../handlers'
import { resetDb } from '../db'
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
    body: JSON.stringify({ account, password }),
  })
  return { res, data, token: (res.headers.get('Authorization') ?? '').replace('Bearer ', '') }
}

describe('假後端', () => {
  it('登入用後端的角色名稱，token 放在 Authorization header', async () => {
    const { res, data, token } = await login('s001')
    expect(res.status).toBe(200)
    expect(data).toMatchObject({ account: 's001', role: ['USER'], must_change_password: false })
    expect(token).toMatch(/^mock-token\./)
    expect((await login('s001', 'wrong')).data.detail).toBe('Invalid account or password')
  })

  it('需要改密碼的老師，改完之前其他 API 會回 403', async () => {
    const { token } = await login('chen')
    const blocked = await call('/teacher/courses', { token })
    expect(blocked.res.status).toBe(403)
    expect(blocked.data.detail).toBe('Password change required')
    const changed = await call('/auth/password', {
      method: 'PUT',
      token,
      body: JSON.stringify({ old_password: 'password123', new_password: 'newpassword1' }),
    })
    expect(changed.res.status).toBe(200)
    expect((await call('/teacher/courses', { token })).res.status).toBe(200)
  })

  it('學生不能打老師的 API', async () => {
    const { token } = await login('s001')
    const { res, data } = await call('/teacher/courses', { token })
    expect(res.status).toBe(403)
    expect(data.detail).toBe('Teacher privileges required')
  })

  it('加入課程：格式錯、代碼不存在、已經加入、成功、退出後不能再加入', async () => {
    const { token } = await login('s001')
    const join = (code: string) =>
      call('/student/courses/join', {
        method: 'POST',
        token,
        body: JSON.stringify({ invite_code: code }),
      })
    expect((await join('NOPE99')).data.detail).toBe('Invalid invitation code format')
    expect((await join('ZZZZZZZZ')).data.detail).toBe('Course not found for this invitation code')
    expect((await join('PHSP3456')).data.detail).toBe('Already a member of this course')
    const ok = await join(' ethc7892 ')
    expect(ok.res.status).toBe(200)
    expect(ok.data.name).toBe('倫理學入門')
    const { data: courses } = await call('/student/courses', { token })
    expect(courses).toHaveLength(3)

    const left = await call(`/student/courses/${ok.data.course_id}`, { method: 'DELETE', token })
    expect(left.res.status).toBe(204)
    expect((await join('ETHC7892')).data.detail).toBe('Cannot rejoin after leaving this course')
  })

  it('老師可以把退出的學生用帳號加回來', async () => {
    const student = await login('s001')
    await call('/student/courses/c-phil', { method: 'DELETE', token: student.token })
    const teacher = await login('wang')
    const add = (account_id: string) =>
      call('/teacher/courses/c-phil/students', {
        method: 'POST',
        token: teacher.token,
        body: JSON.stringify({ account_id }),
      })
    expect((await add('nobody')).data.detail).toBe('Student not found')
    expect((await add('s001')).res.status).toBe(200)
    expect((await add('s001')).data.detail).toBe('Student is already in this course')
    const { data: students } = await call('/teacher/courses/c-phil/students', {
      token: teacher.token,
    })
    expect(students.map((s: { account_id: string }) => s.account_id)).toContain('s001')
  })

  it('情境：空資料、錯誤只影響指定的 API 群組', async () => {
    const { token } = await login('s001')
    scenarios.groups.studentCourses = 'empty'
    expect((await call('/student/courses', { token })).data).toEqual([])
    scenarios.groups.studentCourses = 'error'
    const failed = await call('/student/courses', { token })
    expect(failed.res.status).toBe(500)
    expect((await call('/users/me', { token })).res.status).toBe(200)
  })

  it('對話串流：逐段回傳文字，最後一個事件帶剩餘回合數', async () => {
    const { token } = await login('s012')
    const { data: session } = await call('/student/topics/t-lie/sessions', {
      method: 'POST',
      token,
    })
    const res = await fetch(`${API}/student/sessions/${session.session_id}/messages/stream`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: '我覺得可以' }),
    })
    expect(res.headers.get('Content-Type')).toContain('text/event-stream')
    const text = await res.text()
    expect(text).toContain('data: ')
    const done = JSON.parse(text.split('event: done\ndata: ')[1] ?? '{}')
    expect(done).toMatchObject({ remaining_rounds: 4, is_completed: false })
    const { data: history } = await call(`/student/sessions/${session.session_id}/messages`, {
      token,
    })
    expect(history.messages).toHaveLength(3)
  })

  it('匿名的同學在學生端統計顯示成「匿名同學」，老師看得到本名', async () => {
    const student = await login('s001')
    const { data: stats } = await call('/student/topics/t-lie/analytics', { token: student.token })
    const names = stats.conclusions.flatMap((k: { students: { display_name: string }[] }) =>
      k.students.map((s) => s.display_name),
    )
    expect(names).toContain('匿名同學')
    const teacher = await login('wang')
    const { data: teacherStats } = await call('/teacher/topics/t-lie/conclusions', {
      token: teacher.token,
    })
    const teacherNames = teacherStats.conclusions.flatMap(
      (k: { students: { display_name: string }[] }) => k.students.map((s) => s.display_name),
    )
    expect(teacherNames).not.toContain('匿名同學')
  })

  it('Debug「新增很多結論」：結論變多，而且每個結論都分到作答', async () => {
    finishTopicForClass('t-lie')
    expect(addManyConclusions('t-lie')).toContain('已新增 5 個結論')
    const { token } = await login('wang')
    const { data } = await call('/teacher/topics/t-lie/conclusions', { token })
    expect(data.conclusions).toHaveLength(8)
    expect(data.total_answered).toBe(12)
    expect(data.conclusions.every((k: { count: number }) => k.count > 0)).toBe(true)
  })
})
