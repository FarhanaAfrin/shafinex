<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { errorMessage } from '@/api'
import { useSession } from '@/stores/session'
import { useStructure } from '@/stores/structure'

const session = useSession()
const structure = useStructure()
const router = useRouter()
const route = useRoute()

const password = ref('')
const show = ref(false)
const busy = ref(false)
const error = ref('')

async function submit() {
  if (!password.value) return
  busy.value = true
  error.value = ''
  try {
    await session.login(password.value)
    await structure.load(true)
    router.push(route.query.next || { name: session.prefs?.start_page === 'settings' ? 'settings' : 'dashboard' })
  } catch (err) {
    error.value = errorMessage(err, 'Could not sign in')
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  if (session.isAuthenticated) router.push({ name: 'dashboard' })
})
</script>

<template>
  <v-container class="fill-height justify-center" fluid>
    <v-card class="pa-8" max-width="420" width="100%">
      <div class="d-flex align-center ga-3 mb-6">
        <v-avatar color="primary" rounded="lg" size="40">
          <v-icon color="white">mdi-finance</v-icon>
        </v-avatar>
        <div>
          <div class="text-h6 font-weight-bold">Welcome back</div>
          <div class="text-caption text-medium-emphasis">Your money, your rules.</div>
        </div>
      </div>

      <v-form @submit.prevent="submit">
        <v-text-field
          v-model="password"
          :type="show ? 'text' : 'password'"
          label="Password"
          autofocus
          autocomplete="current-password"
          :append-inner-icon="show ? 'mdi-eye-off' : 'mdi-eye'"
          :error-messages="error"
          @click:append-inner="show = !show"
        />
        <v-btn
          type="submit"
          color="primary"
          block
          size="large"
          class="mt-4"
          :loading="busy"
          :disabled="!password"
        >
          Sign in
        </v-btn>
      </v-form>

      <div class="text-caption text-medium-emphasis mt-6">
        Single-user app. The password is the one set in your server environment.
      </div>
    </v-card>
  </v-container>
</template>
