/**
 * Debug 面板「假資料」分頁的動作。直接改假資料庫，再讓畫面重新抓資料。
 */
import { announcements } from '@/data/announcements'
import { mockReply, mockSetup } from './ai'
import { completeSession } from './handlers'
import { db, newId, newInviteCode, resetDb, secureRandomInt, type DbSession } from './db'

const COURSE_NAMES = ['邏輯思考', '媒體識讀', '環境倫理', '科技與社會', '生命教育', '經濟學入門']
const TOPIC_TEXTS = [
  '考試是評量學習最好的方式嗎？討論考試的目的與限制。',
  '網路上匿名發言應該被禁止嗎？兼顧言論自由與責任。',
  '動物園應該存在嗎？從保育、教育和動物福利來看。',
  '社群媒體讓我們更孤單了嗎？從自己的使用經驗出發。',
]
const FAMILY = ['陳', '林', '黃', '張', '李', '王', '吳', '劉', '蔡', '楊', '許', '鄭', '謝', '郭']
const GIVEN = ['宇翔', '雅琪', '子涵', '承恩', '欣妤', '冠廷', '思妤', '柏宇', '品睿', '佳穎']

/** 用安全亂數挑一個（Math.random 會被 SonarCloud 擋，直接取餘數會被 CodeQL 擋） */
function pick<T>(list: readonly T[]) {
  return list[secureRandomInt(list.length)] as T
}

/** 目前登入的假帳號（從 token 看出來） */
export function currentMockUser() {
  try {
    const token = localStorage.getItem('access_token') ?? ''
    const id = token.replace(/^mock-token\./, '')
    return db.users.find((u) => u.id === id)
  } catch {
    return undefined
  }
}

export function addCourse() {
  const user = currentMockUser()
  const teacherId = user?.role === 'TEACHER' ? user.id : 'u-wang'
  const name = `${pick(COURSE_NAMES)} ${pick([11, 23, 35, 47, 59, 61, 73, 85, 97])}`
  const course = {
    id: newId('c'),
    name,
    description: '用 Debug 面板新增的課程',
    invite_code: newInviteCode(),
    teacher_id: teacherId,
    created_at: new Date().toISOString(),
  }
  db.courses.push(course)
  // 學生登入時，順便把他加進去，馬上看得到
  if (user?.role === 'USER') {
    db.members.push({
      course_id: course.id,
      user_id: user.id,
      role: 'student',
      permissions: [],
      joined_at: new Date().toISOString(),
    })
  }
  return `已新增課程「${name}」，課程代碼 ${course.invite_code}`
}

/** 新增一題已發布的活動（學生馬上可以作答） */
export function addTopic(courseId: string) {
  const course = db.courses.find((c) => c.id === courseId)
  if (!course) return '請先進到某一門課程的頁面'
  const text = pick(TOPIC_TEXTS)
  db.topics.push({
    id: newId('t'),
    course_id: course.id,
    status: 'conversation',
    course_description: text,
    model_id: db.models[0]!.model_id,
    setup: mockSetup(text, '16-18', 5),
    created_at: new Date().toISOString(),
  })
  return '已新增一個已發布的探究活動'
}

export function addStudents(courseId: string, count = 5) {
  const course = db.courses.find((c) => c.id === courseId)
  if (!course) return '請先進到某一門課程的頁面'
  for (let i = 0; i < count; i += 1) {
    const id = newId('u')
    db.users.push({
      id,
      account_id: `demo${db.users.length + 1}`,
      name: `${pick(FAMILY)}${pick(GIVEN)}`,
      password: 'password123',
      role: 'USER',
      must_change_password: false,
      preferred_language: 'zh-TW',
      created_at: new Date().toISOString(),
    })
    db.members.push({
      course_id: course.id,
      user_id: id,
      role: 'student',
      permissions: [],
      joined_at: new Date().toISOString(),
    })
  }
  return `已新增 ${count} 位學生`
}

/** 讓一個 Session 直接聊到最後一回合並完成 */
function finish(session: DbSession) {
  const topic = db.topics.find((t) => t.id === session.topic_id)
  if (!topic || session.status === 'COMPLETED') return false
  let turn = session.messages.filter((m) => m.sender === 'student').length
  while (turn < topic.setup.max_turns) {
    turn += 1
    const line = `（自動作答）第 ${turn} 回合的想法`
    session.messages.push({
      id: newId('m'),
      sender: 'student',
      content: line,
      created_at: new Date().toISOString(),
    })
    session.messages.push({
      id: newId('m'),
      sender: 'ai',
      content: mockReply(line, turn, turn === topic.setup.max_turns),
      created_at: new Date().toISOString(),
    })
  }
  // 自動作答到回合用完：跟真後端一樣自動結束（turn_limit）並開始產生報告
  completeSession(session, 'turn_limit')
  return true
}

/** 全班都完成這一題（還沒開始的也幫他開始） */
export function finishTopicForClass(topicId: string) {
  const topic = db.topics.find((t) => t.id === topicId)
  if (!topic) return '請先進到某一個探究活動的頁面'
  const students = db.members.filter((m) => m.course_id === topic.course_id && m.role === 'student')
  let done = 0
  for (const m of students) {
    let session = db.sessions.find((s) => s.topic_id === topicId && s.student_id === m.user_id)
    if (!session) {
      session = {
        id: newId('ss'),
        topic_id: topicId,
        student_id: m.user_id,
        status: 'IN_PROGRESS',
        awaiting_end_consent: false,
        messages: [],
        completed_at: null,
      }
      db.sessions.push(session)
    }
    if (finish(session)) done += 1
  }
  return `已讓 ${done} 位學生完成作答（報告約 4 秒後產生完成）`
}

/** 目前登入的學生直接完成這一題 */
export function finishMyChat(topicId: string) {
  const user = currentMockUser()
  const session = db.sessions.find((s) => s.topic_id === topicId && s.student_id === user?.id)
  if (!session) return '請先在對話頁開始作答'
  return finish(session) ? '已完成這次對話，重新整理後可以看報告' : '這次對話已經完成了'
}

/** 找出目前頁面的題目：網址有 topicId 就用；學生報告頁從 sessionId 反查 */
export function topicFromRoute(params: Record<string, unknown>) {
  if (typeof params.topicId === 'string') return params.topicId
  if (typeof params.sessionId === 'string') {
    return db.sessions.find((s) => s.id === params.sessionId)?.topic_id ?? ''
  }
  return ''
}

/** 讓這一題所有報告變成「產生失敗」，用來看失敗畫面 */
export function failReports(topicId: string) {
  const ids = db.sessions.filter((s) => s.topic_id === topicId).map((s) => s.id)
  const reports = db.reports.filter((r) => ids.includes(r.session_id))
  for (const r of reports) r.failed = true
  return reports.length ? `已讓 ${reports.length} 份報告變成產生失敗` : '這一題還沒有報告'
}

/** 新增公告；標題、內容沒填就用預設的測試文字 */
export function addAnnouncement(title = '', content = '') {
  const now = new Date()
  announcements.unshift({
    id: `debug-${now.getTime()}`,
    title: title.trim() || `測試公告 ${now.toLocaleTimeString('zh-TW', { hour12: false })}`,
    content:
      content.trim() ||
      '這是用 Debug 面板新增的公告。內容比較長的時候，收合狀態只會顯示第一行，點一下標題可以展開全文。',
    published_at: now.toISOString(),
  })
  return '已新增公告（重新整理後會消失；要永久保留請改 src/data/announcements.ts）'
}

export function clearAnnouncements() {
  announcements.splice(0, announcements.length)
  return '已清空公告（重新整理後會恢復）'
}

export function resetAllData() {
  resetDb()
  return '假資料已重置'
}
