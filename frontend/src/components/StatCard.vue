<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: String, required: true },
  caption: { type: String, default: '' },
  icon: { type: String, default: 'mdi-cash' },
  color: { type: String, default: 'primary' },
  trend: { type: Number, default: null },
  loading: { type: Boolean, default: false },
})
</script>

<template>
  <v-card class="pa-4 h-100">
    <div class="d-flex align-start justify-space-between ga-3">
      <div class="min-w-0">
        <div class="section-title mb-1">{{ label }}</div>
        <v-skeleton-loader v-if="loading" type="text" width="120" />
        <div v-else class="stat-value numeric text-truncate" :title="value">{{ value }}</div>
        <div v-if="caption" class="text-caption text-medium-emphasis mt-1">{{ caption }}</div>
      </div>
      <v-avatar :color="`${color}`" variant="tonal" rounded="lg" size="40">
        <v-icon :color="color">{{ icon }}</v-icon>
      </v-avatar>
    </div>
    <div v-if="trend !== null" class="mt-2 d-flex align-center ga-1">
      <v-icon size="16" :color="trend >= 0 ? 'success' : 'error'">
        {{ trend >= 0 ? 'mdi-trending-up' : 'mdi-trending-down' }}
      </v-icon>
      <span class="text-caption" :class="trend >= 0 ? 'text-success' : 'text-error'">
        {{ Math.abs(trend).toFixed(1) }}%
      </span>
    </div>
  </v-card>
</template>

<style scoped>
.min-w-0 {
  min-width: 0;
}
</style>
