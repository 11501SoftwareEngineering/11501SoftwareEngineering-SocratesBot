import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import './assets/main.css'

import App from './App.vue'
import router from './router'
import { queryClient } from './queryClient'

function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()
  pinia.use(piniaPluginPersistedstate)
  app.use(pinia)
  app.use(router)
  app.use(VueQueryPlugin, { queryClient })
  app.mount('#app')
}

bootstrap()
