<script setup>
/** Friends, family and colleagues — and what each of them owes you. */
import { computed, onMounted, ref } from 'vue'

import api, { errorMessage } from '@/api'
import { useFormat } from '@/composables/useFormat'
import { useSession } from '@/stores/session'

const session = useSession()
const { formatMoney } = useFormat()

const balances = ref([])
const expenses = ref([])
const loading = ref(true)
const editing = ref(null)
const form = ref({ name: '', relation: 'friend', contact: '', note: '' })
const confirm = ref(null)
const expanded = ref(null)

const RELATIONS = [
  { title: 'Friend', value: 'friend', icon: 'mdi-account-heart-outline' },
  { title: 'Family', value: 'family', icon: 'mdi-home-heart' },
  { title: 'Colleague', value: 'colleague', icon: 'mdi-briefcase-outline' },
  { title: 'Other', value: 'other', icon: 'mdi-account-outline' },
]

const iconFor = (relation) => RELATIONS.find((r) => r.value === relation)?.icon || 'mdi-account'

async function load() {
  loading.value = true
  try {
    const [bal, ex] = await Promise.all([api.balances(), api.expenses({ limit: 300 })])
    balances.value = bal.data
    expenses.value = ex.data
  } catch (error) {
    session.notify(errorMessage(error, 'Could not load people'), 'error')
  } finally {
    loading.value = false
  }
}

onMounted(load)

const totalOwed = computed(() =>
  balances.value.reduce((sum, b) => sum + Number(b.owed), 0),
)

/** Grouped for the summary strip — who owes you, by relationship. */
const byRelation = computed(() => {
  const groups = {}
  for (const balance of balances.value) {
    const key = balance.person.relation
    groups[key] = (groups[key] || 0) + Number(balance.owed)
  }
  return RELATIONS.map((r) => ({ ...r, amount: groups[r.value] || 0 })).filter((r) => r.amount > 0)
})

const openItemsFor = (personId) =>
  expenses.value
    .flatMap((e) => e.shares.map((s) => ({ ...s, expense: e })))
    .filter((s) => s.person_id === personId && !s.settled_at)

function openNew() {
  editing.value = { id: null }
  form.value = { name: '', relation: 'friend', contact: '', note: '' }
}

function openEdit(person) {
  editing.value = person
  form.value = {
    name: person.name,
    relation: person.relation,
    contact: person.contact || '',
    note: person.note || '',
  }
}

async function save() {
  const payload = {
    name: form.value.name.trim(),
    relation: form.value.relation,
    contact: form.value.contact || null,
    note: form.value.note || null,
  }
  if (!payload.name) return
  try {
    if (editing.value.id) await api.updatePerson(editing.value.id, payload)
    else await api.createPerson(payload)
    editing.value = null
    await load()
    session.notify('Saved')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not save'), 'error')
  }
}

async function settleAll(person) {
  try {
    await api.settleAll(person.id)
    await load()
    session.notify(`${person.name} settled up`)
  } catch (error) {
    session.notify(errorMessage(error, 'Could not settle'), 'error')
  }
}

async function settleOne(share) {
  try {
    await api.settleShare(share.id, true)
    await load()
  } catch (error) {
    session.notify(errorMessage(error, 'Could not settle'), 'error')
  }
}

function askRemove(person) {
  confirm.value = person
}

async function remove(hard) {
  const person = confirm.value
  confirm.value = null
  try {
    await api.deletePerson(person.id, hard)
    await load()
    session.notify(hard ? 'Deleted' : 'Hidden')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not remove them'), 'error')
  }
}
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6" style="max-width: 900px">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold">People</div>
        <div class="text-caption text-medium-emphasis">
          What friends, family and colleagues owe you
        </div>
      </div>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-account-plus-outline" @click="openNew">
        Add person
      </v-btn>
    </div>

    <v-card class="pa-5 mb-4">
      <div class="section-title mb-1">Total owed to you</div>
      <div class="stat-value numeric" :class="totalOwed > 0 ? 'text-warning' : ''">
        {{ formatMoney(totalOwed) }}
      </div>
      <div class="d-flex flex-wrap ga-2 mt-3">
        <v-chip v-for="group in byRelation" :key="group.value" size="small" variant="tonal">
          <v-icon start size="14">{{ group.icon }}</v-icon>
          {{ group.title }} · {{ formatMoney(group.amount) }}
        </v-chip>
      </div>
      <div class="text-caption text-medium-emphasis mt-3">
        This money isn't income — it's your own spending coming back, so settling up
        doesn't change any totals.
      </div>
    </v-card>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-3" />

    <v-card v-if="!loading && !balances.length" class="pa-10 text-center">
      <v-icon size="42" class="mb-3 text-medium-emphasis">mdi-account-group-outline</v-icon>
      <div class="text-body-1 mb-1">Nobody added yet</div>
      <div class="text-body-2 text-medium-emphasis mb-4">
        Add the people you share bills with, then split an expense with them.
      </div>
      <v-btn color="primary" @click="openNew">Add your first</v-btn>
    </v-card>

    <v-card v-for="balance in balances" :key="balance.person.id" class="mb-3">
      <div class="pa-4 d-flex align-center ga-3 flex-wrap">
        <v-avatar :color="balance.person.color || 'primary'" variant="tonal" rounded="lg" size="42">
          <v-icon>{{ iconFor(balance.person.relation) }}</v-icon>
        </v-avatar>
        <div class="flex-grow-1" style="min-width: 140px">
          <div class="font-weight-medium">
            {{ balance.person.name }}
            <v-chip v-if="!balance.person.is_active" size="x-small" variant="tonal" class="ml-1">hidden</v-chip>
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ balance.person.relation }}
            <template v-if="balance.settled > 0"> · {{ formatMoney(balance.settled) }} settled</template>
          </div>
        </div>

        <div class="text-right mr-2">
          <div class="numeric text-h6" :class="Number(balance.owed) > 0 ? 'text-warning' : 'text-medium-emphasis'">
            {{ formatMoney(balance.owed) }}
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ balance.open_items }} open
          </div>
        </div>

        <v-btn
          v-if="Number(balance.owed) > 0"
          size="small"
          color="success"
          variant="tonal"
          prepend-icon="mdi-check"
          @click="settleAll(balance.person)"
        >
          Settle up
        </v-btn>

        <v-menu location="bottom end">
          <template #activator="{ props }">
            <v-btn v-bind="props" icon="mdi-dots-vertical" size="small" variant="text" />
          </template>
          <v-list density="compact" min-width="170">
            <v-list-item prepend-icon="mdi-pencil" title="Edit" @click="openEdit(balance.person)" />
            <v-list-item
              v-if="balance.open_items"
              prepend-icon="mdi-format-list-bulleted"
              :title="expanded === balance.person.id ? 'Hide items' : 'Show items'"
              @click="expanded = expanded === balance.person.id ? null : balance.person.id"
            />
            <v-divider />
            <v-list-item prepend-icon="mdi-delete-outline" title="Remove" base-color="error" @click="askRemove(balance.person)" />
          </v-list>
        </v-menu>
      </div>

      <v-expand-transition>
        <div v-if="expanded === balance.person.id">
          <v-divider />
          <v-list density="compact" class="bg-transparent">
            <v-list-item
              v-for="share in openItemsFor(balance.person.id)"
              :key="share.id"
              :title="share.expense.merchant || share.expense.category_name"
              :subtitle="share.expense.spent_on"
            >
              <template #append>
                <span class="numeric mr-3">{{ formatMoney(share.amount) }}</span>
                <v-btn size="x-small" variant="tonal" color="success" @click="settleOne(share)">
                  Paid
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </div>
      </v-expand-transition>
    </v-card>

    <v-dialog :model-value="Boolean(editing)" max-width="440" @update:model-value="editing = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-4">{{ editing?.id ? 'Edit person' : 'Add person' }}</div>
        <v-text-field v-model="form.name" label="Name" class="mb-3" autofocus />
        <v-select v-model="form.relation" :items="RELATIONS" label="Relationship" class="mb-3" />
        <v-text-field v-model="form.contact" label="Contact (optional)" placeholder="Phone or email" class="mb-3" />
        <v-textarea v-model="form.note" label="Note (optional)" rows="2" />
        <div class="d-flex justify-end ga-2 mt-4">
          <v-btn variant="text" @click="editing = null">Cancel</v-btn>
          <v-btn color="primary" :disabled="!form.name.trim()" @click="save">Save</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <v-dialog :model-value="Boolean(confirm)" max-width="440" @update:model-value="confirm = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-2">Remove {{ confirm?.name }}?</div>
        <div class="text-body-2 text-medium-emphasis">
          Hiding keeps their past splits intact. Deleting is only possible once
          they don't owe you anything.
        </div>
        <div class="d-flex justify-end ga-2 mt-5 flex-wrap">
          <v-btn variant="text" @click="confirm = null">Cancel</v-btn>
          <v-btn color="error" variant="tonal" @click="remove(true)">Delete</v-btn>
          <v-btn color="primary" @click="remove(false)">Hide</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </v-container>
</template>
