<script setup>
import { computed, ref, watch } from 'vue'

import api, { errorMessage } from '@/api'
import PlotlyChart from '@/components/PlotlyChart.vue'
import StatCard from '@/components/StatCard.vue'
import { useFormat } from '@/composables/useFormat'
import { useSession } from '@/stores/session'

const session = useSession()
const { formatMoney, formatPercent } = useFormat()

const data = ref(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const response = await api.aggregates(session.year)
    data.value = response.data
    session.availableYears = response.data.available_years
  } catch (error) {
    session.notify(errorMessage(error, 'Could not load the dashboard'), 'error')
  } finally {
    loading.value = false
  }
}

watch(() => session.year, load, { immediate: true })

const labels = computed(() => (data.value?.months || []).map((m) => m.label))
const goals = computed(() => data.value?.goals || {})

const cashflowTraces = computed(() => {
  if (!data.value) return []
  return [
    {
      type: 'bar',
      name: 'Income',
      x: labels.value,
      y: data.value.inflow_monthly.map(Number),
      marker: { color: session.palette[1] || '#22C55E' },
    },
    {
      type: 'bar',
      name: 'Expenses',
      x: labels.value,
      y: data.value.outflow_monthly.map(Number),
      marker: { color: session.palette[3] || '#EF4444' },
    },
    {
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Balance',
      x: labels.value,
      y: data.value.balance_monthly.map(Number),
      line: { color: session.accent, width: 3, shape: 'spline' },
    },
  ]
})

const spendTraces = computed(() => {
  const outflow = (data.value?.sheets || []).filter((s) => s.sheet.kind === 'outflow')
  const rows = outflow
    .flatMap((s) => s.by_category)
    .filter((row) => Number(row.total) > 0)
    .sort((a, b) => Number(b.total) - Number(a.total))
    .slice(0, 8)
  if (!rows.length) return []
  return [
    {
      type: 'pie',
      hole: 0.62,
      labels: rows.map((r) => r.name),
      values: rows.map((r) => Number(r.total)),
      textinfo: 'percent',
      marker: { colors: rows.map((r, i) => r.color || session.palette[i % session.palette.length]) },
    },
  ]
})

const netWorthTrace = computed(() => {
  if (!data.value) return []
  return [
    {
      type: 'scatter',
      mode: 'lines',
      fill: 'tozeroy',
      name: 'Net worth',
      x: labels.value,
      y: data.value.net_worth_series.map(Number),
      line: { color: session.accent, width: 3, shape: 'spline' },
      fillcolor: `${session.accent}22`,
    },
  ]
})

const progress = computed(() => {
  const rate = Number(goals.value.savings_rate_actual || 0)
  const target = Number(goals.value.savings_rate_target || 0)
  return {
    rate,
    target,
    percent: target ? Math.min(100, Math.max(0, (rate / target) * 100)) : 0,
    netWorthPercent: goals.value.net_worth_target
      ? Math.min(100, Math.max(0, (Number(goals.value.net_worth_actual) / Number(goals.value.net_worth_target)) * 100))
      : 0,
    runway: Number(goals.value.emergency_fund_months_actual || 0),
    runwayTarget: Number(goals.value.emergency_fund_months || 0),
  }
})

const topSheets = computed(() => data.value?.sheets || [])
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="d-flex flex-wrap align-center mb-4 ga-2">
      <div>
        <div class="text-h5 font-weight-bold">
          {{ session.prefs?.owner_name ? `Hey ${session.prefs.owner_name}` : 'Dashboard' }}
        </div>
        <div class="text-caption text-medium-emphasis">Your {{ session.year }} at a glance</div>
      </div>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-tray-arrow-down" :to="{ name: 'export' }">Export</v-btn>
    </div>

    <v-row dense>
      <v-col cols="12" sm="6" lg="3">
        <StatCard
          label="Income"
          icon="mdi-trending-up"
          color="success"
          :loading="loading"
          :value="formatMoney(data?.total_inflow || 0)"
          :caption="`${session.year} total`"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <StatCard
          label="Expenses"
          icon="mdi-trending-down"
          color="error"
          :loading="loading"
          :value="formatMoney(data?.total_outflow || 0)"
          :caption="`${session.year} total`"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <StatCard
          label="Saved"
          icon="mdi-piggy-bank-outline"
          color="primary"
          :loading="loading"
          :value="formatMoney(data?.balance || 0)"
          :caption="`${formatPercent(data?.savings_rate || 0)} of income`"
        />
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <StatCard
          label="Net worth"
          icon="mdi-scale-balance"
          color="info"
          :loading="loading"
          :value="formatMoney(data?.net_worth_latest || 0)"
          :caption="`Assets ${formatMoney(data?.assets_latest || 0)} · Debt ${formatMoney(data?.liabilities_latest || 0)}`"
        />
      </v-col>
    </v-row>

    <v-row dense class="mt-1">
      <v-col cols="12" lg="8">
        <v-card class="pa-4">
          <div class="d-flex align-center mb-2">
            <div class="section-title">Money in vs out</div>
            <v-spacer />
            <v-chip size="small" variant="tonal" :color="Number(data?.balance) >= 0 ? 'success' : 'error'">
              {{ Number(data?.balance) >= 0 ? 'Surplus' : 'Deficit' }} {{ formatMoney(Math.abs(Number(data?.balance || 0))) }}
            </v-chip>
          </div>
          <PlotlyChart v-if="data" :traces="cashflowTraces" :height="330" :layout="{ barmode: 'group' }" />
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card class="pa-4 h-100">
          <div class="section-title mb-3">Goals</div>

          <div class="mb-4">
            <div class="d-flex justify-space-between text-body-2 mb-1">
              <span>Savings rate</span>
              <span class="numeric">{{ formatPercent(progress.rate) }} / {{ progress.target }}%</span>
            </div>
            <v-progress-linear
              :model-value="progress.percent"
              height="8"
              rounded
              :color="progress.rate >= progress.target ? 'success' : 'primary'"
            />
          </div>

          <div v-if="goals.net_worth_target" class="mb-4">
            <div class="d-flex justify-space-between text-body-2 mb-1">
              <span>Net worth target</span>
              <span class="numeric">{{ formatMoney(goals.net_worth_actual) }} / {{ formatMoney(goals.net_worth_target) }}</span>
            </div>
            <v-progress-linear :model-value="progress.netWorthPercent" height="8" rounded color="info" />
          </div>

          <div class="mb-4">
            <div class="d-flex justify-space-between text-body-2 mb-1">
              <span>Emergency runway</span>
              <span class="numeric">{{ progress.runway }} / {{ progress.runwayTarget }} months</span>
            </div>
            <v-progress-linear
              :model-value="progress.runwayTarget ? Math.min(100, (progress.runway / progress.runwayTarget) * 100) : 0"
              height="8"
              rounded
              color="warning"
            />
          </div>

          <v-btn variant="text" size="small" prepend-icon="mdi-target" :to="{ name: 'settings', query: { tab: 'goals' } }">
            Change targets
          </v-btn>
        </v-card>
      </v-col>
    </v-row>

    <v-row dense class="mt-1">
      <v-col cols="12" md="6">
        <v-card class="pa-4 h-100">
          <div class="section-title mb-2">Where the money goes</div>
          <PlotlyChart v-if="spendTraces.length" :traces="spendTraces" :height="300" />
          <div v-else class="text-medium-emphasis text-body-2 py-8 text-center">
            Add some expenses to see the breakdown.
          </div>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card class="pa-4 h-100">
          <div class="section-title mb-2">Net worth trend</div>
          <PlotlyChart v-if="data" :traces="netWorthTrace" :height="300" />
        </v-card>
      </v-col>
    </v-row>

    <v-row dense class="mt-1">
      <v-col v-for="summary in topSheets" :key="summary.sheet.id" cols="12" md="6" lg="4">
        <v-card class="pa-4 h-100">
          <div class="d-flex align-center ga-2 mb-3">
            <v-icon :color="summary.sheet.color" size="20">{{ summary.sheet.icon }}</v-icon>
            <span class="font-weight-medium">{{ summary.sheet.name }}</span>
            <v-spacer />
            <span class="numeric text-body-2">{{ formatMoney(summary.actual_total) }}</span>
          </div>
          <v-table density="compact" class="bg-transparent">
            <tbody>
              <tr v-for="row in summary.by_category.slice(0, 5)" :key="row.category_id">
                <td class="px-0">{{ row.name }}</td>
                <td class="px-0 text-right numeric">{{ formatMoney(row.total) }}</td>
              </tr>
            </tbody>
          </v-table>
          <v-btn
            variant="text"
            size="small"
            class="mt-2"
            :to="{ name: 'sheet', params: { slug: summary.sheet.slug } }"
          >
            Open sheet
          </v-btn>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
