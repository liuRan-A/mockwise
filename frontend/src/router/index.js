import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/store/user'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'form', name: 'form', component: () => import('@/views/SelectForm.vue') },
      { path: 'set', name: 'set', component: () => import('@/views/SelectSet.vue') },
      { path: 'special', name: 'special', component: () => import('@/views/SpecialPractice.vue') },
      { path: 'answer', name: 'answer', component: () => import('@/views/Answer.vue') },
      { path: 'answer/:sessionId', name: 'answerById', component: () => import('@/views/Answer.vue') },
      { path: 'report', name: 'report', component: () => import('@/views/Report.vue') },
      { path: 'report/:reportId', name: 'reportById', component: () => import('@/views/Report.vue') },
      { path: 'history', name: 'history', component: () => import('@/views/History.vue') },
      { path: 'resume', name: 'resume', component: () => import('@/views/Resume.vue') },
      { path: 'admin', name: 'admin', component: () => import('@/views/Admin.vue') },
      { path: 'question/:sessionId/:sqId', name: 'questionDetail', component: () => import('@/views/QuestionDetail.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 } },
})

router.beforeEach((to) => {
  const store = useUserStore()
  if (!to.meta.public && !store.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && store.isLoggedIn) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
