import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { UserRole } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: UserRole[]
  }
}

const routes: RouteRecordRaw[] = [
  {// 管理員端路由
    path: '/admin',
    name: 'AdminHome',
    component: () => import('@/views/admin/AdminHome.vue')
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  // 學生端路由
  {
    path: '/student',
    meta: { requiresAuth: true, roles: ['STUDENT'] },
    children: [
      {
        path: 'courses',
        name: 'StudentCourses',
        component: () => import('@/views/student/CourseListView.vue'),
      },
      {
        path: 'chat/:questionId',
        name: 'StudentChat',
        component: () => import('@/views/student/ChatView.vue'),
      },
    ],
  },
  // 老師端路由
  {
    path: '/teacher',
    meta: { requiresAuth: true, roles: ['TEACHER'] },
    children: [
      {
        path: 'dashboard',
        name: 'TeacherDashboard',
        component: () => import('@/views/teacher/DashboardView.vue'),
      },
      {
        path: 'questions',
        name: 'TeacherQuestions',
        component: () => import('@/views/teacher/QuestionManageView.vue'),
      },
    ],
  },
  // 管理員路由
  {
    path: '/admin',
    meta: { requiresAuth: true, roles: ['ADMIN'] },
    children: [
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/UserManageView.vue'),
      },
    ],
  },
  // 預設跳轉首頁
  {
    path: '/',
    redirect: '/login',
  },
  // 404 / 無權限處理
  {
    path: '/forbidden',
    name: 'Forbidden',
    component: () => import('@/views/common/ForbiddenView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// 全域前置守衛（警衛室）
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // 1. 若該頁面需要登入，但使用者尚未登入
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next({
      path: '/login',
      query: { redirect: to.fullPath }, // 記錄原本想去的路徑，登入成功後跳回
    })
  }

  // 2. 若使用者已登入，卻試圖訪問登入頁，依身分導航至其主頁
  if (to.path === '/login' && authStore.isAuthenticated) {
    if (authStore.userRole === 'STUDENT') return next('/student/courses')
    if (authStore.userRole === 'TEACHER') return next('/teacher/dashboard')
    if (authStore.userRole === 'ADMIN') return next('/admin/users')
  }

  // 3. 檢查身分權限是否符合該路由規範
  if (to.meta.roles && authStore.userRole) {
    const hasRole = to.meta.roles.includes(authStore.userRole)
    if (!hasRole) {
      // 角色不符（例如學生偷連 /teacher），攔截導向無權限頁面
      return next('/forbidden')
    }
  }

  // 4. 驗證全數通過，放行
  next()
})

export default router