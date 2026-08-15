<script setup>
import { computed, ref, watch } from 'vue'

import api, { errorMessage } from '@/api'
import PlotlyChart from '@/components/PlotlyChart.vue'
import { useFormat } from '@/composables/useFormat'
import { useSession } from '@/stores/session'

const session = useSession()
const { formatMoney, formatPercent } = useFormat()

const data = ref(null)
const loading = ref(true)
const selectedSheet = ref(null)
const chartType = ref('bar')

async function load() {
  loading.value = true
  try {
    const response = await api.aggregates(session.year)
    data.value = response.data
    if (!selectedSheet.value && response.data.sheets.length) {
      const outflow = response.data.sheets.find((s) => s.sheet.kind === 'outflow')
      selectedSheet.value = (outflow || response.data.sheets[0]).sheet.slug
    }
  } catch (error) {
    session.notify(errorMessage(error, 'Could not load charts'), 'error')
  } finally {
    loading.value = false
  }
}

watch(() => session.year, load, { immediate: true })

const labels = computed(() => (data.value?.months || []).map((m) => m.label))
const sheetOptions = computed(() =>
  (data.value?.sheets || []).map((s) => ({ title: s.sheet.name, value: s.sheet.slug })),
)
const active = computed(() =>
  (data.value?.sheets || []).find((s) => s.sheet.slug === selectedSheet.value),
)

const breakdown = computed(() => {
  const rows = (active.value?.by_category || []).filter((r) => Number(r.total) !== 0)
  if (!rows.length) return []
  const colors = rows.map((r, i) => r.color || session.palette[i % session.palette.length])

  if (chartType.value === 'pie') {
    return [
      {
        type: 'pie',
        hole: 0.6,
        labels: rows.map((r) => r.name),
        values: rows.map((r) => Number(r.total)),
        marker: { colors },
      },
    ]
  }
  const sorted = [...rows].sort((a, b) => Number(a.total) - Number(b.total))
  return [
    {
      type: 'bar',
      orientation: 'h',
      x: sorted.map((r) => Number(r.total)),
      y: sorted.map((r) => r.name),
      marker: { color: colors },
    },
  ]
})

const planVsActual = computed(() => {
  const rows = (active.value?.by_category || []).filter(
    (r) => Number(r.total) !== 0 || Number(r.plan || 0) !== 0,
  )
  if (!rows.length) return []
  return [
    {
      type: 'bar',
      name: active.value.sheet.plan_label,
      x: rows.map((r) => r.name),
      y: rows.map((r) => Number(r.plan || 0)),
      marker: { color: session.palette[0] },
    },
    {
      type: 'bar',
      name: 'Actual',
      x: rows.map((r) => r.name),
      y: rows.map((r) => Number(r.total)),
      marker: { color: session.palette[2] || '#F59E0B' },
    },
  ]
})

const cumulative = computed(() => {
  if (!data.value) return []
  return [
    {
      type: 'scatter',
      mode: 'lines',
      name: 'Cumulative savings',
      x: labels.value,
      y: data.value.cumulative_balance.map(Number),
      fill: 'tozeroy',
      line: { color: session.accent, width: 3, shape: 'spline' },
      fillcolor: `${session.accent}22`,
    },
  ]
})

const savingsRate = computed(() => {
  if (!data.value) return []
  const rates = data.value.months.map((_, index) => {
    const income = Number(data.value.inflow_monthly[index])
    const spend = Number(data.value.outflow_monthly[index])
    return income ? ((income - spend) / income) * 100 : 0
  })
  return [
    {
      type: 'bar',
      name: 'Savings rate',
      x: labels.value,
      y: rates,
      marker: { color: rates.map((r) => (r >= (data.value.goals.savings_rate_target || 0) ? session.palette[1] : session.palette[3])) },
    },
  ]
})

const monthlyTrend = computed(() => {
  if (!data.value) return []
  return (data.value.sheets || []).map((summary, index) => ({
    type: 'scatter',
    mode: 'lines+markers',
    name: summary.sheet.name,
    x: labels.value,
    y: summary.monthly.map(Number),
    line: {
      color: summary.sheet.color || session.palette[index % session.palette.length],
      width: 2.5,
      shape: 'spline',
    },
  }))
})
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold">Charts</div>
        <div class="text-caption text-medium-emphasis">{{ session.year }}</div>
      </div>
      <v-spacer />
      <v-select
        v-model="selectedSheet"
        :items="sheetOptions"
        density="compact"
        hide-details
        style="max-width: 220px"
      />
      <v-btn-toggle v-model="chartType" density="compact" mandatory variant="outlined" divided>
        <v-btn value="bar" icon="mdi-chart-bar" size="small" />
        <v-btn value="pie" icon="mdi-chart-donut" size="small" />
      </v-btn-toggle>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-3" />

    <v-row dense>
      <v-col cols="12" lg="6">
        <v-card class="pa-4 h-100">
          <div class="section-title mb-2">{{ active?.sheet.name }} by category</div>
          <PlotlyChart
            v-if="breakdown.length"
            :traces="breakdown"
            :height="380"
            :layout="{ margin: { l: 150, r: 20, t: 20, b: 40 } }"
          />
          <div v-else class="text-medium-emphasis text-center py-10">Nothing recorded yet.</div>
        </v-card>
      </v-col>

      <v-col cols="12" lg="6">
        <v-card class="pa-4 h-100">
          <div class="section-title mb-2">Plan vs actual</div>
          <PlotlyChart
            v-if="planVsActual.length"
            :traces="planVsActual"
            :height="380"
            :layout="{ barmode: 'group', xaxis: { tickangle: -35 } }"
          />
          <div v-else class="text-medium-emphasis text-center py-10">
            Set a plan on the sheet to compare.
          </div>
        </v-card>
      </v-col>

      <v-col cols="12" lg="6">
        <v-card class="pa-4 h-100">
          <div class="section-title mb-2">Monthly trend by sheet</div>
          <PlotlyChart v-if="data" :traces="monthlyTrend" :height="330" />
        </v-card>
      </v-col>

      <v-col cols="12" lg="6">
        <v-card class="pa-4 h-100">
          <div class="section-title mb-2">Cumulative savings</div>
          <PlotlyChart v-if="data" :traces="cumulative" :height="330" />
        </v-card>
      </v-col>

      <v-col cols="12">
        <v-card class="pa-4">
          <div class="d-flex align-center mb-2">
            <div class="section-title">Savings rate by month</div>
            <v-spacer />
            <v-chip size="small" variant="tonal">
              Target {{ formatPercent(data?.goals?.savings_rate_target || 0, 0) }} · Actual
              {{ formatPercent(data?.savings_rate || 0) }}
            </v-chip>
          </div>
          <PlotlyChart
            v-if="data"
            :traces="savingsRate"
            :height="280"
            :layout="{ yaxis: { ticksuffix: '%', tickformat: '.0f' } }"
          />
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
