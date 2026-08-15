<script setup>
/** Everything customizable in one place: look, money format, calendar,
 *  structure (sheets/categories/net-worth items), goals and data tools. */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api, { errorMessage } from '@/api'
import { useFormat } from '@/composables/useFormat'
import { useSession } from '@/stores/session'
import { useStructure } from '@/stores/structure'

const session = useSession()
const structure = useStructure()
const route = useRoute()
const router = useRouter()
const { formatMoney } = useFormat()

const tab = ref(route.query.tab || 'appearance')
watch(tab, (value) => router.replace({ query: { ...route.query, tab: value } }))

const prefs = computed(() => session.prefs || {})
const busy = ref(false)
const templates = ref([])
const categories = ref({})
const expandedSheet = ref(null)
const confirm = ref(null)

/** Every control writes straight through to the server (deep-merged). */
async function set(patch) {
  try {
    await session.savePrefs(patch)
  } catch (error) {
    session.notify(errorMessage(error, 'Could not save that setting'), 'error')
  }
}

function update(key) {
  return (value) => set({ [key]: value })
}

function updateGoal(key) {
  return (value) => set({ goals: { [key]: Number(value) || 0 } })
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
].map((title, index) => ({ title, value: index + 1 }))

const CURRENCIES = [
  { title: 'Japanese yen (¥)', value: 'JPY', symbol: '¥', decimals: 0 },
  { title: 'US dollar ($)', value: 'USD', symbol: '$', decimals: 2 },
  { title: 'Euro (€)', value: 'EUR', symbol: '€', decimals: 2 },
  { title: 'British pound (£)', value: 'GBP', symbol: '£', decimals: 2 },
  { title: 'Indian rupee (₹)', value: 'INR', symbol: '₹', decimals: 2 },
  { title: 'Bangladeshi taka (৳)', value: 'BDT', symbol: '৳', decimals: 0 },
  { title: 'Canadian dollar (C$)', value: 'CAD', symbol: 'C$', decimals: 2 },
  { title: 'Australian dollar (A$)', value: 'AUD', symbol: 'A$', decimals: 2 },
  { title: 'Custom', value: 'CUSTOM', symbol: '', decimals: 2 },
]

const ACCENTS = [
  '#6366F1', '#0EA5E9', '#22C55E', '#F59E0B',
  '#EF4444', '#EC4899', '#8B5CF6', '#14B8A6',
]

const SECTIONS = [
  { title: 'Dashboard', value: 'dashboard' },
  { title: 'Sheets', value: 'sheets' },
  { title: 'Net worth', value: 'networth' },
  { title: 'Charts', value: 'visualization' },
  { title: 'Tools', value: 'tools' },
  { title: 'Export', value: 'export' },
  { title: 'Settings', value: 'settings' },
]

function pickCurrency(code) {
  const entry = CURRENCIES.find((c) => c.value === code)
  if (!entry) return
  set({
    currency: code,
    ...(code === 'CUSTOM' ? {} : { currency_symbol: entry.symbol, decimals: entry.decimals }),
  })
}

// ------------------------------------------------------------------ structure
const newSheet = ref({ name: '', kind: 'outflow', plan_label: 'Budget', color: '#6366F1', icon: 'mdi-table' })
const newItem = ref({ asset: '', liability: '' })

async function loadCategories(sheet) {
  const { data } = await api.categories(sheet.slug, true)
  categories.value = { ...categories.value, [sheet.slug]: data }
}

async function addSheet() {
  if (!newSheet.value.name.trim()) return
  busy.value = true
  try {
    await structure.createSheet({ ...newSheet.value, name: newSheet.value.name.trim() })
    newSheet.value = { name: '', kind: 'outflow', plan_label: 'Budget', color: '#6366F1', icon: 'mdi-table' }
    session.notify('Sheet added')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not add that sheet'), 'error')
  } finally {
    busy.value = false
  }
}

async function saveSheet(sheet, patch) {
  try {
    await structure.updateSheet(sheet.id, patch)
  } catch (error) {
    session.notify(errorMessage(error, 'Could not update that sheet'), 'error')
  }
}

function askDeleteSheet(sheet) {
  confirm.value = {
    title: `Delete “${sheet.name}”?`,
    text: 'Hiding keeps every amount. Deleting removes the sheet, its categories and all of its numbers.',
    action: async () => {
      await structure.deleteSheet(sheet.id, false)
      session.notify('Sheet hidden')
    },
    hardAction: async () => {
      await structure.deleteSheet(sheet.id, true)
      session.notify('Sheet deleted')
    },
  }
}

async function moveSheet(sheet, direction) {
  const ids = structure.sheets.map((s) => s.id)
  const index = ids.indexOf(sheet.id)
  const target = index + direction
  if (target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  await structure.reorderSheets(ids)
}

async function addCategory(sheet, name) {
  if (!name.trim()) return
  try {
    await api.createCategory({ sheet_id: sheet.id, name: name.trim() })
    await loadCategories(sheet)
    session.notify('Category added')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not add that category'), 'error')
  }
}

async function toggleCategory(sheet, category) {
  await api.updateCategory(category.id, { is_active: !category.is_active })
  await loadCategories(sheet)
}

async function removeCategory(sheet, category) {
  confirm.value = {
    title: `Delete “${category.name}”?`,
    text: 'Hiding keeps its history. Deleting removes the category and every amount recorded against it.',
    action: async () => {
      await api.deleteCategory(category.id, false)
      await loadCategories(sheet)
    },
    hardAction: async () => {
      await api.deleteCategory(category.id, true)
      await loadCategories(sheet)
    },
  }
}

async function addNetworthItem(side) {
  const name = newItem.value[side].trim()
  if (!name) return
  try {
    await structure.createNetworthItem({ side, name })
    newItem.value[side] = ''
    session.notify('Item added')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not add that item'), 'error')
  }
}

function askDeleteItem(item) {
  confirm.value = {
    title: `Delete “${item.name}”?`,
    text: 'Hiding keeps its balances. Deleting removes the item and its history.',
    action: async () => structure.deleteNetworthItem(item.id, false),
    hardAction: async () => structure.deleteNetworthItem(item.id, true),
  }
}

const assets = computed(() => structure.networthItems.filter((i) => i.side === 'asset'))
const liabilities = computed(() => structure.networthItems.filter((i) => i.side === 'liability'))

// ------------------------------------------------------------------ data tools
const seedTemplate = ref('default')
const seedReplace = ref(false)
const copySource = ref(session.year - 1)
const copyTarget = ref(session.year)
const copyPlanOnly = ref(true)

async function runSeed() {
  confirm.value = {
    title: seedReplace.value ? 'Replace everything?' : 'Add starter categories?',
    text: seedReplace.value
      ? 'This deletes all current sheets, categories, items AND amounts, then loads the template.'
      : 'Missing categories from the template will be added. Nothing existing is touched.',
    action: async () => {
      const { data } = await api.seed(seedTemplate.value, seedReplace.value)
      await structure.load(true)
      session.notify(
        `Added ${data.created.sheets} sheets, ${data.created.categories} categories, ${data.created.networth_items} items`,
      )
    },
  }
}

async function runCopyYear() {
  try {
    const { data } = await api.copyYear(copySource.value, copyTarget.value, copyPlanOnly.value)
    session.notify(`Copied ${data.written} values into ${copyTarget.value}`)
  } catch (error) {
    session.notify(errorMessage(error, 'Copy failed'), 'error')
  }
}

function askClearYear() {
  confirm.value = {
    title: `Clear all ${session.year} amounts?`,
    text: 'Categories stay; every number recorded for this year is deleted. Export first if unsure.',
    hardAction: async () => {
      const { data } = await api.clearYear(session.year)
      session.notify(`Deleted ${data.deleted} values`, 'warning')
    },
  }
}

function askResetPrefs() {
  confirm.value = {
    title: 'Reset appearance and settings?',
    text: 'Returns theme, currency, calendar and goals to defaults. Your amounts are untouched.',
    action: async () => {
      await session.resetPrefs()
      session.notify('Settings reset')
    },
  }
}

async function runConfirm(hard) {
  const item = confirm.value
  confirm.value = null
  try {
    await (hard && item.hardAction ? item.hardAction() : (item.action || item.hardAction)())
  } catch (error) {
    session.notify(errorMessage(error, 'That did not work'), 'error')
  }
}

watch(expandedSheet, async (slug) => {
  if (!slug) return
  const sheet = structure.bySlug(slug)
  if (sheet && !categories.value[slug]) await loadCategories(sheet)
})

onMounted(async () => {
  await structure.load(true)
  try {
    const { data } = await api.templates()
    templates.value = data
  } catch {
    templates.value = []
  }
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6" style="max-width: 1100px">
    <div class="text-h5 font-weight-bold mb-1">Settings</div>
    <div class="text-caption text-medium-emphasis mb-4">
      Make it yours — nothing here is fixed.
    </div>

    <v-tabs v-model="tab" class="mb-4" show-arrows color="primary">
      <v-tab value="appearance" prepend-icon="mdi-palette-outline">Look</v-tab>
      <v-tab value="money" prepend-icon="mdi-cash-multiple">Money</v-tab>
      <v-tab value="calendar" prepend-icon="mdi-calendar-range">Calendar</v-tab>
      <v-tab value="sheets" prepend-icon="mdi-table-large">Sheets</v-tab>
      <v-tab value="networth" prepend-icon="mdi-scale-balance">Net worth</v-tab>
      <v-tab value="goals" prepend-icon="mdi-target">Goals</v-tab>
      <v-tab value="data" prepend-icon="mdi-database-cog-outline">Data</v-tab>
    </v-tabs>

    <v-window v-model="tab">
      <!-- ------------------------------------------------ appearance -->
      <v-window-item value="appearance">
        <v-card class="pa-5 mb-4">
          <div class="section-title mb-4">Theme</div>
          <v-btn-toggle
            :model-value="prefs.theme"
            mandatory
            divided
            variant="outlined"
            class="mb-5"
            @update:model-value="update('theme')($event)"
          >
            <v-btn value="light" prepend-icon="mdi-weather-sunny">Light</v-btn>
            <v-btn value="dark" prepend-icon="mdi-weather-night">Dark</v-btn>
            <v-btn value="system" prepend-icon="mdi-monitor">System</v-btn>
          </v-btn-toggle>

          <div class="section-title mb-3">Accent colour</div>
          <div class="d-flex flex-wrap ga-2 align-center mb-5">
            <v-btn
              v-for="color in ACCENTS"
              :key="color"
              icon
              size="small"
              :style="{ background: color, border: prefs.accent === color ? '3px solid rgba(128,128,128,.6)' : 'none' }"
              @click="set({ accent: color })"
            />
            <input
              :value="prefs.accent"
              type="color"
              style="width: 36px; height: 36px; border: 0; background: none; cursor: pointer"
              @change="set({ accent: $event.target.value })"
            />
          </div>

          <v-row dense>
            <v-col cols="12" md="6">
              <v-select
                :model-value="prefs.density"
                :items="[{ title: 'Comfortable', value: 'comfortable' }, { title: 'Compact', value: 'compact' }]"
                label="Row density"
                @update:model-value="update('density')($event)"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                :model-value="prefs.rounded"
                :items="[
                  { title: 'Sharp', value: 'sm' },
                  { title: 'Soft', value: 'md' },
                  { title: 'Rounded', value: 'lg' },
                  { title: 'Pill', value: 'xl' },
                ]"
                label="Corner style"
                @update:model-value="update('rounded')($event)"
              />
            </v-col>
            <v-col cols="12">
              <div class="text-body-2 mt-3 mb-1">Text size</div>
              <v-slider
                :model-value="prefs.font_scale"
                :min="0.85"
                :max="1.25"
                :step="0.05"
                thumb-label
                color="primary"
                hide-details
                @end="update('font_scale')($event)"
              />
            </v-col>
          </v-row>
        </v-card>

        <v-card class="pa-5 mb-4">
          <div class="section-title mb-3">Identity</div>
          <v-row dense>
            <v-col cols="12" md="6">
              <v-text-field
                :model-value="prefs.app_name"
                label="App name"
                @update:model-value="update('app_name')($event)"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                :model-value="prefs.owner_name"
                label="Your name"
                placeholder="Shown on the dashboard"
                @update:model-value="update('owner_name')($event)"
              />
            </v-col>
          </v-row>
        </v-card>

        <v-card class="pa-5">
          <div class="section-title mb-3">Chart colours</div>
          <div class="d-flex flex-wrap ga-2 mb-3">
            <input
              v-for="(color, index) in prefs.chart_palette || []"
              :key="index"
              :value="color"
              type="color"
              style="width: 34px; height: 34px; border: 0; background: none; cursor: pointer"
              @change="
                set({
                  chart_palette: prefs.chart_palette.map((c, i) => (i === index ? $event.target.value : c)),
                })
              "
            />
          </div>
          <div class="section-title mb-3 mt-5">Sections in the sidebar</div>
          <v-chip-group
            :model-value="prefs.visible_sections"
            multiple
            column
            filter
            @update:model-value="update('visible_sections')($event)"
          >
            <v-chip v-for="section in SECTIONS" :key="section.value" :value="section.value" variant="outlined">
              {{ section.title }}
            </v-chip>
          </v-chip-group>
        </v-card>
      </v-window-item>

      <!-- ------------------------------------------------ money -->
      <v-window-item value="money">
        <v-card class="pa-5 mb-4">
          <div class="section-title mb-4">Currency</div>
          <v-row dense>
            <v-col cols="12" md="6">
              <v-select
                :model-value="prefs.currency"
                :items="CURRENCIES"
                label="Currency"
                @update:model-value="pickCurrency($event)"
              />
            </v-col>
            <v-col cols="12" md="3">
              <v-text-field
                :model-value="prefs.currency_symbol"
                label="Symbol"
                @update:model-value="update('currency_symbol')($event)"
              />
            </v-col>
            <v-col cols="12" md="3">
              <v-select
                :model-value="prefs.symbol_position"
                :items="[{ title: 'Before (¥100)', value: 'before' }, { title: 'After (100¥)', value: 'after' }]"
                label="Symbol position"
                @update:model-value="update('symbol_position')($event)"
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-select
                :model-value="prefs.decimals"
                :items="[{ title: 'None (1,200)', value: 0 }, { title: 'Two (1,200.00)', value: 2 }]"
                label="Decimals"
                @update:model-value="update('decimals')($event)"
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-select
                :model-value="prefs.negative_style"
                :items="[{ title: 'Minus (-100)', value: 'minus' }, { title: 'Brackets (100)', value: 'parentheses' }]"
                label="Negative numbers"
                @update:model-value="update('negative_style')($event)"
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field
                :model-value="prefs.locale"
                label="Number locale"
                placeholder="en-US"
                @update:model-value="update('locale')($event)"
              />
            </v-col>
          </v-row>

          <v-switch
            :model-value="prefs.thousands_separator"
            label="Thousands separator"
            color="primary"
            hide-details
            @update:model-value="update('thousands_separator')($event)"
          />
          <v-switch
            :model-value="prefs.compact_large_numbers"
            label="Shorten big numbers (1.2M)"
            color="primary"
            hide-details
            @update:model-value="update('compact_large_numbers')($event)"
          />

          <v-alert variant="tonal" class="mt-4" density="comfortable">
            Preview: <strong class="numeric">{{ formatMoney(1234567.89) }}</strong> ·
            <strong class="numeric">{{ formatMoney(-450) }}</strong>
          </v-alert>
        </v-card>

        <v-card class="pa-5">
          <div class="section-title mb-3">Entry behaviour</div>
          <div class="text-body-2 mb-1">Autosave delay — {{ prefs.autosave_delay_ms }}ms</div>
          <v-slider
            :model-value="prefs.autosave_delay_ms"
            :min="200"
            :max="2000"
            :step="100"
            thumb-label
            color="primary"
            hide-details
            class="mb-4"
            @end="update('autosave_delay_ms')($event)"
          />
          <v-switch
            :model-value="prefs.highlight_over_budget"
            label="Highlight categories over budget"
            color="primary"
            hide-details
            @update:model-value="update('highlight_over_budget')($event)"
          />
        </v-card>
      </v-window-item>

      <!-- ------------------------------------------------ calendar -->
      <v-window-item value="calendar">
        <v-card class="pa-5">
          <div class="section-title mb-4">Year and months</div>
          <v-row dense>
            <v-col cols="12" md="6">
              <v-select
                :model-value="prefs.fiscal_start_month"
                :items="MONTHS"
                label="Year starts in"
                @update:model-value="update('fiscal_start_month')($event)"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                :model-value="prefs.month_label_style"
                :items="[
                  { title: 'Short (Jan)', value: 'short' },
                  { title: 'Long (January)', value: 'long' },
                  { title: 'Numeric (01)', value: 'numeric' },
                ]"
                label="Month labels"
                @update:model-value="update('month_label_style')($event)"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                :model-value="prefs.start_page"
                :items="[
                  { title: 'Dashboard', value: 'dashboard' },
                  { title: 'Settings', value: 'settings' },
                ]"
                label="Open on"
                @update:model-value="update('start_page')($event)"
              />
            </v-col>
          </v-row>
          <v-alert variant="tonal" density="comfortable" class="mt-4">
            A non-January start shifts the grid columns only. Amounts stay attached to their real
            calendar month, so nothing shifts underneath you.
          </v-alert>
        </v-card>
      </v-window-item>

      <!-- ------------------------------------------------ sheets -->
      <v-window-item value="sheets">
        <v-card class="pa-5 mb-4">
          <div class="section-title mb-3">Add a sheet</div>
          <v-row dense align="center">
            <v-col cols="12" md="4">
              <v-text-field v-model="newSheet.name" label="Name" placeholder="e.g. Side hustle" />
            </v-col>
            <v-col cols="6" md="3">
              <v-select
                v-model="newSheet.kind"
                :items="[{ title: 'Money in', value: 'inflow' }, { title: 'Money out', value: 'outflow' }]"
                label="Direction"
              />
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field v-model="newSheet.plan_label" label="Plan column" />
            </v-col>
            <v-col cols="12" md="2">
              <v-btn color="primary" block :loading="busy" @click="addSheet">Add</v-btn>
            </v-col>
          </v-row>
        </v-card>

        <v-expansion-panels v-model="expandedSheet" variant="accordion">
          <v-expansion-panel v-for="sheet in structure.sheets" :key="sheet.id" :value="sheet.slug">
            <v-expansion-panel-title>
              <div class="d-flex align-center ga-3 flex-grow-1">
                <v-icon :color="sheet.color">{{ sheet.icon }}</v-icon>
                <span class="font-weight-medium">{{ sheet.name }}</span>
                <v-chip size="x-small" variant="tonal" :color="sheet.kind === 'inflow' ? 'success' : 'error'">
                  {{ sheet.kind === 'inflow' ? 'in' : 'out' }}
                </v-chip>
                <v-chip v-if="!sheet.is_active" size="x-small" variant="tonal">hidden</v-chip>
              </div>
            </v-expansion-panel-title>

            <v-expansion-panel-text>
              <v-row dense class="mb-2">
                <v-col cols="12" md="4">
                  <v-text-field
                    :model-value="sheet.name"
                    label="Name"
                    @update:model-value="saveSheet(sheet, { name: $event })"
                  />
                </v-col>
                <v-col cols="6" md="3">
                  <v-text-field
                    :model-value="sheet.plan_label"
                    label="Plan column label"
                    @update:model-value="saveSheet(sheet, { plan_label: $event })"
                  />
                </v-col>
                <v-col cols="6" md="3">
                  <v-text-field
                    :model-value="sheet.icon"
                    label="Icon (mdi-…)"
                    @update:model-value="saveSheet(sheet, { icon: $event })"
                  />
                </v-col>
                <v-col cols="12" md="2" class="d-flex align-center ga-2">
                  <input
                    :value="sheet.color"
                    type="color"
                    style="width: 34px; height: 34px; border: 0; background: none; cursor: pointer"
                    @change="saveSheet(sheet, { color: $event.target.value })"
                  />
                  <v-btn icon="mdi-arrow-up" size="small" variant="text" @click="moveSheet(sheet, -1)" />
                  <v-btn icon="mdi-arrow-down" size="small" variant="text" @click="moveSheet(sheet, 1)" />
                </v-col>
              </v-row>

              <div class="d-flex ga-4 flex-wrap mb-3">
                <v-switch
                  :model-value="sheet.show_plan"
                  label="Show plan column"
                  color="primary"
                  hide-details
                  density="compact"
                  @update:model-value="saveSheet(sheet, { show_plan: $event })"
                />
                <v-switch
                  :model-value="sheet.is_active"
                  label="Visible in sidebar"
                  color="primary"
                  hide-details
                  density="compact"
                  @update:model-value="saveSheet(sheet, { is_active: $event })"
                />
                <v-spacer />
                <v-btn color="error" variant="text" size="small" prepend-icon="mdi-delete-outline" @click="askDeleteSheet(sheet)">
                  Delete sheet
                </v-btn>
              </div>

              <v-divider class="mb-3" />
              <div class="section-title mb-2">
                Categories ({{ (categories[sheet.slug] || []).length }})
              </div>

              <v-text-field
                label="Add category"
                placeholder="Type a name and press Enter"
                prepend-inner-icon="mdi-plus"
                class="mb-3"
                @keyup.enter="addCategory(sheet, $event.target.value); $event.target.value = ''"
              />

              <v-list density="compact" class="bg-transparent" max-height="380" style="overflow-y: auto">
                <v-list-item
                  v-for="category in categories[sheet.slug] || []"
                  :key="category.id"
                  :title="category.name"
                  :subtitle="category.group_name || ''"
                  :class="{ 'text-disabled': !category.is_active }"
                >
                  <template #prepend>
                    <span class="row-color-dot mr-3" :style="{ background: category.color || 'rgba(128,128,128,.35)' }" />
                  </template>
                  <template #append>
                    <v-btn
                      :icon="category.is_active ? 'mdi-eye-outline' : 'mdi-eye-off-outline'"
                      size="x-small"
                      variant="text"
                      @click="toggleCategory(sheet, category)"
                    />
                    <v-btn icon="mdi-delete-outline" size="x-small" variant="text" @click="removeCategory(sheet, category)" />
                  </template>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-window-item>

      <!-- ------------------------------------------------ net worth -->
      <v-window-item value="networth">
        <v-row dense>
          <v-col v-for="side in ['asset', 'liability']" :key="side" cols="12" md="6">
            <v-card class="pa-5 h-100">
              <div class="section-title mb-3">{{ side === 'asset' ? 'Assets' : 'Liabilities' }}</div>
              <v-text-field
                v-model="newItem[side]"
                :label="side === 'asset' ? 'Add an asset' : 'Add a liability'"
                prepend-inner-icon="mdi-plus"
                class="mb-3"
                @keyup.enter="addNetworthItem(side)"
              />
              <v-list density="compact" class="bg-transparent">
                <v-list-item
                  v-for="item in side === 'asset' ? assets : liabilities"
                  :key="item.id"
                  :title="item.name"
                  :class="{ 'text-disabled': !item.is_active }"
                >
                  <template #prepend>
                    <span class="row-color-dot mr-3" :style="{ background: item.color || (side === 'asset' ? '#22C55E' : '#EF4444') }" />
                  </template>
                  <template #append>
                    <v-btn
                      :icon="item.is_active ? 'mdi-eye-outline' : 'mdi-eye-off-outline'"
                      size="x-small"
                      variant="text"
                      @click="structure.updateNetworthItem(item.id, { is_active: !item.is_active })"
                    />
                    <v-btn icon="mdi-delete-outline" size="x-small" variant="text" @click="askDeleteItem(item)" />
                  </template>
                </v-list-item>
              </v-list>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- ------------------------------------------------ goals -->
      <v-window-item value="goals">
        <v-card class="pa-5">
          <div class="section-title mb-4">What you're aiming for</div>
          <v-row dense>
            <v-col cols="12" md="6">
              <div class="text-body-2 mb-1">
                Savings rate target — {{ prefs.goals?.savings_rate_target }}%
              </div>
              <v-slider
                :model-value="prefs.goals?.savings_rate_target"
                :min="0"
                :max="70"
                :step="1"
                thumb-label
                color="primary"
                hide-details
                @end="updateGoal('savings_rate_target')($event)"
              />
            </v-col>
            <v-col cols="12" md="6">
              <div class="text-body-2 mb-1">
                Emergency fund — {{ prefs.goals?.emergency_fund_months }} months of spending
              </div>
              <v-slider
                :model-value="prefs.goals?.emergency_fund_months"
                :min="0"
                :max="24"
                :step="1"
                thumb-label
                color="primary"
                hide-details
                @end="updateGoal('emergency_fund_months')($event)"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                :model-value="prefs.goals?.monthly_savings_target"
                label="Monthly savings target"
                type="number"
                class="mt-4"
                @update:model-value="updateGoal('monthly_savings_target')($event)"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                :model-value="prefs.goals?.net_worth_target"
                label="Net worth target"
                type="number"
                class="mt-4"
                @update:model-value="updateGoal('net_worth_target')($event)"
              />
            </v-col>
          </v-row>
        </v-card>
      </v-window-item>

      <!-- ------------------------------------------------ data -->
      <v-window-item value="data">
        <v-card class="pa-5 mb-4">
          <div class="section-title mb-3">Starter templates</div>
          <div class="text-body-2 text-medium-emphasis mb-4">
            Load a ready-made set of sheets and categories. Everything stays editable afterwards.
          </div>
          <v-row dense align="center">
            <v-col cols="12" md="6">
              <v-select
                v-model="seedTemplate"
                :items="templates.map((t) => ({ title: `${t.name} — ${t.description}`, value: t.key }))"
                label="Template"
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-switch v-model="seedReplace" label="Replace everything" color="error" hide-details />
            </v-col>
            <v-col cols="12" md="2">
              <v-btn color="primary" block @click="runSeed">Apply</v-btn>
            </v-col>
          </v-row>
        </v-card>

        <v-card class="pa-5 mb-4">
          <div class="section-title mb-3">Start a new year</div>
          <div class="text-body-2 text-medium-emphasis mb-4">
            Copy last year's plan into this one so you're not retyping budgets every January.
          </div>
          <v-row dense align="center">
            <v-col cols="6" md="3">
              <v-text-field v-model.number="copySource" label="From year" type="number" />
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field v-model.number="copyTarget" label="To year" type="number" />
            </v-col>
            <v-col cols="12" md="4">
              <v-switch v-model="copyPlanOnly" label="Plan column only" color="primary" hide-details />
            </v-col>
            <v-col cols="12" md="2">
              <v-btn color="primary" block @click="runCopyYear">Copy</v-btn>
            </v-col>
          </v-row>
        </v-card>

        <v-card class="pa-5">
          <div class="section-title mb-3">Danger zone</div>
          <div class="d-flex flex-wrap ga-3">
            <v-btn variant="tonal" prepend-icon="mdi-backup-restore" @click="askResetPrefs">
              Reset settings
            </v-btn>
            <v-btn color="error" variant="tonal" prepend-icon="mdi-delete-sweep-outline" @click="askClearYear">
              Clear {{ session.year }} amounts
            </v-btn>
            <v-spacer />
            <v-btn variant="text" prepend-icon="mdi-tray-arrow-down" :to="{ name: 'export' }">
              Export first
            </v-btn>
          </div>
        </v-card>
      </v-window-item>
    </v-window>

    <v-dialog :model-value="Boolean(confirm)" max-width="460" @update:model-value="confirm = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-2">{{ confirm?.title }}</div>
        <div class="text-body-2 text-medium-emphasis">{{ confirm?.text }}</div>
        <div class="d-flex justify-end ga-2 mt-5 flex-wrap">
          <v-btn variant="text" @click="confirm = null">Cancel</v-btn>
          <v-btn v-if="confirm?.hardAction && confirm?.action" color="error" variant="tonal" @click="runConfirm(true)">
            Delete for good
          </v-btn>
          <v-btn :color="confirm?.action ? 'primary' : 'error'" @click="runConfirm(!confirm?.action)">
            {{ confirm?.action ? 'Confirm' : 'Yes, delete' }}
          </v-btn>
        </div>
      </v-card>
    </v-dialog>
  </v-container>
</template>
