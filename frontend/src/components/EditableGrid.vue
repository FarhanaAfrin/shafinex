<script setup>
/**
 * The editable category x month grid used by every sheet and by net worth.
 *
 * Behaviour that matters:
 *  - optimistic writes, debounced per cell, with a per-cell saved/error state
 *  - spreadsheet keyboard nav (arrows, enter, tab) so it can be filled without a mouse
 *  - accepts "1.2k", "1,200", "(450)" and "1200+300" as input
 *  - the parent owns persistence; this component only reports what changed
 */
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useFormat } from '@/composables/useFormat'
import { useSession } from '@/stores/session'

const props = defineProps({
  months: { type: Array, required: true },
  rows: { type: Array, required: true },
  save: { type: Function, required: true }, // async ({ row, column, amount }) => void
  showPlan: { type: Boolean, default: false },
  planLabel: { type: String, default: 'Planned' },
  labelHeader: { type: String, default: 'Category' },
  columnTotals: { type: Array, default: () => [] },
  totalsLabel: { type: String, default: 'Total' },
  showRowTotals: { type: Boolean, default: true },
  showVariance: { type: Boolean, default: false },
  varianceLabel: { type: String, default: 'Left' },
  allowAdd: { type: Boolean, default: true },
  addPlaceholder: { type: String, default: 'Add a category…' },
  emptyText: { type: String, default: 'No rows yet. Add your first one below.' },
  highlightMonth: { type: Number, default: null },
  // Extra footer rows, e.g. the workbook's Balance row:
  // [{ label, plan, values: [...], signed: true }]
  footerRows: { type: Array, default: () => [] },
})

const emit = defineEmits(['add', 'edit', 'remove', 'fill', 'clear', 'move', 'totals'])

const session = useSession()
const { formatCell, formatMoney, parseAmount } = useFormat()

const PLAN_COL = -1
const local = reactive({})   // what the cell shows (optimistic)
const saved = reactive({})   // what the server last confirmed
const status = reactive({})  // key -> 'saving' | 'saved' | 'error'
const pending = {}           // key -> value waiting to be written
const timers = {}
const inputs = reactive({})
const focused = ref(null)
const editText = ref('')
const newRowName = ref('')

const compact = computed(() => session.prefs?.density === 'compact')
const columnCount = computed(
  () => 1 + (props.showPlan ? 1 : 0) + props.months.length + (props.showRowTotals ? 2 : 0) + (props.showVariance ? 1 : 0),
)

const keyOf = (rowId, col) => `${rowId}:${col}`

/** Clear local state when the parent reloads the grid (year change, etc). */
watch(
  () => props.rows,
  () => {
    for (const key of Object.keys(local)) delete local[key]
    for (const key of Object.keys(saved)) delete saved[key]
    for (const key of Object.keys(pending)) delete pending[key]
  },
)

function baseValue(row, col) {
  return col === PLAN_COL ? row.plan : row.cells[col]
}

function cellValue(row, col) {
  const key = keyOf(row.id, col)
  return key in local ? local[key] : toNumber(baseValue(row, col))
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function display(row, col) {
  const key = keyOf(row.id, col)
  if (focused.value === key) return editText.value
  const value = cellValue(row, col)
  return value === null ? '' : formatCell(value)
}

function onFocus(row, col, event) {
  const key = keyOf(row.id, col)
  focused.value = key
  const value = cellValue(row, col)
  editText.value = value === null ? '' : String(value)
  nextTick(() => event.target.select())
}

function onInput(event) {
  editText.value = event.target.value
}

function onBlur(row, col) {
  const key = keyOf(row.id, col)
  if (focused.value === key) focused.value = null
  commit(row, col, editText.value, 0)
}

/** Typing schedules a save; leaving the cell flushes it immediately. */
function onKeyup(row, col, event) {
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Tab', 'Enter', 'Escape'].includes(event.key)) return
  commit(row, col, editText.value, session.autosaveDelay)
}

/** The value the server is known to hold — what a write is compared against. */
function serverValue(row, col) {
  const key = keyOf(row.id, col)
  return key in saved ? saved[key] : toNumber(baseValue(row, col))
}

function commit(row, col, text, delay) {
  const key = keyOf(row.id, col)
  clearTimeout(timers[key])

  const parsed = parseAmount(text)
  if (Number.isNaN(parsed)) {
    delete pending[key]
    status[key] = 'error'
    return
  }

  local[key] = parsed

  if (parsed === serverValue(row, col)) {
    delete pending[key]
    delete status[key]
    return
  }

  pending[key] = parsed
  status[key] = 'saving'

  if (delay > 0) timers[key] = setTimeout(() => flush(key, row, col), delay)
  else flush(key, row, col)
}

async function flush(key, row, col) {
  if (!(key in pending)) return
  const amount = pending[key]
  delete pending[key]

  try {
    await props.save({
      row,
      column: col === PLAN_COL ? { plan: true } : props.months[col],
      amount,
    })
    saved[key] = amount
    status[key] = 'saved'
    setTimeout(() => {
      if (status[key] === 'saved') delete status[key]
    }, 1400)
  } catch (error) {
    status[key] = 'error'
    delete local[key]
    session.notify('Could not save that cell — check your connection', 'error')
  }
}

function onKeydown(rowIndex, col, event) {
  const move = (rowDelta, colDelta) => {
    event.preventDefault()
    focusCell(rowIndex + rowDelta, col + colDelta)
  }
  switch (event.key) {
    case 'ArrowDown':
    case 'Enter':
      move(event.shiftKey ? -1 : 1, 0)
      break
    case 'ArrowUp':
      move(-1, 0)
      break
    case 'ArrowLeft':
      if (event.target.selectionStart === 0) move(0, -1)
      break
    case 'ArrowRight':
      if (event.target.selectionStart === event.target.value.length) move(0, 1)
      break
    case 'Escape':
      editText.value = ''
      event.target.blur()
      break
    default:
      break
  }
}

function focusCell(rowIndex, col) {
  const row = props.rows[rowIndex]
  if (!row) return
  const min = props.showPlan ? PLAN_COL : 0
  const bounded = Math.min(Math.max(col, min), props.months.length - 1)
  const input = inputs[keyOf(row.id, bounded)]
  if (input) {
    input.focus()
  }
}

function setRef(rowId, col, element) {
  const key = keyOf(rowId, col)
  if (element) inputs[key] = element
  else delete inputs[key]
}

function cellClass(row, col) {
  const key = keyOf(row.id, col)
  return [status[key], col === PLAN_COL ? 'is-plan' : '']
}

function rowTotal(row) {
  return props.months.reduce((sum, _, index) => sum + (cellValue(row, index) ?? 0), 0)
}

function rowVariance(row) {
  const plan = cellValue(row, PLAN_COL)
  if (plan === null) return null
  return row.varianceSign === -1 ? rowTotal(row) - plan : plan - rowTotal(row)
}

function columnTotal(index) {
  return props.rows.reduce((sum, row) => sum + (cellValue(row, index) ?? 0), 0)
}

/** Totals include not-yet-saved edits, so the header cards stay in step. */
const totals = computed(() => ({
  plan: props.rows.reduce((sum, row) => sum + (cellValue(row, PLAN_COL) ?? 0), 0),
  actual: props.months.reduce((sum, _, index) => sum + columnTotal(index), 0),
}))

watch(totals, (value) => emit('totals', value), { immediate: true })

/** Signed footer rows (Balance) read green when positive, red when negative. */
function toneOf(extra, value) {
  if (!extra.signed || value === null || value === undefined) return ''
  return Number(value) < 0 ? 'over-budget' : 'under-budget'
}

function submitNewRow() {
  const name = newRowName.value.trim()
  if (!name) return
  emit('add', name)
  newRowName.value = ''
}
</script>

<template>
  <div class="grid-wrap">
    <table class="money-grid" :class="{ 'density-compact': compact }">
      <thead>
        <tr>
          <th class="col-label">{{ labelHeader }}</th>
          <th v-if="showPlan">{{ planLabel }}</th>
          <th
            v-for="month in months"
            :key="`h-${month.index}`"
            :class="{ 'text-primary': month.month === highlightMonth }"
          >
            {{ month.label }}
          </th>
          <template v-if="showRowTotals">
            <th>Total</th>
            <th>Avg</th>
          </template>
          <th v-if="showVariance">{{ varianceLabel }}</th>
        </tr>
      </thead>

      <tbody>
        <tr v-if="!rows.length">
          <td :colspan="columnCount" class="text-center text-medium-emphasis pa-6">
            {{ emptyText }}
          </td>
        </tr>

        <tr v-for="(row, rowIndex) in rows" :key="row.id">
          <td class="col-label">
            <div class="d-flex align-center ga-2">
              <span
                class="row-color-dot"
                :style="{ background: row.color || 'rgba(128,128,128,.35)' }"
              />
              <div class="flex-grow-1 min-width-0">
                <div class="text-truncate" :title="row.name">{{ row.name }}</div>
                <div v-if="row.group_name" class="text-caption text-medium-emphasis text-truncate">
                  {{ row.group_name }}
                </div>
              </div>

              <v-menu location="bottom end">
                <template #activator="{ props: menu }">
                  <v-btn v-bind="menu" icon="mdi-dots-vertical" size="x-small" variant="text" />
                </template>
                <v-list density="compact" min-width="200">
                  <v-list-item prepend-icon="mdi-pencil" title="Edit" @click="emit('edit', row)" />
                  <v-list-item
                    prepend-icon="mdi-arrow-expand-horizontal"
                    title="Fill across months"
                    @click="emit('fill', row)"
                  />
                  <v-list-item
                    prepend-icon="mdi-eraser"
                    title="Clear this row"
                    @click="emit('clear', row)"
                  />
                  <v-divider />
                  <v-list-item
                    prepend-icon="mdi-arrow-up"
                    title="Move up"
                    :disabled="rowIndex === 0"
                    @click="emit('move', { row, direction: -1 })"
                  />
                  <v-list-item
                    prepend-icon="mdi-arrow-down"
                    title="Move down"
                    :disabled="rowIndex === rows.length - 1"
                    @click="emit('move', { row, direction: 1 })"
                  />
                  <v-divider />
                  <v-list-item
                    prepend-icon="mdi-delete-outline"
                    title="Delete"
                    base-color="error"
                    @click="emit('remove', row)"
                  />
                </v-list>
              </v-menu>
            </div>
          </td>

          <td v-if="showPlan" class="cell">
            <input
              :ref="(el) => setRef(row.id, PLAN_COL, el)"
              class="cell-input"
              size="1"
              :class="cellClass(row, PLAN_COL)"
              inputmode="decimal"
              :value="display(row, PLAN_COL)"
              placeholder="—"
              @focus="onFocus(row, PLAN_COL, $event)"
              @input="onInput"
              @keyup="onKeyup(row, PLAN_COL, $event)"
              @keydown="onKeydown(rowIndex, PLAN_COL, $event)"
              @blur="onBlur(row, PLAN_COL)"
            />
          </td>

          <td
            v-for="(month, colIndex) in months"
            :key="`c-${row.id}-${month.index}`"
            class="cell"
            :class="{ 'current-month': month.month === highlightMonth }"
          >
            <input
              :ref="(el) => setRef(row.id, colIndex, el)"
              class="cell-input"
              size="1"
              :class="cellClass(row, colIndex)"
              inputmode="decimal"
              :value="display(row, colIndex)"
              placeholder="—"
              @focus="onFocus(row, colIndex, $event)"
              @input="onInput"
              @keyup="onKeyup(row, colIndex, $event)"
              @keydown="onKeydown(rowIndex, colIndex, $event)"
              @blur="onBlur(row, colIndex)"
            />
          </td>

          <template v-if="showRowTotals">
            <td class="cell numeric px-3 font-weight-medium">{{ formatMoney(rowTotal(row)) }}</td>
            <td class="cell numeric px-3 text-medium-emphasis">
              {{ formatMoney(rowTotal(row) / (months.length || 1)) }}
            </td>
          </template>

          <td v-if="showVariance" class="cell numeric px-3">
            <span
              v-if="rowVariance(row) !== null"
              :class="rowVariance(row) < 0 ? 'over-budget' : 'under-budget'"
            >
              {{ formatMoney(rowVariance(row)) }}
            </span>
            <span v-else class="text-disabled">—</span>
          </td>
        </tr>

        <tr v-if="allowAdd">
          <td class="col-label">
            <v-text-field
              v-model="newRowName"
              :placeholder="addPlaceholder"
              density="compact"
              variant="plain"
              hide-details
              prepend-inner-icon="mdi-plus"
              @keyup.enter="submitNewRow"
              @blur="submitNewRow"
            />
          </td>
          <td :colspan="columnCount - 1" class="text-medium-emphasis text-caption px-3">
            Type a name and press Enter
          </td>
        </tr>
      </tbody>

      <tfoot v-if="rows.length">
        <tr>
          <td class="col-label">{{ totalsLabel }}</td>
          <td v-if="showPlan" class="numeric">
            {{ formatMoney(rows.reduce((sum, row) => sum + (cellValue(row, PLAN_COL) ?? 0), 0)) }}
          </td>
          <td v-for="(month, index) in months" :key="`t-${month.index}`" class="numeric">
            {{ formatMoney(columnTotal(index)) }}
          </td>
          <template v-if="showRowTotals">
            <td class="numeric">
              {{ formatMoney(months.reduce((sum, _, index) => sum + columnTotal(index), 0)) }}
            </td>
            <td />
          </template>
          <td v-if="showVariance" />
        </tr>

        <tr v-for="extra in footerRows" :key="extra.label">
          <td class="col-label">{{ extra.label }}</td>
          <td v-if="showPlan" class="numeric" :class="toneOf(extra, extra.plan)">
            {{ extra.plan === null || extra.plan === undefined ? '' : formatMoney(extra.plan) }}
          </td>
          <td
            v-for="(value, index) in extra.values"
            :key="`f-${extra.label}-${index}`"
            class="numeric"
            :class="toneOf(extra, value)"
          >
            {{ formatMoney(value) }}
          </td>
          <template v-if="showRowTotals">
            <td class="numeric" :class="toneOf(extra, extra.values.reduce((a, b) => a + Number(b), 0))">
              {{ formatMoney(extra.values.reduce((a, b) => a + Number(b), 0)) }}
            </td>
            <td />
          </template>
          <td v-if="showVariance" />
        </tr>
      </tfoot>
    </table>
  </div>
</template>

<style scoped>
.min-width-0 {
  min-width: 0;
}
</style>
