<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTheme } from 'vuetify'
import Plotly from 'plotly.js-basic-dist-min'

import { useSession } from '@/stores/session'

const props = defineProps({
  traces: { type: Array, required: true },
  layout: { type: Object, default: () => ({}) },
  height: { type: Number, default: 320 },
})

const container = ref(null)
const theme = useTheme()
const session = useSession()

/** Charts follow the app theme rather than Plotly's defaults. */
function themedLayout() {
  const colors = theme.current.value.colors
  const ink = theme.current.value.dark ? '#E2E8F0' : '#1E293B'
  const grid = theme.current.value.dark ? 'rgba(226,232,240,.12)' : 'rgba(15,23,42,.08)'

  return {
    height: props.height,
    margin: { l: 56, r: 20, t: 28, b: 44 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    colorway: session.palette,
    font: { color: ink, family: 'Inter, system-ui, sans-serif', size: 12 },
    xaxis: { gridcolor: grid, zerolinecolor: grid, automargin: true },
    yaxis: { gridcolor: grid, zerolinecolor: grid, automargin: true, tickformat: ',.0f' },
    legend: { orientation: 'h', y: -0.2, font: { size: 11 } },
    hoverlabel: { bgcolor: colors.surface, bordercolor: grid, font: { color: ink } },
    ...props.layout,
  }
}

function draw() {
  if (!container.value) return
  Plotly.react(container.value, props.traces, themedLayout(), {
    displayModeBar: false,
    responsive: true,
  })
}

onMounted(draw)
watch(() => [props.traces, props.layout, theme.global.name.value, session.palette], draw, {
  deep: true,
})
onBeforeUnmount(() => {
  if (container.value) Plotly.purge(container.value)
})
</script>

<template>
  <div ref="container" :style="{ minHeight: `${height}px`, width: '100%' }" />
</template>
