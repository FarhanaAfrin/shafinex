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

// A tab open across a redeploy still holds the old index.html in memory, so a
// lazily-imported view resolves to a filename the server no longer has and the
// route silently fails to render. Reload once to pick up the new asset map;
// the sessionStorage flag stops that turning into a refresh loop if the chunk
// is genuinely missing rather than merely stale.
const RELOADED = 'chunk-reload-attempted'

router.onError((error, to) => {
  const stale = /dynamically imported module|Importing a module script failed|Failed to fetch/i
  if (!stale.test(error?.message || '')) return
  if (sessionStorage.getItem(RELOADED)) return
  sessionStorage.setItem(RELOADED, '1')
  window.location.assign(to?.fullPath || window.location.pathname)
})

router.afterEach(() => sessionStorage.removeItem(RELOADED))

export default router
