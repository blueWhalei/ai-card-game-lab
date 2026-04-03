import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/game',
    },
    {
      path: '/game',
      name: 'game',
      component: () => import('@/views/GameView.vue'),
    },
    {
      path: '/game/:id',
      name: 'game-observer',
      component: () => import('@/views/GameObserverView.vue'),
    },
    {
      path: '/ai-players',
      name: 'ai-players',
      component: () => import('@/views/AIPlayerView.vue'),
    },
    {
      path: '/data',
      name: 'data',
      component: () => import('@/views/DataView.vue'),
    },
    {
      path: '/training',
      name: 'training',
      component: () => import('@/views/TrainingView.vue'),
    },
    {
      path: '/prompt',
      name: 'prompt',
      component: () => import('@/views/PromptView.vue'),
    },
    {
      path: '/traces',
      name: 'traces',
      component: () => import('@/views/TraceView.vue'),
    },
    {
      path: '/decisions',
      name: 'decisions',
      component: () => import('@/views/DecisionView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
    },
  ],
})

export default router
