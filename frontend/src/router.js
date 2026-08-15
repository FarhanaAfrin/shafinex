import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from '@/stores/session'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
  { path: '/sheet/:slug', name: 'sheet', component: () => import('@/views/SheetView.vue'), props: true },
  { path: '/expenses', name: 'expenses', component: () => import('@/views/ExpensesView.vue') },
  { path: '/people', name: 'people', component: () => import('@/views/PeopleView.vue') },
  { path: '/networth', name: 'networth', component: () => import('@/views/NetWorthView.vue') },
  { path: '/charts', name: 'charts', component: () => import('@/views/VisualizationView.vue') },
  { path: '/tools', name: 'tools', component: () => import('@/views/ToolsView.vue') },
  { path: '/export', name: 'export', component: () => import('@/views/ExportView.vue') },
  { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const session = useSession()
  if (to.meta.public) return true
  if (!session.isAuthenticated) return { name: 'login', query: { next: to.fullPath } }
  if (!session.ready) {
    try {
      await session.bootstrap()
    } catch {
      session.logout()
      return { name: 'login' }
    }
  }
  return true
})

export default router
