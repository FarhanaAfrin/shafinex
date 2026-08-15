import axios from 'axios'

const client = axios.create({ baseURL: '/api', timeout: 60000 })

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) onUnauthorized()
    return Promise.reject(error)
  },
)

export function errorMessage(error, fallback = 'Something went wrong') {
  return error?.response?.data?.detail || error?.message || fallback
}

export const api = {
  // auth
  login: (password) => client.post('/auth/login', { password }),
  me: () => client.get('/auth/me'),

  // bootstrap
  meta: () => client.get('/meta'),
  preferences: () => client.get('/preferences'),
  savePreferences: (patch) => client.patch('/preferences', patch),
  resetPreferences: () => client.post('/preferences/reset'),
  templates: () => client.get('/structure/templates'),
  seed: (template, replace) =>
    client.post(`/structure/seed?template=${template}&replace=${replace ? 'true' : 'false'}`),

  // sheets & categories
  sheets: (includeInactive = false) =>
    client.get(`/sheets?include_inactive=${includeInactive}`),
  createSheet: (payload) => client.post('/sheets', payload),
  updateSheet: (id, payload) => client.patch(`/sheets/${id}`, payload),
  deleteSheet: (id, hard = false) => client.delete(`/sheets/${id}?hard=${hard}`),
  reorderSheets: (ids) => client.post('/sheets/reorder', { ids }),

  categories: (slug, includeInactive = false) =>
    client.get(`/categories?${slug ? `sheet=${slug}&` : ''}include_inactive=${includeInactive}`),
  createCategory: (payload) => client.post('/categories', payload),
  updateCategory: (id, payload) => client.patch(`/categories/${id}`, payload),
  deleteCategory: (id, hard = false) => client.delete(`/categories/${id}?hard=${hard}`),
  reorderCategories: (ids) => client.post('/categories/reorder', { ids }),

  // grid
  grid: (slug, year, includeInactive = false) =>
    client.get(`/grid?sheet=${slug}&year=${year}&include_inactive=${includeInactive}`),
  patchValue: (payload) => client.patch('/values', payload),
  patchValues: (patches) => client.patch('/values/bulk', { patches }),
  fillRow: (payload) => client.post('/values/fill-row', payload),
  copyYear: (source, target, planOnly = true, overwrite = false) =>
    client.post(
      `/values/copy-year?source=${source}&target=${target}&plan_only=${planOnly}&overwrite=${overwrite}`,
    ),
  clearYear: (year, slug) =>
    client.delete(`/values/year?year=${year}${slug ? `&sheet=${slug}` : ''}`),

  // net worth
  networth: (year, includeInactive = false) =>
    client.get(`/networth?year=${year}&include_inactive=${includeInactive}`),
  networthItems: (includeInactive = false) =>
    client.get(`/networth-items?include_inactive=${includeInactive}`),
  createNetworthItem: (payload) => client.post('/networth-items', payload),
  updateNetworthItem: (id, payload) => client.patch(`/networth-items/${id}`, payload),
  deleteNetworthItem: (id, hard = false) => client.delete(`/networth-items/${id}?hard=${hard}`),
  reorderNetworthItems: (ids) => client.post('/networth-items/reorder', { ids }),
  patchNetworthValue: (payload) => client.patch('/networth-values', payload),
  carryForward: (year, month) =>
    client.post(`/networth-values/carry-forward?year=${year}&month=${month}`),

  // tools
  tools: (includeInactive = false) => client.get(`/tools?include_inactive=${includeInactive}`),
  createTool: (payload) => client.post('/tools', payload),
  updateTool: (id, payload) => client.patch(`/tools/${id}`, payload),
  deleteTool: (id, hard = false) => client.delete(`/tools/${id}?hard=${hard}`),
  reorderTools: (ids) => client.post('/tools/reorder', { ids }),

  // people & splits
  people: (includeInactive = false) => client.get(`/people?include_inactive=${includeInactive}`),
  createPerson: (payload) => client.post('/people', payload),
  updatePerson: (id, payload) => client.patch(`/people/${id}`, payload),
  deletePerson: (id, hard = false) => client.delete(`/people/${id}?hard=${hard}`),
  balances: () => client.get('/people/balances'),
  settleAll: (personId) => client.post(`/people/${personId}/settle-all`),
  settleShare: (shareId, settled = true) =>
    client.post(`/expenses/shares/${shareId}/settle?settled=${settled}`),

  // expenses
  expenses: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ''),
    ).toString()
    return client.get(`/expenses${query ? `?${query}` : ''}`)
  },
  createExpense: (payload) => client.post('/expenses', payload),
  updateExpense: (id, payload) => client.patch(`/expenses/${id}`, payload),
  deleteExpense: (id) => client.delete(`/expenses/${id}`),

  // receipt scanning
  receiptsStatus: () => client.get('/receipts/status'),
  scanReceipt: (file) => {
    const form = new FormData()
    form.append('image', file)
    return client.post('/receipts/scan', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
  },

  // aggregates & export
  aggregates: (year) => client.get(`/aggregates?year=${year}`),
  exportUrl: (year) => `/api/export?year=${year}`,
  exportWorkbook: (year) => client.get(`/export?year=${year}`, { responseType: 'blob' }),
}

export default api
