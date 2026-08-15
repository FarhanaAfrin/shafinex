<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme, useDisplay } from 'vuetify'

import { useSession } from '@/stores/session'
import { useStructure } from '@/stores/structure'

const session = useSession()
const structure = useStructure()
const theme = useTheme()
const route = useRoute()
const router = useRouter()
const { mobile } = useDisplay()

const drawer = ref(true)
const snackbar = ref(false)

const isLogin = computed(() => route.name === 'login')

const nav = computed(() => {
  const items = []
  if (session.sectionVisible('dashboard')) {
    items.push({ title: 'Dashboard', icon: 'mdi-view-dashboard-outline', to: { name: 'dashboard' } })
  }
  if (session.sectionVisible('expenses')) {
    items.push({ title: 'Expenses', icon: 'mdi-receipt-text-outline', to: { name: 'expenses' } })
  }
  if (session.sectionVisible('people')) {
    items.push({ title: 'People', icon: 'mdi-account-group-outline', to: { name: 'people' } })
  }
  if (session.sectionVisible('sheets')) {
    for (const sheet of structure.activeSheets) {
      items.push({
        title: sheet.name,
        icon: sheet.icon || 'mdi-table',
        color: sheet.color,
        to: { name: 'sheet', params: { slug: sheet.slug } },
      })
    }
  }
  if (session.sectionVisible('networth')) {
    items.push({ title: 'Net Worth', icon: 'mdi-scale-balance', to: { name: 'networth' } })
  }
  if (session.sectionVisible('visualization')) {
    items.push({ title: 'Charts', icon: 'mdi-chart-line', to: { name: 'charts' } })
  }
  if (session.sectionVisible('tools')) {
    items.push({ title: 'Tools', icon: 'mdi-tools', to: { name: 'tools' } })
  }
  if (session.sectionVisible('export')) {
    items.push({ title: 'Export', icon: 'mdi-tray-arrow-down', to: { name: 'export' } })
  }
  return items
})

const years = computed(() => {
  const current = new Date().getFullYear()
  const set = new Set([...session.availableYears, current, current + 1, session.year])
  return [...set].sort((a, b) => b - a)
})

/** Preferences drive the live theme: dark mode, accent colour and text size. */
function applyPreferences() {
  const prefs = session.prefs
  if (!prefs) return

  const wantsDark =
    prefs.theme === 'dark' ||
    (prefs.theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  theme.global.name.value = wantsDark ? 'dark' : 'light'

  const themeInstance = theme.themes.value[theme.global.name.value]
  themeInstance.colors.primary = prefs.accent || '#6366F1'

  const radius = { sm: '6px', md: '10px', lg: '14px', xl: '22px' }[prefs.rounded || 'lg']
  document.documentElement.style.setProperty('--app-radius', radius)
  document.documentElement.style.fontSize = `${16 * (prefs.font_scale || 1)}px`
  document.title = prefs.app_name || 'Shahfinex'
}

watch(() => session.prefs, applyPreferences, { deep: true })
watch(
  () => session.toast,
  (value) => {
    if (value) snackbar.value = true
  },
)
watch(mobile, (value) => {
  drawer.value = !value
}, { immediate: true })

watch(
  () => session.isAuthenticated,
  async (value) => {
    if (value) await structure.load(true)
  },
)

onMounted(async () => {
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => applyPreferences())
  if (session.isAuthenticated) {
    try {
      await session.bootstrap()
      await structure.load()
      applyPreferences()
    } catch {
      session.logout()
      router.push({ name: 'login' })
    }
  }
})
</script>

<template>
  <v-app>
    <template v-if="!isLogin">
      <v-navigation-drawer
        v-model="drawer"
        :temporary="mobile"
        color="surface"
        width="248"
        border="0"
      >
        <div class="pa-4 d-flex align-center ga-3">
          <v-avatar :color="session.accent" size="34" rounded="lg">
            <v-icon color="white" size="20">mdi-finance</v-icon>
          </v-avatar>
          <div class="text-truncate">
            <div class="font-weight-bold text-truncate">{{ session.appName }}</div>
            <div v-if="session.prefs?.owner_name" class="text-caption text-medium-emphasis text-truncate">
              {{ session.prefs.owner_name }}
            </div>
          </div>
        </div>

        <v-divider class="mb-2" />

        <v-list nav density="comfortable">
          <v-list-item
            v-for="item in nav"
            :key="item.title"
            :to="item.to"
            :prepend-icon="item.icon"
            :title="item.title"
            rounded="lg"
            color="primary"
          />
        </v-list>

        <template #append>
          <v-divider />
          <v-list nav density="comfortable">
            <v-list-item
              v-if="session.sectionVisible('settings')"
              :to="{ name: 'settings' }"
              prepend-icon="mdi-tune-variant"
              title="Settings"
              rounded="lg"
              color="primary"
            />
            <v-list-item
              prepend-icon="mdi-logout"
              title="Sign out"
              rounded="lg"
              @click="session.logout(); router.push({ name: 'login' })"
            />
          </v-list>
        </template>
      </v-navigation-drawer>

      <v-app-bar flat border="b" height="60">
        <v-app-bar-nav-icon @click="drawer = !drawer" />
        <v-toolbar-title class="text-body-1 font-weight-medium">
          {{ route.name === 'sheet' ? structure.bySlug(route.params.slug)?.name : route.meta.title || '' }}
        </v-toolbar-title>
        <v-spacer />

        <v-select
          :model-value="session.year"
          :items="years"
          density="compact"
          variant="solo-filled"
          flat
          hide-details
          class="year-select mr-2"
          style="min-width: 104px; max-width: 120px"
          @update:model-value="session.setYear($event)"
        />

        <v-btn
          icon
          variant="text"
          :title="session.prefs?.theme === 'dark' ? 'Switch to light' : 'Switch to dark'"
          @click="session.savePrefs({ theme: session.prefs?.theme === 'dark' ? 'light' : 'dark' })"
        >
          <v-icon>{{ session.prefs?.theme === 'dark' ? 'mdi-weather-sunny' : 'mdi-weather-night' }}</v-icon>
        </v-btn>
      </v-app-bar>
    </template>

    <v-main>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </v-main>

    <v-snackbar v-model="snackbar" :color="session.toast?.color" location="bottom right" timeout="2600">
      {{ session.toast?.message }}
    </v-snackbar>
  </v-app>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 120ms ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
