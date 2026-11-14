/**
 * 探索結果報告的範例資料（還沒接 API，畫面先用這份）。
 *
 * 欄位名稱照 docs/API功能規格.md v0.2：
 *   messages → GET /sessions/{sessionId}/messages 的 `messages`
 *   之後接 API 時，只要把 ReportView 裡的 sampleReport 換成 API 回傳的資料，畫面不用改。
 */

/** 一則對話訊息（GET /sessions/{sessionId}/messages） */
export interface SessionMessage {
  message_id: string
  sender: 'ai' | 'student'
  content: string
  created_at: string
}

export interface SampleReport {
  course_id: string
  course_name: string
  topic_title: string
  messages: SessionMessage[]
}

export const sampleReport: SampleReport = {
  course_id: 'course-1',
  course_name: '公民思辨',
  topic_title: '多數決做出的決定，一定是公平的嗎？',
  messages: [
    {
      message_id: 'm1',
      sender: 'ai',
      content:
        '你剛剛說「大家投票決定就很公平」。想像一下：班上投票決定畢業旅行的地點，三十個人裡有二十個人想去海邊，但有五位同學因為身體因素不能下水。投票結果是去海邊，你覺得這個決定對那五位同學公平嗎？為什麼？',
      created_at: '2026-11-10T10:02:00+08:00',
    },
    {
      message_id: 'm2',
      sender: 'student',
      content:
        '我覺得程序上是公平的，因為每個人都有投票權，票數也算得很清楚。可是對那五位同學來說，結果好像不太公平，他們去了也只能在旁邊看。也許公平不只是「每個人一票」，還要看結果有沒有讓每個人都能參與，所以我覺得投票前應該先問大家有沒有不能參加的原因。',
      created_at: '2026-11-10T10:04:30+08:00',
    },
    {
      message_id: 'm3',
      sender: 'ai',
      content:
        '你把公平分成了「程序」和「結果」兩種，這是很重要的區分。那如果投票前先問了，大家還是決定去海邊，只是另外幫那五位同學安排別的活動，這樣算公平了嗎？誰有權決定「哪些原因」值得被考慮？',
      created_at: '2026-11-10T10:05:10+08:00',
    },
  ],
}
