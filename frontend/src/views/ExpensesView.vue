<script setup>
/**
 * Snap a receipt, check what Claude read, decide whether it was yours alone or
 * split, and save. Only your share reaches the monthly grid — the rest becomes
 * something a friend owes you.
 */
import { computed, onMounted, ref } from 'vue'

import api, { errorMessage } from '@/api'
import { useFormat } from '@/composables/useFormat'
import { prepareReceiptImage } from '@/composables/useImagePrep'
import { useSession } from '@/stores/session'
import { useStructure } from '@/stores/structure'

const session = useSession()
const structure = useStructure()
const { formatMoney, parseAmount } = useFormat()

const expenses = ref([])
const people = ref([])
const categories = ref([])
const scanning = ref(false)
const loading = ref(true)
const scanEnabled = ref(false)
const fileInput = ref(null)
const cameraInput = ref(null)
const confirmDelete = ref(null)

// the draft under review
const draft = ref(null)
const preview = ref(null)
const form = ref(null)
const saving = ref(false)

const today = () => new Date().toISOString().slice(0, 10)

const blankForm = () => ({
  spent_on: today(),
  merchant: '',
  category_id: null,
  total_amount: '',
  note: '',
  is_split: false,
  splitMode: session.prefs?.default_split_mode || 'equal',
  participants: [],
  customShares: {},
})

async function load() {
  loading.value = true
  try {
    const [ex, pe, cats, status] = await Promise.all([
      api.expenses({ limit: 100 }),
      api.people(),
      api.categories(null, false),
      api.receiptsStatus().catch(() => ({ data: { enabled: false } })),
    ])
    expenses.value = ex.data
    people.value = pe.data
    const outflowIds = new Set(
      structure.sheets.filter((s) => s.kind === 'outflow').map((s) => s.id),
    )
    categories.value = cats.data.filter((c) => outflowIds.has(c.sheet_id))
    scanEnabled.value = Boolean(status.data.enabled)
  } catch (error) {
    session.notify(errorMessage(error, 'Could not load expenses'), 'error')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await structure.load()
  await load()
})

// ---------------------------------------------------------------- scanning
async function onFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  scanning.value = true
  try {
    const prepared = await prepareReceiptImage(file)
    preview.value = prepared.previewUrl
    const { data } = await api.scanReceipt(prepared.file)
    draft.value = data
    form.value = {
      ...blankForm(),
      spent_on: data.spent_on || today(),
      merchant: data.merchant || '',
      category_id: data.suggested_category_id,
      total_amount: data.total ?? '',
      is_split: data.likely_shared,
      participants: [],
      customShares: {},
    }
    if (data.warnings?.length) {
      session.notify(data.warnings[0], 'warning')
    }
  } catch (error) {
    session.notify(errorMessage(error, 'Could not read that receipt'), 'error')
    preview.value = null
  } finally {
    scanning.value = false
  }
}

function startManual() {
  draft.value = { manual: true, warnings: [] }
  preview.value = null
  form.value = blankForm()
}

function cancelDraft() {
  draft.value = null
  form.value = null
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = null
}

// ---------------------------------------------------------------- categories
/**
 * Sheet order puts long-lived commitments (mortgage, insurance) first, but
 * day-to-day spending is what actually gets logged and split. Rather than
 * hardcoding which categories those are — the whole point is that they are the
 * user's to define (CLAUDE.md §11) — rank them by how often they have really
 * been used, so travel, groceries and eating out rise on their own.
 */
const MOST_USED_LIMIT = 6

const categoryItems = computed(() => {
  const decorate = (c) => ({
    title: c.name,
    value: c.id,
    subtitle: c.group_name || undefined,
  })

  const uses = new Map()
  for (const expense of expenses.value) {
    if (expense.category_id == null) continue
    uses.set(expense.category_id, (uses.get(expense.category_id) || 0) + 1)
  }

  const top = categories.value
    .filter((c) => uses.has(c.id))
    .sort((a, b) => uses.get(b.id) - uses.get(a.id) || a.name.localeCompare(b.name))
    .slice(0, MOST_USED_LIMIT)

  // Nothing logged yet, so there is no usage to rank on — keep the plain list
  // rather than inventing an order.
  if (!top.length) return categories.value.map(decorate)

  const promoted = new Set(top.map((c) => c.id))
  return [
    { type: 'subheader', title: 'Most used' },
    ...top.map(decorate),
    { type: 'subheader', title: 'All categories' },
    ...categories.value.filter((c) => !promoted.has(c.id)).map(decorate),
  ]
})

// ---------------------------------------------------------------- split maths
const total = computed(() => Number(parseAmount(form.value?.total_amount) || 0))

/** Everyone sharing the bill: me plus whoever is selected. */
const splitCount = computed(() => (form.value?.participants.length || 0) + 1)

const equalShare = computed(() => {
  if (!form.value?.is_split || splitCount.value < 2) return 0
  return Math.round((total.value / splitCount.value) * 100) / 100
})

const shares = computed(() => {
  if (!form.value?.is_split) return []
  return form.value.participants.map((personId) => ({
    person_id: personId,
    amount:
      form.value.splitMode === 'equal'
        ? equalShare.value
        : Number(parseAmount(form.value.customShares[personId]) || 0),
  }))
})

const othersTotal = computed(() => shares.value.reduce((sum, s) => sum + s.amount, 0))

/** I keep the remainder, so rounding never goes missing. */
const myShare = computed(() => Math.round((total.value - othersTotal.value) * 100) / 100)

const splitError = computed(() => {
  if (!form.value?.is_split) return ''
  if (!form.value.participants.length) return 'Choose who you split this with'
  if (othersTotal.value > total.value) return 'The shares add up to more than the total'
  return ''
})

const canSave = computed(
  () => form.value && total.value > 0 && form.value.category_id && !splitError.value,
)

async function save() {
  saving.value = true
  try {
    const { data } = await api.createExpense({
      spent_on: form.value.spent_on,
      category_id: form.value.category_id,
      total_amount: total.value,
      merchant: form.value.merchant || null,
      note: form.value.note || null,
      is_split: form.value.is_split,
      shares: shares.value,
      source: draft.value?.manual ? 'manual' : 'receipt',
      extraction: draft.value?.manual ? null : draft.value,
    })
    session.notify(
      data.is_split
        ? `Saved — ${formatMoney(data.my_share)} is yours, ${formatMoney(
            Number(data.total_amount) - Number(data.my_share),
          )} owed to you`
        : `Saved ${formatMoney(data.my_share)}`,
    )
    cancelDraft()
    await load()
  } catch (error) {
    session.notify(errorMessage(error, 'Could not save that expense'), 'error')
  } finally {
    saving.value = false
  }
}

// ---------------------------------------------------------------- list
async function settle(share) {
  try {
    await api.settleShare(share.id, !share.settled_at)
    await load()
    session.notify(share.settled_at ? 'Marked unpaid' : 'Marked paid back')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not update that'), 'error')
  }
}

async function remove() {
  const expense = confirmDelete.value
  confirmDelete.value = null
  try {
    await api.deleteExpense(expense.id)
    await load()
    session.notify('Expense deleted — the grid was adjusted')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not delete that'), 'error')
  }
}

const owedToMe = computed(() =>
  expenses.value
    .flatMap((e) => e.shares)
    .filter((s) => !s.settled_at)
    .reduce((sum, s) => sum + Number(s.amount), 0),
)

const personName = (id) => people.value.find((p) => p.id === id)?.name || ''
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6" style="max-width: 1100px">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold">Expenses</div>
        <div class="text-caption text-medium-emphasis">
          Snap a receipt — only your share goes into the budget
        </div>
      </div>
      <v-spacer />
      <v-chip v-if="owedToMe > 0" color="warning" variant="tonal" :to="{ name: 'people' }">
        <v-icon start size="16">mdi-account-cash-outline</v-icon>
        {{ formatMoney(owedToMe) }} owed to you
      </v-chip>
    </div>

    <!-- capture -->
    <v-card v-if="!draft" class="pa-5 mb-4">
      <input ref="fileInput" type="file" accept="image/*" hidden @change="onFile" />
      <input ref="cameraInput" type="file" accept="image/*" capture="environment" hidden @change="onFile" />

      <div v-if="scanEnabled" class="d-flex flex-wrap align-center ga-3">
        <v-avatar color="primary" variant="tonal" rounded="lg" size="48">
          <v-icon color="primary">mdi-receipt-text-outline</v-icon>
        </v-avatar>
        <div class="flex-grow-1" style="min-width: 200px">
          <div class="font-weight-medium">Scan a receipt</div>
          <div class="text-caption text-medium-emphasis">
            Photos only. Nothing is saved until you check it.
          </div>
        </div>
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-camera"
          :loading="scanning"
          class="d-md-none"
          @click="cameraInput.click()"
        >
          Take photo
        </v-btn>
        <v-btn
          color="primary"
          size="large"
          prepend-icon="mdi-image-outline"
          :loading="scanning"
          @click="fileInput.click()"
        >
          Choose photo
        </v-btn>
        <v-btn variant="text" @click="startManual">Enter by hand</v-btn>
      </div>

      <div v-else class="d-flex flex-wrap align-center ga-3">
        <v-avatar color="surface-variant" rounded="lg" size="48">
          <v-icon>mdi-camera-off-outline</v-icon>
        </v-avatar>
        <div class="flex-grow-1" style="min-width: 220px">
          <div class="font-weight-medium">Receipt scanning is off</div>
          <div class="text-caption text-medium-emphasis">
            Set <code>ANTHROPIC_API_KEY</code> on the server to turn it on.
          </div>
        </div>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="startManual">Add by hand</v-btn>
      </div>

      <v-progress-linear v-if="scanning" indeterminate color="primary" class="mt-4" rounded />
      <div v-if="scanning" class="text-caption text-medium-emphasis mt-2">
        Reading the receipt…
      </div>
    </v-card>

    <!-- review -->
    <v-card v-if="draft && form" class="pa-5 mb-4">
      <div class="d-flex align-center mb-4">
        <div class="text-h6">{{ draft.manual ? 'New expense' : 'Check what was read' }}</div>
        <v-spacer />
        <v-chip
          v-if="!draft.manual && draft.confidence"
          size="small"
          variant="tonal"
          :color="draft.confidence >= 0.8 ? 'success' : 'warning'"
        >
          {{ Math.round(draft.confidence * 100) }}% confident
        </v-chip>
      </div>

      <v-alert
        v-for="warning in draft.warnings || []"
        :key="warning"
        type="warning"
        variant="tonal"
        density="comfortable"
        class="mb-3"
      >
        {{ warning }}
      </v-alert>

      <v-row dense>
        <v-col v-if="preview" cols="12" md="4">
          <v-img :src="preview" rounded="lg" max-height="320" cover class="border" />
          <div v-if="draft.line_items?.length" class="mt-3">
            <div class="section-title mb-1">Lines read</div>
            <div
              v-for="(item, index) in draft.line_items.slice(0, 6)"
              :key="index"
              class="d-flex justify-space-between text-caption"
            >
              <span class="text-truncate mr-2">{{ item.description }}</span>
              <span class="numeric">{{ formatMoney(item.amount) }}</span>
            </div>
          </div>
        </v-col>

        <v-col cols="12" :md="preview ? 8 : 12">
          <v-row dense>
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.merchant" label="Where" placeholder="Merchant" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.spent_on" label="When" type="date" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.total_amount"
                label="Total paid"
                inputmode="decimal"
                :hint="total > 0 ? formatMoney(total) : ''"
                persistent-hint
              />
            </v-col>
          </v-row>

          <!-- Full width and searchable: there are far too many categories to
               scroll, and the ones that get split are rarely near the top of
               the sheet order. -->
          <v-autocomplete
            v-model="form.category_id"
            :items="categoryItems"
            label="Category"
            placeholder="Type to search — travel, food, groceries…"
            auto-select-first
            :menu-props="{ maxHeight: 420 }"
            :error-messages="form.category_id ? '' : 'Pick a category'"
          />

          <v-divider class="my-4" />

          <!-- individual or split -->
          <div class="section-title mb-2">Was this just you?</div>
          <v-btn-toggle
            v-model="form.is_split"
            mandatory
            divided
            variant="outlined"
            class="mb-3"
          >
            <v-btn :value="false" prepend-icon="mdi-account">Just me</v-btn>
            <v-btn :value="true" prepend-icon="mdi-account-group">Split it</v-btn>
          </v-btn-toggle>

          <div v-if="!draft.manual && draft.likely_shared" class="text-caption text-medium-emphasis mb-3">
            <v-icon size="14" class="mr-1">mdi-information-outline</v-icon>
            The receipt looks like it covered
            {{ draft.likely_people_count || 'several' }} people — check before saving.
          </div>

          <template v-if="form.is_split">
            <v-select
              v-model="form.participants"
              :items="people.map((p) => ({ title: `${p.name} (${p.relation})`, value: p.id }))"
              label="Split with"
              multiple
              chips
              closable-chips
              class="mb-3"
            />
            <div v-if="!people.length" class="text-caption text-medium-emphasis mb-3">
              No people yet — add friends, family or colleagues on the
              <router-link :to="{ name: 'people' }">People</router-link> page.
            </div>

            <v-btn-toggle v-model="form.splitMode" mandatory divided variant="outlined" density="compact" class="mb-3">
              <v-btn value="equal" size="small">Split equally</v-btn>
              <v-btn value="custom" size="small">Custom amounts</v-btn>
            </v-btn-toggle>

            <div v-if="form.splitMode === 'custom'">
              <v-text-field
                v-for="personId in form.participants"
                :key="personId"
                v-model="form.customShares[personId]"
                :label="`${personName(personId)} owes`"
                inputmode="decimal"
                density="compact"
                class="mb-2"
              />
            </div>

            <v-alert
              :type="splitError ? 'error' : 'info'"
              variant="tonal"
              density="comfortable"
              class="mt-2"
            >
              <template v-if="splitError">{{ splitError }}</template>
              <template v-else>
                Split {{ splitCount }} ways —
                <strong>{{ formatMoney(myShare) }} is yours</strong> and goes into your budget;
                {{ formatMoney(othersTotal) }} is owed to you.
              </template>
            </v-alert>
          </template>

          <v-textarea v-model="form.note" label="Note (optional)" rows="2" class="mt-3" />
        </v-col>
      </v-row>

      <div class="d-flex justify-end ga-2 mt-4 flex-wrap">
        <v-btn variant="text" @click="cancelDraft">Cancel</v-btn>
        <v-btn color="primary" size="large" :loading="saving" :disabled="!canSave" @click="save">
          Save {{ total > 0 ? formatMoney(form.is_split ? myShare : total) : '' }}
        </v-btn>
      </div>
    </v-card>

    <!-- history -->
    <v-card>
      <div class="px-4 py-3 d-flex align-center">
        <span class="font-weight-medium">Recent</span>
        <v-spacer />
        <span class="text-caption text-medium-emphasis">{{ expenses.length }} expenses</span>
      </div>
      <v-divider />
      <v-progress-linear v-if="loading" indeterminate color="primary" />

      <div v-if="!loading && !expenses.length" class="pa-10 text-center text-medium-emphasis">
        Nothing logged yet.
      </div>

      <v-list v-else class="bg-transparent">
        <v-list-item v-for="expense in expenses" :key="expense.id" class="py-2">
          <template #prepend>
            <v-avatar :color="expense.is_split ? 'warning' : 'primary'" variant="tonal" rounded="lg" size="38">
              <v-icon size="18">{{ expense.is_split ? 'mdi-account-group' : 'mdi-receipt-text-outline' }}</v-icon>
            </v-avatar>
          </template>

          <v-list-item-title class="font-weight-medium">
            {{ expense.merchant || expense.category_name }}
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ expense.spent_on }} · {{ expense.category_name }}
            <template v-if="expense.is_split">
              · split with
              {{ expense.shares.map((s) => s.person_name).join(', ') }}
            </template>
          </v-list-item-subtitle>

          <div v-if="expense.is_split" class="d-flex flex-wrap ga-1 mt-1">
            <v-chip
              v-for="share in expense.shares"
              :key="share.id"
              size="x-small"
              :color="share.settled_at ? 'success' : 'warning'"
              variant="tonal"
              @click="settle(share)"
            >
              <v-icon start size="12">
                {{ share.settled_at ? 'mdi-check' : 'mdi-clock-outline' }}
              </v-icon>
              {{ share.person_name }} {{ formatMoney(share.amount) }}
            </v-chip>
          </div>

          <template #append>
            <div class="text-right">
              <div class="numeric font-weight-medium">{{ formatMoney(expense.my_share) }}</div>
              <div v-if="expense.is_split" class="text-caption text-medium-emphasis numeric">
                of {{ formatMoney(expense.total_amount) }}
              </div>
            </div>
            <v-btn
              icon="mdi-delete-outline"
              size="x-small"
              variant="text"
              class="ml-2"
              @click="confirmDelete = expense"
            />
          </template>
        </v-list-item>
      </v-list>
    </v-card>

    <v-dialog :model-value="Boolean(confirmDelete)" max-width="420" @update:model-value="confirmDelete = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-2">Delete this expense?</div>
        <div class="text-body-2 text-medium-emphasis">
          {{ formatMoney(confirmDelete?.my_share) }} will be taken back off
          {{ confirmDelete?.category_name }}, and any amounts owed to you for it are dropped.
        </div>
        <div class="d-flex justify-end ga-2 mt-5">
          <v-btn variant="text" @click="confirmDelete = null">Cancel</v-btn>
          <v-btn color="error" @click="remove">Delete</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </v-container>
</template>
