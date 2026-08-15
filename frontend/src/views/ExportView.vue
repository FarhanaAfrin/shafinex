<script setup>
import { ref } from 'vue'

import api, { errorMessage } from '@/api'
import { useSession } from '@/stores/session'

const session = useSession()
const busy = ref(false)

async function download(year) {
  busy.value = true
  try {
    const response = await api.exportWorkbook(year)
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${(session.appName || 'finance').toLowerCase().replace(/\s+/g, '-')}-${year}.xlsx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    session.notify('Workbook downloaded')
  } catch (error) {
    session.notify(errorMessage(error, 'Export failed'), 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6" style="max-width: 900px">
    <div class="text-h5 font-weight-bold mb-1">Export</div>
    <div class="text-caption text-medium-emphasis mb-5">
      One file, everything in it. This is also your backup — do it monthly.
    </div>

    <v-card class="pa-5 mb-4">
      <div class="d-flex flex-wrap align-center ga-4">
        <v-avatar color="success" variant="tonal" rounded="lg" size="48">
          <v-icon color="success">mdi-microsoft-excel</v-icon>
        </v-avatar>
        <div class="flex-grow-1" style="min-width: 200px">
          <div class="font-weight-medium">{{ session.year }} workbook</div>
          <div class="text-caption text-medium-emphasis">
            Dashboard, every sheet, net worth and your settings — as .xlsx
          </div>
        </div>
        <v-btn color="primary" size="large" :loading="busy" prepend-icon="mdi-download" @click="download(session.year)">
          Download
        </v-btn>
      </div>
    </v-card>

    <v-card class="pa-5">
      <div class="section-title mb-3">Other years</div>
      <div class="d-flex flex-wrap ga-2">
        <v-btn
          v-for="year in session.availableYears"
          :key="year"
          variant="tonal"
          size="small"
          :loading="busy"
          @click="download(year)"
        >
          {{ year }}
        </v-btn>
      </div>
      <v-alert type="info" variant="tonal" class="mt-5" density="comfortable">
        Your data is never locked in. Every export is a plain Excel file you can open, keep, or
        move somewhere else.
      </v-alert>
    </v-card>
  </v-container>
</template>
