import {
  createRouter,
  createWebHistory,
  type RouteMeta,
  type RouteRecordRaw,
  type RouteRecordSingleView,
} from 'vue-router'
import type { UserRole } from '@/api/auth'
import { HOME_ROUTE, useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: UserRole[]
    /** 已登入的人不需要看到的頁面（登入、註冊），會直接導回他的首頁 */
    guestOnly?: boolean
    /** 瀏覽器分頁標題 */
    title?: string
  }
}

type PageComponent = RouteRecordSingleView['component']

/** 一個頁面：網址、路由名稱、瀏覽器分頁標題、頁面元件（延遲載入） */
function page(
  path: string,
  name: string,
  title: string,
  component: PageComponent,
  meta: RouteMeta = {},
): RouteRecordRaw {
  return { path, name, component, meta: { ...meta, title } }
}

/** 某個身分的一組頁面：需要登入、只有 roles 能進；打開前綴網址時導到第一個頁面 */
function section(path: string, roles: UserRole[], children: RouteRecordRaw[]): RouteRecordRaw {
  const home = children[0]?.name
  return {
    path,
    meta: { requiresAuth: true, roles },
    children: [{ path: '', redirect: { name: home } }, ...children],
  }
}

const routes: RouteRecordRaw[] = [
  // 公開頁面
  {
    ...page('/', 'Home', '公告', () => import('@/views/common/AnnouncementsView.vue')),
    alias: '/announcements',
  },
  page('/login', 'Login', '登入', () => import('@/views/auth/LoginView.vue'), { guestOnly: true }),
  page('/register', 'Register', '註冊', () => import('@/views/auth/RegisterView.vue'), {
    guestOnly: true,
  }),

  section(
    '/admin',
    ['SUPER_ADMIN'],
    [
      page(
        'teachers',
        'AdminTeachers',
        '老師管理',
        () => import('@/views/admin/TeacherManageView.vue'),
      ),
    ],
  ),

  section(
    '/teacher',
    ['TEACHER'],
    [
      page(
        'courses',
        'TeacherCourses',
        '我的課程',
        () => import('@/views/teacher/CourseListView.vue'),
      ),
      page(
        'courses/:courseId',
        'TeacherCourse',
        '問題列表',
        () => import('@/views/teacher/CourseView.vue'),
      ),
      page(
        'courses/:courseId/topics/:topicId',
        'TeacherTopic',
        '問題結果',
        () => import('@/views/teacher/TopicView.vue'),
      ),
    ],
  ),

  section(
    '/student',
    ['STUDENT'],
    [
      page(
        'courses',
        'StudentCourses',
        '我的課程',
        () => import('@/views/student/CourseListView.vue'),
      ),
      page(
        'courses/:courseId',
        'StudentCourse',
        '問題列表',
        () => import('@/views/student/CourseView.vue'),
      ),
      page(
        'courses/:courseId/topics/:topicId',
        'StudentChat',
        '對話',
        () => import('@/views/student/ChatView.vue'),
      ),
      page(
        'courses/:courseId/sessions/:sessionId/result',
        'StudentResult',
        '對話結果',
        () => import('@/views/student/ResultView.vue'),
      ),
    ],
  ),

  page('/forbidden', 'Forbidden', '沒有權限', () => import('@/views/common/ForbiddenView.vue')),
  page(
    '/:pathMatch(.*)*',
    'NotFound',
    '找不到頁面',
    () => import('@/views/common/NotFoundView.vue'),
  ),
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  // 1. 需要登入但還沒登入 → 登入頁，登入後跳回原本想去的頁面
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  // 2. 已登入卻打開登入、註冊頁 → 回到自己的首頁
  if (to.meta.guestOnly && authStore.isAuthenticated && authStore.userRole) {
    return { name: HOME_ROUTE[authStore.userRole] }
  }

  // 3. 身分不符（例如學生打開 /teacher）→ 沒有權限頁。管理員同時也是老師時，兩邊都能進
  if (to.meta.roles && authStore.userRole && !to.meta.roles.some((r) => authStore.hasRole(r))) {
    return { name: 'Forbidden' }
  }

  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title}｜問導魷` : '問導魷'
})

export default router
