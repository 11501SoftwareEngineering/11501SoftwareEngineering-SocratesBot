import path from 'node:path'
import { createServer, type Plugin } from 'vite'

const origin = 'http://127.0.0.1:5176'
const coursePath = '/student/courses/demo-course'
const auth = {
  token: 'preview-only-student-token',
  user: { id: 'preview-student', email: 'student-preview', name: '示範學生', role: 'STUDENT' },
}
const course = {
  course_id: 'demo-course',
  name: '公民與社會',
  invite_code: 'PREVIEW',
  topics: [
    {
      topic_id: 'demo-phone',
      title: '校園應該限制手機使用嗎？',
      description: '討論校園規範與學生自由。',
      status: 'ACTIVE',
      session_id: null,
      age_range: '12–18',
      round_count: 5,
    },
    {
      topic_id: 'demo-ai',
      title: '人工智慧生成的作品有著作權嗎？',
      description: '討論人工智慧、創作與著作權。',
      status: 'ACTIVE',
      session_id: null,
      age_range: '15–18',
      round_count: 8,
    },
    {
      topic_id: 'demo-safety',
      title: '公共安全可以限制個人自由嗎？',
      description: '思考公共安全與個人權利的界線。',
      status: 'ACTIVE',
      session_id: null,
      age_range: '12–18',
      round_count: 0,
    },
  ],
}
const previewPlugin: Plugin = {
  name: 'student-course-local-preview',
  apply: 'serve',
  transformIndexHtml() {
    return [
      {
        tag: 'script',
        injectTo: 'head-prepend',
        children: `
        if (location.pathname.startsWith('/student/')) {
          localStorage.setItem('auth', JSON.stringify(${JSON.stringify(auth)}));
          localStorage.setItem('access_token', ${JSON.stringify(auth.token)});
        }
      `,
      },
    ]
  },
  configureServer(server) {
    server.middlewares.use((request, response, next) => {
      const pathname = new URL(request.url ?? '/', origin).pathname
      if (!pathname.startsWith('/api/v1/')) return next()
      response.setHeader('Content-Type', 'application/json; charset=utf-8')
      response.setHeader('Cache-Control', 'no-store')

      if (request.method === 'GET' && pathname === '/api/v1/student/courses/demo-course/topics') {
        response.end(JSON.stringify(course))
      } else {
        response.statusCode = 404
        response.end(JSON.stringify({ detail: '前端預覽模式未提供此 API' }))
      }
    })
  },
}

const server = await createServer({
  root: path.resolve(import.meta.dirname, '..'),
  mode: 'development',
  plugins: [previewPlugin],
  define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify(origin) },
  server: { host: '127.0.0.1', port: 5176, strictPort: true },
})
await server.listen()
console.log('前端預覽首頁已恢復為公告。')
console.log(`課程假資料預覽：${origin}${coursePath}（無需帳號密碼）；Ctrl+C 停止預覽。`)
server.printUrls()
server.bindCLIShortcuts({ print: true })
