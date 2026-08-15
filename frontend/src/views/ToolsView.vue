<script setup>
/** The workbook's Tools tab: the cards, apps and services you use, with the
 *  referral bonus and link or code attached to each. Fully editable. */
import { computed, onMounted, ref } from 'vue'

import api, { errorMessage } from '@/api'
import { useSession } from '@/stores/session'

const session = useSession()

const tools = ref([])
const loading = ref(true)
const showInactive = ref(false)
const search = ref('')
const editing = ref(null)
const form = ref({ name: '', purpose: '', bonus: '', link: '', note: '' })
const confirm = ref(null)
const copied = ref(null)

const blank = () => ({ name: '', purpose: '', bonus: '', link: '', note: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await api.tools(showInactive.value)
    tools.value = data
  } catch (error) {
    session.notify(errorMessage(error, 'Could not load your tools'), 'error')
  } finally {
    loading.value = false
  }
}

onMounted(load)

const filtered = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return tools.value
  return tools.value.filter((tool) =>
    [tool.name, tool.purpose, tool.bonus].some((field) => (field || '').toLowerCase().includes(term)),
  )
})

const purposes = computed(() => [...new Set(tools.value.map((t) => t.purpose).filter(Boolean))])

/** A link column that holds a plain referral code rather than a URL. */
const isUrl = (value) => /^https?:\/\//i.test((value || '').trim())

function openNew() {
  editing.value = { id: null }
  form.value = blank()
}

function openEdit(tool) {
  editing.value = tool
  form.value = {
    name: tool.name,
    purpose: tool.purpose || '',
    bonus: tool.bonus || '',
    link: tool.link || '',
    note: tool.note || '',
  }
}

async function save() {
  const payload = {
    name: form.value.name.trim(),
    purpose: form.value.purpose || null,
    bonus: form.value.bonus || null,
    link: form.value.link ? form.value.link.trim() : null,
    note: form.value.note || null,
  }
  if (!payload.name) return
  try {
    if (editing.value.id) await api.updateTool(editing.value.id, payload)
    else await api.createTool(payload)
    editing.value = null
    await load()
    session.notify('Saved')
  } catch (error) {
    session.notify(errorMessage(error, 'Could not save that tool'), 'error')
  }
}

function askRemove(tool) {
  confirm.value = {
    title: `Remove “${tool.name}”?`,
    text: 'Hide it to keep it on the list but out of the way, or delete it entirely.',
    action: async () => {
      await api.deleteTool(tool.id, false)
      await load()
    },
    hardAction: async () => {
      await api.deleteTool(tool.id, true)
      await load()
    },
  }
}

async function runConfirm(hard) {
  const item = confirm.value
  confirm.value = null
  try {
    await (hard ? item.hardAction() : item.action())
  } catch (error) {
    session.notify(errorMessage(error, 'That did not work'), 'error')
  }
}

async function copy(tool) {
  try {
    await navigator.clipboard.writeText(tool.link)
    copied.value = tool.id
    setTimeout(() => {
      if (copied.value === tool.id) copied.value = null
    }, 1600)
  } catch {
    session.notify('Could not copy — select it by hand', 'warning')
  }
}

async function move(tool, direction) {
  const ids = tools.value.map((t) => t.id)
  const index = ids.indexOf(tool.id)
  const target = index + direction
  if (target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  await api.reorderTools(ids)
  await load()
}
</script>

<template>
  <v-container fluid class="pa-4 pa-md-6">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold">Tools</div>
        <div class="text-caption text-medium-emphasis">
          Cards, apps and services you use — with their referral bonuses and codes
        </div>
      </div>
      <v-spacer />
      <v-text-field
        v-model="search"
        placeholder="Search tools"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        hide-details
        clearable
        style="max-width: 230px"
      />
      <v-switch
        v-model="showInactive"
        label="Show hidden"
        density="compact"
        color="primary"
        hide-details
        class="flex-grow-0"
        @update:model-value="load"
      />
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">Add tool</v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-3" />

    <v-card v-if="!loading && !tools.length" class="pa-10 text-center">
      <v-icon size="42" class="mb-3 text-medium-emphasis">mdi-tools</v-icon>
      <div class="text-body-1 mb-1">No tools yet</div>
      <div class="text-body-2 text-medium-emphasis mb-4">
        Track the cards and apps you use, what each is for, and the referral bonus you can share.
      </div>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">Add your first</v-btn>
    </v-card>

    <v-row v-else dense>
      <v-col v-for="(tool, index) in filtered" :key="tool.id" cols="12" md="6" lg="4">
        <v-card class="pa-4 h-100 d-flex flex-column" :class="{ 'opacity-60': !tool.is_active }">
          <div class="d-flex align-start ga-3 mb-2">
            <v-avatar color="primary" variant="tonal" rounded="lg" size="38">
              <v-icon color="primary" size="20">mdi-tag-outline</v-icon>
            </v-avatar>
            <div class="flex-grow-1 min-w-0">
              <div class="font-weight-medium text-truncate" :title="tool.name">{{ tool.name }}</div>
              <div v-if="tool.purpose" class="text-caption text-medium-emphasis">
                {{ tool.purpose }}
              </div>
            </div>
            <v-menu location="bottom end">
              <template #activator="{ props: menu }">
                <v-btn v-bind="menu" icon="mdi-dots-vertical" size="x-small" variant="text" />
              </template>
              <v-list density="compact" min-width="180">
                <v-list-item prepend-icon="mdi-pencil" title="Edit" @click="openEdit(tool)" />
                <v-list-item
                  prepend-icon="mdi-arrow-up"
                  title="Move up"
                  :disabled="index === 0"
                  @click="move(tool, -1)"
                />
                <v-list-item
                  prepend-icon="mdi-arrow-down"
                  title="Move down"
                  :disabled="index === filtered.length - 1"
                  @click="move(tool, 1)"
                />
                <v-divider />
                <v-list-item
                  prepend-icon="mdi-delete-outline"
                  title="Remove"
                  base-color="error"
                  @click="askRemove(tool)"
                />
              </v-list>
            </v-menu>
          </div>

          <v-chip v-if="tool.bonus" size="small" color="success" variant="tonal" class="mb-3 align-self-start">
            <v-icon start size="16">mdi-gift-outline</v-icon>
            {{ tool.bonus }}
          </v-chip>

          <div v-if="tool.note" class="text-caption text-medium-emphasis mb-3">{{ tool.note }}</div>

          <v-spacer />

          <div v-if="tool.link" class="d-flex align-center ga-2 mt-2">
            <v-btn
              v-if="isUrl(tool.link)"
              :href="tool.link"
              target="_blank"
              rel="noopener noreferrer"
              variant="tonal"
              size="small"
              append-icon="mdi-open-in-new"
            >
              Open link
            </v-btn>
            <v-chip v-else size="small" variant="outlined" class="numeric">{{ tool.link }}</v-chip>
            <v-spacer />
            <v-btn
              :icon="copied === tool.id ? 'mdi-check' : 'mdi-content-copy'"
              size="x-small"
              variant="text"
              :color="copied === tool.id ? 'success' : undefined"
              :title="isUrl(tool.link) ? 'Copy link' : 'Copy code'"
              @click="copy(tool)"
            />
          </div>
        </v-card>
      </v-col>
    </v-row>

    <v-dialog :model-value="Boolean(editing)" max-width="480" @update:model-value="editing = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-4">{{ editing?.id ? 'Edit tool' : 'Add tool' }}</div>
        <v-text-field v-model="form.name" label="Tool" placeholder="e.g. Discover it credit card" class="mb-3" />
        <v-combobox
          v-model="form.purpose"
          :items="purposes"
          label="Purpose"
          placeholder="Credit card, Payment, Shopping…"
          variant="outlined"
          density="comfortable"
          hide-details
          class="mb-3"
        />
        <v-text-field
          v-model="form.bonus"
          label="Referral bonus"
          placeholder="100, $30-40, 50% off 2 rides"
          class="mb-3"
        />
        <v-text-field
          v-model="form.link"
          label="Referral link or code"
          placeholder="https://… or a plain code"
          class="mb-3"
        />
        <v-textarea v-model="form.note" label="Note (optional)" rows="2" />
        <div class="d-flex justify-end ga-2 mt-4">
          <v-btn variant="text" @click="editing = null">Cancel</v-btn>
          <v-btn color="primary" :disabled="!form.name.trim()" @click="save">Save</v-btn>
        </div>
      </v-card>
    </v-dialog>

    <v-dialog :model-value="Boolean(confirm)" max-width="440" @update:model-value="confirm = null">
      <v-card class="pa-5">
        <div class="text-h6 mb-2">{{ confirm?.title }}</div>
        <div class="text-body-2 text-medium-emphasis">{{ confirm?.text }}</div>
        <div class="d-flex justify-end ga-2 mt-5 flex-wrap">
          <v-btn variant="text" @click="confirm = null">Cancel</v-btn>
          <v-btn color="error" variant="tonal" @click="runConfirm(true)">Delete</v-btn>
          <v-btn color="primary" @click="runConfirm(false)">Hide</v-btn>
        </div>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<style scoped>
.min-w-0 {
  min-width: 0;
}
.opacity-60 {
  opacity: 0.6;
}
</style>
