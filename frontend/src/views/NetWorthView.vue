<script setup>
import { computed, ref, watch } from 'vue'

import api, { errorMessage } from '@/api'
import EditableGrid from '@/components/EditableGrid.vue'
import PlotlyChart from '@/components/PlotlyChart.vue'
import StatCard from '@/components/StatCard.vue'
import { useFormat } from '@/composables/useFormat'
import { useSession } from '@/stores/session'
import { useStructure } from '@/stores/structure'

const session = useSession()
const structure = useStructure()
const { formatMoney } = useFormat()

const data = ref(null)
const loading = ref(true)
const showInactive = ref(false)
const editing = ref(null)
const editForm = ref({ name: '', color: '', note: '', side: 'asset' })
const confirm = ref(null)

async function load() {
  loading.value = true
  try {
    const response = await api.networth(session.year, showInactive.value)
    data.value = response.data
  } catch (error) {
    session.notify(errorMessage(error, 'Could not load net worth'), 'error')
  } finally {
    loading.value = false
  }
}

watch(() => [session.year, showInactive.value], load, { immediate: true })

const assets = computed(() => (data.value?.assets || []).map((row) => ({ ...row, id: row.item_id })))
const liabilities = computed(() =>
  (data.value?.liabilities || []).map((row) => ({ ...row, id: row.item_id })),
)

const latest = computed(() => {
  if (!data.value) return { assets: 0, liabilities: 0, net: 0, change: 0 }
  const lastFilled = (series) => {
    const filled = series.map(Number).filter((v) => v !== 0)
    return filled.length ? filled[filled.length - 1] : 0
  }
  const net = data.value.net_worth.map(Number)
  const nonZero = net.filter((v) => v !== 0)
  return {
    assets: lastFilled(data.value.asset_totals),
    liabilities: lastFilled(data.value.liability_totals),
    net: nonZero.length ? nonZero[nonZero.length - 1] : 0,
    change: nonZero.length > 1 ? nonZero[nonZero.length - 1] - nonZero[0] : 0,
  }
})

const trend = computed(() => {
  if (!data.value) return []
  const labels = data.value.months.map((m) => m.label)
  return [
    {
      type: 'bar',
      name: 'Assets',
      x: labels,
      y: data.value.asset_totals.map(Number),
      marker: { color: session.palette[1] || '#22C55E' },
    },
    {
      type: 'bar',
      name: 'Liabilities',
      x: labels,
      y: data.value.liability_totals.map((v) => -Number(v)),
      marker: { color: session.palette[3] || '#EF4444' },
    },
    {
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Net worth',
      x: labels,
      y: data.value.net_worth.map(Number),
      line: { color: session.accent, width: 3, shape: 'spline' },
    },
  ]
})

const saveAsset = async ({ row, column, amount }) => {
  await api.patchNetworthValue({ item_id: row.id, year: column.year, month: column.month, amount })
}

async function addItem(side, name) {
  try {
    await structure.createNetworthItem({ side, name })
    await load()
    session.notify(`Added “${name}”`)
  } catch (error) {
    session.notify(errorMessage(error, 'Could not add that item'), 'error')
  }
}

function openEdit(row) {
  editing.value = row
  editForm.value = { name: row.name, color: row.color || '', note: row.note || '', side: row.side }
}

async function saveEdit() {
  try {
    await structure.updateNetworthItem(editing.value.id, {
      name: editForm.value.name.trim(),
      color: editForm.value.color || null,
      note: editForm.value.note || null,
      side: editForm.value.side,
    })
    editing.value = null
    await load()
    session.notify('Item updated')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not update that item'), 'error')
  }
}

function askRemove(row) {
  confirm.value = {
    title: `Delete ${row.name}?`,
    text: 'Hide it to keep the history, or delete it permanently with its balances.',
    action: async () => {
      await structure.deleteNetworthItem(row.id, false)
      await load()
    },
    hardAction: async () => {
      await structure.deleteNetworthItem(row.id, true)
      await load()
    },
  }
}

async function clearRow(row) {
  const patches = data.value.months.map((month) =>
    api.patchNetworthValue({ item_id: row.id, year: month.year, month: month.month, amount: null }),
  )
  await Promise.all(patches)
  await load()
  session.notify('Row cleared')
}

async function fillRow(row) {
  const filled = row.cells.map(Number).filter((v) => Number.isFinite(v) && v !== 0)
  if (!filled.length) {
    session.notify('Enter one balance first, then fill', 'warning')
    return
  }
  const value = filled[filled.length - 1]
  await Promise.all(
    data.value.months.map((month) =>
      api.patchNetworthValue({ item_id: row.id, year: month.year, month: month.month, amount: value }),
    ),
  )
  await load()
  session.notify('Balance copied across the year')
}

async function carryForward() {
  try {
    await api.carryForward(session.year, session.currentMonth)
    await load()
    session.notify('Last month’s balances copied forward')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not carry balances forward'), 'error')
  }
}

async function runConfirm(hard) {
  const item = confirm.value
  confirm.value = null
  try {
    await (hard ? item.hardAction() : item.action())
  } catch (error) {
    session.notify(errorMessage(error, 'That did not work'), 'error')
  }
}
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold">Net worth</div>
        <div class="text-caption text-medium-emphasis">
          Month-end balances for {{ session.year }}
        </div>
      </div>
      <v-spacer />
      <v-switch v-model="showInactive" label="Show hidden" density="compact" color="primary" hide-details class="flex-grow-0" />
      <v-btn variant="tonal" prepend-icon="mdi-content-duplicate" @click="carryForward">
        Carry forward
      </v-btn>
    </div>

    <v-row dense class="mb-1">
      <v-col cols="12" sm="4">
        <StatCard label="Assets" icon="mdi-bank-outline" color="success" :loading="loading" :value="formatMoney(latest.assets)" />
      </v-col>
      <v-col cols="12" sm="4">
        <StatCard label="Liabilities" icon="mdi-credit-card-outline" color="error" :loading="loading" :value="formatMoney(latest.liabilities)" />
      </v-col>
      <v-col cols="12" sm="4">
        <StatCard
          label="Net worth"
          icon="mdi-scale-balance"
          color="primary"
          :loading="loading"
          :value="formatMoney(latest.net)"
          :caption="`${latest.change >= 0 ? '+' : ''}${formatMoney(latest.change)} this year`"
        />
      </v-col>
    </v-row>

    <v-card class="pa-4 mb-4">
      <div class="section-title mb-2">Trend</div>
      <PlotlyChart v-if="data" :traces="trend" :height="320" :layout="{ barmode: 'relative' }" />
    </v-card>

    <v-card class="mb-4">
      <div class="px-4 py-3 font-weight-medium d-flex align-center ga-2">
        <v-icon color="success" size="20">mdi-bank-outline</v-icon> Assets
      </div>
      <v-divider />
      <EditableGrid
        v-if="data"
        :months="data.months"
        :rows="assets"
        :save="saveAsset"
        label-header="Asset"
        totals-label="Total assets"
        :show-row-totals="false"
        add-placeholder="Add an asset…"
        empty-text="No assets yet — add a savings account or investment below."
        :highlight-month="session.year === new Date().getFullYear() ? session.currentMonth : null"
        @add="(name) => addItem('asset', name)"
        @edit="openEdit"
        @remove="askRemove"
        @clear="clearRow"
        @fill="fillRow"
      />
    </v-card>

    <v-card>
      <div class="px-4 py-3 font-weight-medium d-flex align-center ga-2">
        <v-icon color="error" size="20">mdi-credit-card-outline</v-icon> Liabilities
      </div>
      <v-divider />
      <EditableGrid
        v-if="data"
        :months="data.months"
        :rows="liabilities"
        :save="saveAsset"
        label-header="Liability"
        totals-label="Total liabilities"
        :show-row-totals="false"
        add-placeholder="Add a debt…"
        empty-text="Nothing owed — nice."
        :highlight-month="session.year === new Date().getFullYear() ? session.currentMonth : null"
        @add="(name) => addItem('liability', name)"
        @edit="openEdit"
        @remove="askRemove"
        @clear="clearRow"
        @fill="fillRow"
      />
    </v-card>

    <v-dialog :model-value="Boolean(editing)" max-width="440" @update:model-value="editing = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-4">Edit item</div>
        <v-text-field v-model="editForm.name" label="Name" class="mb-3" />
        <v-select
          v-model="editForm.side"
          :items="[{ title: 'Asset', value: 'asset' }, { title: 'Liability', value: 'liability' }]"
          label="Type"
          class="mb-3"
        />
        <v-text-field v-model="editForm.color" label="Colour" placeholder="#22C55E" class="mb-3">
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

    <v-dialog :model-value="Boolean(confirm)" max-width="440" @update:model-value="confirm = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-2">{{ confirm?.title }}</div>
        <div class="text-body-2 text-medium-emphasis">{{ confirm?.text }}</div>
        <div class="d-flex justify-end ga-2 mt-5 flex-wrap">
          <v-btn variant="text" @click="confirm = null">Cancel</v-btn>
          <v-btn color="error" variant="tonal" @click="runConfirm(true)">Delete for good</v-btn>
          <v-btn color="primary" @click="runConfirm(false)">Hide</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </v-container>
</template>
