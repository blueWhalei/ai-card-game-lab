import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/layouts/WorkbenchLayout.vue'),
      children: [
        {
          path: '',
          name: 'pipeline',
          component: () => import('@/views/PipelineView.vue'),
        },
        {
          path: 'game',
          name: 'game',
          component: () => import('@/views/GameView.vue'),
        },
        {
          path: 'ai-players',
          name: 'ai-players',
          component: () => import('@/views/AIPlayerView.vue'),
        },
        {
          path: 'data',
          name: 'data',
          component: () => import('@/views/DataView.vue'),
        },
        {
          path: 'training',
          name: 'training',
          component: () => import('@/views/TrainingView.vue'),
        },
        {
          path: 'prompt',
          name: 'prompt',
          component: () => import('@/views/PromptView.vue'),
        },
        {
          path: 'traces',
          name: 'traces',
          component: () => import('@/views/TraceView.vue'),
        },
        {
          path: 'decisions',
          name: 'decisions',
          component: () => import('@/views/DecisionView.vue'),
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
        },
      ],
    },
    {
      path: '/game/:id',
      component: () => import('@/layouts/ObserverLayout.vue'),
      children: [
        {
          path: '',
          name: 'game-observer',
          component: () => import('@/views/GameObserverView.vue'),
        },
      ],
    },
  ],
})

export default router
