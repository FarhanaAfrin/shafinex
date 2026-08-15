import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'
import { setUnauthorizedHandler } from './api'
import { useSession } from './stores/session'
import './styles/app.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(vuetify)

const session = useSession(pinia)
setUnauthorizedHandler(() => {
  session.logout()
  router.push({ name: 'login' })
})

app.mount('#app')
