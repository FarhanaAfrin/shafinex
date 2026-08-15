import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

const light = {
  dark: false,
  colors: {
    background: '#F6F7FB',
    surface: '#FFFFFF',
    'surface-variant': '#EEF1F7',
    primary: '#6366F1',
    secondary: '#0EA5E9',
    success: '#22C55E',
    warning: '#F59E0B',
    error: '#EF4444',
    info: '#0EA5E9',
  },
}

const dark = {
  dark: true,
  colors: {
    background: '#0B1020',
    surface: '#141A2E',
    'surface-variant': '#1E263F',
    primary: '#818CF8',
    secondary: '#38BDF8',
    success: '#4ADE80',
    warning: '#FBBF24',
    error: '#F87171',
    info: '#38BDF8',
  },
}

export default createVuetify({
  icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
  theme: {
    defaultTheme: 'light',
    themes: { light, dark },
    variations: { colors: ['primary', 'success', 'error', 'warning'], lighten: 4, darken: 3 },
  },
  defaults: {
    VCard: { rounded: 'lg', flat: true, border: true },
    VBtn: { rounded: 'lg', variant: 'flat' },
    VTextField: { variant: 'outlined', density: 'comfortable', hideDetails: 'auto' },
    VSelect: { variant: 'outlined', density: 'comfortable', hideDetails: 'auto' },
    VTextarea: { variant: 'outlined', density: 'comfortable', hideDetails: 'auto' },
    VChip: { rounded: 'lg' },
  },
})
