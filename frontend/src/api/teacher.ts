import { apiClient } from './client'

// TODO(負責老師端的組員):
// 依 docs/API功能規格.md 的「老師端模組」段落,照 api/student.ts 的寫法補上
// 對應的 TypeScript 介面跟函式(課程/題目/結論/學生名單 CRUD、AI 生成結論建議等)。
export const teacherApi = {
  getCourses() {
    return apiClient.get('/teacher/courses')
  },
}
