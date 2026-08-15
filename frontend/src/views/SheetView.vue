<script setup>
/** One customizable sheet: categories x months, plus a plan column. */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import api, { errorMessage } from '@/api'
import EditableGrid from '@/components/EditableGrid.vue'
import { useFormat } from '@/composables/useFormat'
import { useSession } from '@/stores/session'
import { useStructure } from '@/stores/structure'

const props = defineProps({ slug: { type: String, required: true } })

const session = useSession()
const structure = useStructure()
const router = useRouter()
const { formatMoney } = useFormat()

const grid = ref(null)
const loading = ref(true)
const search = ref('')
const showInactive = ref(false)

const editing = ref(null)
const editForm = ref({ name: '', group_name: '', color: '', note: '' })
const fillTarget = ref(null)
const fillAmount = ref('')
const fillFrom = ref(1)
const confirm = ref(null)

const sheet = computed(() => grid.value?.sheet || structure.bySlug(props.slug))

const rows = computed(() => {
  if (!grid.value) return []
  const term = search.value.trim().toLowerCase()
  return grid.value.rows
    .filter((row) => !term || row.name.toLowerCase().includes(term) || (row.group_name || '').toLowerCase().includes(term))
    .map((row) => ({
      ...row,
      id: row.category_id,
      varianceSign: sheet.value?.kind === 'inflow' ? -1 : 1,
    }))
})

const groups = computed(() => [...new Set((grid.value?.rows || []).map((r) => r.group_name).filter(Boolean))])

/** The workbook's Balance row — income minus expenditure, per month. */
const footerRows = computed(() => {
  if (!grid.value?.balance_row) return []
  return [
    {
      label: 'Balance',
      plan: grid.value.balance_plan === null ? null : Number(grid.value.balance_plan),
      values: grid.value.balance_row.map(Number),
      signed: true,
    },
  ]
})

/** Fed live by the grid so the cards move as you type, not only after a reload. */
const liveTotals = ref(null)

const summary = computed(() => {
  if (!grid.value) return { planned: 0, actual: 0, left: 0 }
  const planned = Number(liveTotals.value?.plan ?? grid.value.plan_total)
  const actual = Number(liveTotals.value?.actual ?? grid.value.grand_total)
  return { planned, actual, left: sheet.value?.kind === 'inflow' ? actual - planned : planned - actual }
})

async function load() {
  loading.value = true
  try {
    const { data } = await api.grid(props.slug, session.year, showInactive.value)
    grid.value = data
  } catch (error) {
    session.notify(errorMessage(error, 'Could not load this sheet'), 'error')
    if (error?.response?.status === 404) router.push({ name: 'dashboard' })
  } finally {
    loading.value = false
  }
}

watch(() => [props.slug, session.year, showInactive.value], load, { immediate: true })

async function saveCell({ row, column, amount }) {
  await api.patchValue({
    category_id: row.id,
    year: column.plan ? session.year : column.year,
    month: column.plan ? 0 : column.month,
    kind: column.plan ? 'plan' : 'actual',
    amount,
  })
}

async function addCategory(name) {
  try {
    await api.createCategory({ sheet_id: sheet.value.id, name })
    session.notify(`Added “${name}”`)
    await load()
  } catch (error) {
    session.notify(errorMessage(error, 'Could not add that category'), 'error')
  }
}

function openEdit(row) {
  editing.value = row
  editForm.value = {
    name: row.name,
    group_name: row.group_name || '',
    color: row.color || '',
    note: row.note || '',
  }
}

async function saveEdit() {
  try {
    await api.updateCategory(editing.value.id, {
      name: editForm.value.name.trim(),
      group_name: editForm.value.group_name || null,
      color: editForm.value.color || null,
      note: editForm.value.note || null,
    })
    editing.value = null
    await load()
    session.notify('Category updated')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not update that category'), 'error')
  }
}

function openFill(row) {
  fillTarget.value = row
  fillAmount.value = ''
  fillFrom.value = 1
}

async function applyFill() {
  try {
    await api.fillRow({
      category_id: fillTarget.value.id,
      year: session.year,
      amount: fillAmount.value === '' ? null : Number(fillAmount.value),
      from_month: Number(fillFrom.value),
    })
    fillTarget.value = null
    await load()
    session.notify('Row filled')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not fill that row'), 'error')
  }
}

function askClear(row) {
  confirm.value = {
    title: `Clear ${row.name}?`,
    text: `Every ${session.year} amount in this row will be removed. The category stays.`,
    action: async () => {
      await api.fillRow({ category_id: row.id, year: session.year, amount: null, from_month: 1 })
      await load()
      session.notify('Row cleared')
    },
  }
}

function askRemove(row) {
  confirm.value = {
    title: `Delete ${row.name}?`,
    text: 'Hide it to keep the history, or delete it permanently along with its amounts.',
    hideLabel: 'Hide',
    deleteLabel: 'Delete for good',
    action: async () => {
      await api.deleteCategory(row.id, false)
      await load()
      session.notify(`“${row.name}” hidden`)
    },
    hardAction: async () => {
      await api.deleteCategory(row.id, true)
      await load()
      session.notify(`“${row.name}” deleted`)
    },
  }
}

async function move({ row, direction }) {
  const ids = grid.value.rows.map((r) => r.category_id)
  const index = ids.indexOf(row.id)
  const target = index + direction
  if (target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  await api.reorderCategories(ids)
  await load()
}

async function runConfirm(hard = false) {
  const item = confirm.value
  confirm.value = null
  try {
    await (hard && item.hardAction ? item.hardAction() : item.action())
  } catch (error) {
    session.notify(errorMessage(error, 'That did not work'), 'error')
  }
}
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold d-flex align-center ga-2">
          <v-icon :color="sheet?.color">{{ sheet?.icon }}</v-icon>
          {{ sheet?.name }}
        </div>
        <div class="text-caption text-medium-emphasis">
          {{ session.year }} · {{ rows.length }} categories
        </div>
      </div>

      <v-spacer />

      <v-text-field
        v-model="search"
        placeholder="Filter categories"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        hide-details
        clearable
        style="max-width: 240px"
      />

      <v-btn variant="tonal" prepend-icon="mdi-tune" :to="{ name: 'settings', query: { tab: 'sheets' } }">
        Customize
      </v-btn>
    </div>

    <v-row dense class="mb-2">
      <v-col cols="12" sm="4">
        <v-card class="pa-3">
          <div class="section-title">{{ sheet?.plan_label || 'Planned' }}</div>
          <div class="text-h6 numeric">{{ formatMoney(summary.planned) }}</div>
        </v-card>
      </v-col>
      <v-col cols="12" sm="4">
        <v-card class="pa-3">
          <div class="section-title">Actual</div>
          <div class="text-h6 numeric">{{ formatMoney(summary.actual) }}</div>
        </v-card>
      </v-col>
      <v-col cols="12" sm="4">
        <v-card class="pa-3">
          <div class="section-title">{{ sheet?.kind === 'inflow' ? 'Above plan' : 'Left to spend' }}</div>
          <div
            class="text-h6 numeric"
            :class="summary.left < 0 ? 'over-budget' : 'under-budget'"
          >
            {{ formatMoney(summary.left) }}
          </div>
        </v-card>
      </v-col>
    </v-row>

    <v-card>
      <div class="d-flex align-center ga-2 px-3 py-2 flex-wrap">
        <v-switch
          v-model="showInactive"
          label="Show hidden"
          density="compact"
          color="primary"
          hide-details
          class="flex-grow-0"
        />
        <v-spacer />
        <span class="text-caption text-medium-emphasis d-none d-md-inline">
          Arrow keys move · Enter goes down · type 1.2k or 900+50
        </span>
      </div>
      <v-divider />

      <v-progress-linear v-if="loading" indeterminate color="primary" />

      <EditableGrid
        v-if="grid"
        :months="grid.months"
        :rows="rows"
        :save="saveCell"
        :show-plan="sheet?.show_plan"
        :plan-label="sheet?.plan_label"
        :show-variance="sheet?.show_plan"
        :variance-label="sheet?.kind === 'inflow' ? 'vs plan' : 'Left'"
        :highlight-month="session.year === new Date().getFullYear() ? session.currentMonth : null"
        :footer-rows="footerRows"
        :add-placeholder="`Add a ${sheet?.kind === 'inflow' ? 'income source' : 'spending category'}…`"
        @totals="liveTotals = $event"
        @add="addCategory"
        @edit="openEdit"
        @fill="openFill"
        @clear="askClear"
        @remove="askRemove"
        @move="move"
      />
    </v-card>

    <!-- edit category -->
    <v-dialog :model-value="Boolean(editing)" max-width="460" @update:model-value="editing = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-4">Edit category</div>
        <v-text-field v-model="editForm.name" label="Name" class="mb-3" />
        <v-combobox
          v-model="editForm.group_name"
          :items="groups"
          label="Group (optional)"
          class="mb-3"
          variant="outlined"
          density="comfortable"
          hide-details
        />
        <v-text-field v-model="editForm.color" label="Colour" placeholder="#6366F1" class="mb-3">
          <template #append-inner>
            <input v-model="editForm.color" type="color" style="width: 26px; height: 26px; border: 0; background: none" />
          </template>
        </v-text-field>
        <v-textarea v-model="editForm.note" label="Note (optional)" rows="2" />
        <div class="d-flex justify-end ga-2 mt-4">
          <v-btn variant="text" @click="editing = null">Cancel</v-btn>
          <v-btn color="primary" @click="saveEdit">Save</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <!-- fill row -->
    <v-dialog :model-value="Boolean(fillTarget)" max-width="420" @update:model-value="fillTarget = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-1">Fill “{{ fillTarget?.name }}”</div>
        <div class="text-caption text-medium-emphasis mb-4">
          Repeat one amount across the rest of the year — useful for rent or subscriptions.
        </div>
        <v-text-field v-model="fillAmount" label="Amount" type="number" class="mb-3" />
        <v-select
          v-model="fillFrom"
          :items="(grid?.months || []).map((m, i) => ({ title: `From ${m.label}`, value: i + 1 }))"
          label="Starting month"
        />
        <div class="d-flex justify-end ga-2 mt-4">
          <v-btn variant="text" @click="fillTarget = null">Cancel</v-btn>
          <v-btn color="primary" @click="applyFill">Fill</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <!-- confirm -->
    <v-dialog :model-value="Boolean(confirm)" max-width="440" @update:model-value="confirm = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-2">{{ confirm?.title }}</div>
        <div class="text-body-2 text-medium-emphasis">{{ confirm?.text }}</div>
        <div class="d-flex justify-end ga-2 mt-5 flex-wrap">
          <v-btn variant="text" @click="confirm = null">Cancel</v-btn>
          <v-btn v-if="confirm?.hardAction" color="error" variant="tonal" @click="runConfirm(true)">
            {{ confirm?.deleteLabel }}
          </v-btn>
          <v-btn color="primary" @click="runConfirm(false)">{{ confirm?.hideLabel || 'Confirm' }}</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </v-container>
</template>
