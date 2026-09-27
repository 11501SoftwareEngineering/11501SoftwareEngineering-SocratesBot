import { apiClient } from './client'

// TODO(負責管理員端的組員):
// 依 docs/API功能規格.md 的「老師管理員模組」段落補上老師帳號的增刪查功能。
export const adminApi = {
  getTeachers() {
    return apiClient.get('/admin/teachers')
  },
}
