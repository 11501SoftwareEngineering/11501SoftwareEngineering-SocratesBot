/**
 * 假 AI：產生活動設定、對話回覆、個人報告。內容是固定的範本，只為了讓畫面有東西看。
 * 不用 Math.random()（SonarCloud 會擋），需要變化時用輸入的長度或回合數決定。
 */
import type { AgeBand, MaxTurns } from '@/api/courses'
import type { TopicSetup } from '@/api/topics'
import type { PersonalReport, TimelineEntry } from '@/api/sessions'

interface MessageLike {
  id: string
  sender: 'ai' | 'student'
  content: string
  created_at: string
}

/** 從一段文字取出前幾個字當主題 */
function headline(text: string, max = 14) {
  const first = text.split(/[。？！?!\n]/)[0]?.trim() ?? ''
  return (first || text).slice(0, max)
}

export function mockOpening(setup: Pick<TopicSetup, 'topic' | 'core_question'>) {
  return `你好！今天我們一起來想想「${setup.topic}」。${setup.core_question} 先不用急著找標準答案，說說你的第一個想法，以及你為什麼這樣想？`
}

/** 新增活動：依課程描述產生八欄 */
export function mockSetup(description: string, age_band: AgeBand, max_turns: MaxTurns): TopicSetup {
  const topic = headline(description)
  const setup: TopicSetup = {
    age_band,
    max_turns,
    topic,
    core_question: `關於「${topic}」，你認為怎樣做才是對的？為什麼？`,
    inquiry_focus: '引導學生說出自己的立場與理由，並思考不同立場的人會怎麼看；不預設標準答案。',
    background_info: `老師提供的課程背景：${description.slice(0, 120)}`,
    exclusions: '未指定',
    opening_message: '',
  }
  setup.opening_message = mockOpening(setup)
  return setup
}

/** 依老師回饋修改：照回饋在探究重點後補一句，示範「AI 改過了」 */
export function mockRefine(setup: TopicSetup, feedback: string): TopicSetup {
  const note = feedback.trim().slice(0, 60)
  return {
    ...setup,
    inquiry_focus: `${setup.inquiry_focus.replace(/（依回饋調整：.*?）$/, '')}（依回饋調整：${note}）`,
    background_info:
      setup.background_info.length > 80
        ? `${setup.background_info.slice(0, 80)}…`
        : setup.background_info,
  }
}

const FOLLOW_UPS = [
  (s: string) => `你提到「${s}」，可以舉一個生活中的例子嗎？`,
  (s: string) => `如果有人不同意「${s}」，他可能會怎麼說？你會怎麼回應？`,
  (s: string) => `「${s}」這個想法，在什麼情況下可能不成立？`,
  (_s: string) => `聽完不同的看法後，你的想法有沒有改變？哪一部分最讓你猶豫？`,
  (s: string) => `如果要用一句話說明你的立場，你會怎麼說？為什麼是「${s}」？`,
]

const STUDENT_LINES = [
  '我覺得要看情況，如果是為了保護別人的感受，好像可以理解。',
  '例如朋友問我他的畫好不好看，我可能會先說優點。',
  '可是如果他之後發現我騙他，可能會更難過，也不相信我了。',
  '我想可以誠實，但是用比較溫和的方式說。',
  '我的立場是：盡量誠實，但要顧及對方的感受。',
  '我想再補充，如果事情很重要，就一定要說實話。',
]

export function snippet(text: string) {
  const clean = text.replace(/\s+/g, '')
  return clean.length > 12 ? `${clean.slice(0, 12)}…` : clean
}

/** 對話回覆 */
export function mockReply(studentText: string, turn: number, isLast: boolean) {
  if (isLast) {
    return '謝謝你的分享！你已經從好幾個角度思考過這個問題了，這次的探究就到這裡，等一下可以看看你的個人報告。'
  }
  const pick = FOLLOW_UPS[(turn - 1) % FOLLOW_UPS.length]!
  return pick(snippet(studentText))
}

/** 產生一段對話紀錄（種子資料用）：開場訊息 + turns 回合 */
export function mockTranscript(setup: TopicSetup, turns: number, start: string): MessageLike[] {
  const base = new Date(start).getTime()
  const at = (i: number) => new Date(base + i * 60_000).toISOString()
  const messages: MessageLike[] = [
    {
      id: `m-${start}-0`,
      sender: 'ai',
      content: setup.opening_message || mockOpening(setup),
      created_at: at(0),
    },
  ]
  for (let turn = 1; turn <= turns; turn += 1) {
    const line = STUDENT_LINES[(turn - 1) % STUDENT_LINES.length]!
    messages.push({
      id: `m-${start}-${turn}s`,
      sender: 'student',
      content: line,
      created_at: at(turn * 2 - 1),
    })
    messages.push({
      id: `m-${start}-${turn}a`,
      sender: 'ai',
      content: mockReply(line, turn, turn === setup.max_turns),
      created_at: at(turn * 2),
    })
  }
  return messages
}

const STANCE_TEXT: Record<string, { viewpoint: string; status: string }> = {
  support: { viewpoint: '善意的謊言可以接受', status: '已表達立場' },
  oppose: { viewpoint: '說謊就是不對', status: '已表達立場' },
  conditional: { viewpoint: '要看情況決定', status: '立場有條件' },
  '': { viewpoint: '盡量誠實，但顧及對方感受', status: '已表達立場' },
}

const CHANGE_TYPES = ['初步表態', '補充理由或條件', '觀點修正', '維持立場', '總結立場']

/** 個人報告（學生完成對話後產生） */
export function mockReport(options: {
  sessionId: string
  topic: { id: string; setup: TopicSetup }
  messages: MessageLike[]
  anonymousId: string
  completedAt: string
  stance?: string
}): PersonalReport {
  const { sessionId, topic, messages, anonymousId, completedAt } = options
  const stance = STANCE_TEXT[options.stance ?? ''] ?? STANCE_TEXT['']!
  const studentMessages = messages.filter((m) => m.sender === 'student')
  const aiMessages = messages.filter((m) => m.sender === 'ai')
  const timeline: TimelineEntry[] = studentMessages.map((m, i) => ({
    turn: i + 1,
    question: aiMessages[i]?.content ?? '',
    evidence: [{ message_id: m.id, turn: i + 1, quote: m.content }],
    viewpoint_before: i === 0 ? null : stance.viewpoint,
    viewpoint_after:
      i === 0 ? `初步觀點：${snippet(m.content)}` : `觀點演變：${snippet(m.content)}`,
    change_type: CHANGE_TYPES[Math.min(i, CHANGE_TYPES.length - 1)]!,
    attribution: i === 0 ? 'none' : i % 2 ? 'sequence_only' : 'explicit',
  }))
  return {
    report_id: `r-${sessionId}`,
    version: 1,
    session_id: sessionId,
    topic_id: topic.id,
    anonymous_id: anonymousId,
    completed_at: completedAt,
    completed_turns: studentMessages.length,
    completion_reason: 'goal_reached',
    viewpoint_summary: `你認為「${stance.viewpoint}」。你從生活中的例子出發，考慮了對方的感受，也想到謊言被發現後可能失去信任。`,
    final_viewpoint: stance.viewpoint,
    viewpoint_status: stance.status,
    reasons: ['顧及對方的感受', '謊言被發現會破壞信任'],
    strongest_reason: '謊言被發現後，失去的信任比原本的傷害更難修復。',
    challenges: [
      { challenge: '如果對方永遠不會發現，說謊還有問題嗎？', responded: true },
      { challenge: '誠實但溫和的說法，一定做得到嗎？', responded: studentMessages.length > 3 },
    ],
    revision_or_defense:
      '一開始認為可以說謊，被問到「被發現之後」時，修正為盡量誠實、但用溫和的方式說。',
    focus_connection: `有回應到探究重點：說出自己的立場與理由，並考慮了不同立場。（${topic.setup.topic}）`,
    other_perspectives: '有想到反對者會擔心信任問題。',
    open_questions: ['什麼樣的事情「重要到」一定要說實話？', '對方知道真相後的感受，要怎麼衡量？'],
    evidence_status: studentMessages.length >= 4 ? 'sufficient' : 'partial',
    limitations: studentMessages.length >= 4 ? null : '回合數較少，判斷可能不夠完整。',
    timeline,
  }
}
