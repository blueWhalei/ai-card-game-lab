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
          component: () => import('@/views/PipelineView.vue'),
          redirect: (to) => ({ path: '/pipeline/data', query: to.query }),
          children: [
            {
              path: 'data',
              name: 'data',
              component: () => import('@/views/DataView.vue'),
            },
            {
              path: 'decisions',
              name: 'decisions',
              component: () => import('@/views/DecisionView.vue'),
            },
            {
              path: 'training',
              name: 'training',
              component: () => import('@/views/TrainingView.vue'),
            },
            {
              path: 'traces',
              name: 'traces',
              component: () => import('@/views/TraceView.vue'),
            },
          ],
        },
        {
          path: 'data',
          redirect: (to) => ({ path: '/pipeline/data', query: to.query }),
        },
        {
          path: 'decisions',
          redirect: (to) => ({ path: '/pipeline/decisions', query: to.query }),
        },
        {
          path: 'training',
          redirect: (to) => ({ path: '/pipeline/training', query: to.query }),
        },
        {
          path: 'traces',
          redirect: (to) => ({ path: '/pipeline/traces', query: to.query }),
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
          path: 'prompt',
          name: 'prompt',
          component: () => import('@/views/PromptView.vue'),
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
