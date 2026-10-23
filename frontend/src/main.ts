import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import './assets/main.css'

import App from './App.vue'
import router from './router'
import { queryClient } from './queryClient'

async function enableMocking() {
  // Demo 模式：在瀏覽器裡啟動假後端（src/mocks），所有 /api/v1 請求都會被攔截
  if (import.meta.env.VITE_USE_MOCK !== 'true') return
  const { worker } = await import('./mocks/browser')
  await worker.start({
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    onUnhandledRequest: 'bypass',
    quiet: true,
  })
}

async function bootstrap() {
  await enableMocking()

  const app = createApp(App)
  const pinia = createPinia()
  pinia.use(piniaPluginPersistedstate)
  app.use(pinia)
  app.use(router)
  app.use(VueQueryPlugin, { queryClient })
  app.mount('#app')
}

void bootstrap()
