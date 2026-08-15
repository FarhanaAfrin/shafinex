import { defineStore } from 'pinia'
import api from '@/api'

/** Sheets and net-worth items — the customizable skeleton of the app. */
export const useStructure = defineStore('structure', {
  state: () => ({
    sheets: [],
    networthItems: [],
    loaded: false,
  }),

  getters: {
    activeSheets: (state) => state.sheets.filter((s) => s.is_active),
    bySlug: (state) => (slug) => state.sheets.find((s) => s.slug === slug),
  },

  actions: {
    async load(force = false) {
      if (this.loaded && !force) return
      const [sheets, items] = await Promise.all([
        api.sheets(true),
        api.networthItems(true),
      ])
      this.sheets = sheets.data
      this.networthItems = items.data
      this.loaded = true
    },

    async createSheet(payload) {
      const { data } = await api.createSheet(payload)
      this.sheets.push(data)
      return data
    },

    async updateSheet(id, payload) {
      const { data } = await api.updateSheet(id, payload)
      const index = this.sheets.findIndex((s) => s.id === id)
      if (index !== -1) this.sheets[index] = data
      return data
    },

    async deleteSheet(id, hard = false) {
      await api.deleteSheet(id, hard)
      if (hard) this.sheets = this.sheets.filter((s) => s.id !== id)
      else {
        const sheet = this.sheets.find((s) => s.id === id)
        if (sheet) sheet.is_active = false
      }
    },

    async reorderSheets(ids) {
      const { data } = await api.reorderSheets(ids)
      this.sheets = data
    },

    async createNetworthItem(payload) {
      const { data } = await api.createNetworthItem(payload)
      this.networthItems.push(data)
      return data
    },

    async updateNetworthItem(id, payload) {
      const { data } = await api.updateNetworthItem(id, payload)
      const index = this.networthItems.findIndex((i) => i.id === id)
      if (index !== -1) this.networthItems[index] = data
      return data
    },

    async deleteNetworthItem(id, hard = false) {
      await api.deleteNetworthItem(id, hard)
      if (hard) this.networthItems = this.networthItems.filter((i) => i.id !== id)
      else {
        const item = this.networthItems.find((i) => i.id === id)
        if (item) item.is_active = false
      }
    },
  },
})
