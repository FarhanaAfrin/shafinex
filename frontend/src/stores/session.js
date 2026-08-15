import { defineStore } from 'pinia'
import api from '@/api'

/**
 * Auth + preferences + the active year. Preferences live here because almost
 * every view formats money or reads the accent colour.
 */
export const useSession = defineStore('session', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    prefs: null,
    year: Number(localStorage.getItem('year')) || new Date().getFullYear(),
    availableYears: [],
    currentMonth: new Date().getMonth() + 1,
    loading: false,
    ready: false,
    toast: null,
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    appName: (state) => state.prefs?.app_name || 'Shahfinex',
    accent: (state) => state.prefs?.accent || '#6366F1',
    palette: (state) => state.prefs?.chart_palette || ['#6366F1'],
    autosaveDelay: (state) => state.prefs?.autosave_delay_ms ?? 600,
    sectionVisible: (state) => (key) =>
      !state.prefs?.visible_sections || state.prefs.visible_sections.includes(key),
  },

  actions: {
    async login(password) {
      const { data } = await api.login(password)
      this.token = data.token
      localStorage.setItem('token', data.token)
      await this.bootstrap()
    },

    logout() {
      this.token = ''
      this.prefs = null
      this.ready = false
      localStorage.removeItem('token')
    },

    async bootstrap() {
      if (!this.token) return
      this.loading = true
      try {
        const { data } = await api.meta()
        this.prefs = data.preferences
        this.availableYears = data.available_years
        this.currentMonth = data.current.month
        if (!this.availableYears.includes(this.year)) {
          this.year = data.current.year
        }
        this.ready = true
      } finally {
        this.loading = false
      }
    },

    setYear(year) {
      this.year = year
      localStorage.setItem('year', String(year))
      if (!this.availableYears.includes(year)) {
        this.availableYears = [...this.availableYears, year].sort()
      }
    },

    /** Optimistic: apply locally first so the UI reacts instantly. */
    async savePrefs(patch) {
      const previous = JSON.parse(JSON.stringify(this.prefs))
      this.prefs = deepMerge(this.prefs, patch)
      try {
        const { data } = await api.savePreferences(patch)
        this.prefs = data
      } catch (error) {
        this.prefs = previous
        throw error
      }
    },

    async resetPrefs() {
      const { data } = await api.resetPreferences()
      this.prefs = data
    },

    notify(message, color = 'success') {
      this.toast = { message, color, at: Date.now() }
    },
  },
})

function deepMerge(base, patch) {
  const out = { ...(base || {}) }
  for (const [key, value] of Object.entries(patch || {})) {
    out[key] =
      value && typeof value === 'object' && !Array.isArray(value)
        ? deepMerge(out[key], value)
        : value
  }
  return out
}
