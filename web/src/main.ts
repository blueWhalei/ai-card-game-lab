import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import { initLocale } from './composables/useLocale'
import { initTheme } from './composables/useTheme'
import './styles/index.css'
import { useDesktopWorkspace } from './stores/useDesktopWorkspace'

initTheme()
initLocale()

const app = createApp(App)

app.use(createPinia())
app.use(i18n)
app.use(router)

async function mount() {
  const disconnect = await useDesktopWorkspace().initialize(router)
  app.onUnmount(disconnect)
  app.mount('#app')
}
void mount()
