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
          name: 'experiments',
          component: () => import('@/views/ExperimentListView.vue'),
        },
        {
          path: 'experiments/compare',
          name: 'experiment-compare',
          component: () => import('@/views/ExperimentCompareView.vue'),
        },
        {
          path: 'experiments/:id',
          name: 'experiment-detail',
          component: () => import('@/views/ExperimentDetailView.vue'),
        },
        {
          path: 'pipeline',
          name: 'pipeline',
          redirect: '/',
        },
        {
          path: 'game',
          name: 'game',
          component: () => import('@/views/GameView.vue'),
        },
        {
          path: 'experiment-configs',
          name: 'experiment-configs',
          component: () => import('@/views/ExperimentConfigView.vue'),
        },
        {
          path: 'ai-players',
          redirect: '/experiment-configs',
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
        {
          path: 'guide',
          name: 'guide',
          component: () => import('@/views/GuideView.vue'),
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
