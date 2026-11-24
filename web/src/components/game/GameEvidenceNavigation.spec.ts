/** @vitest-environment happy-dom */
import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import zhCN from '@/i18n/locales/zh-CN'
import GameResultDialog from './GameResultDialog.vue'
import GameHighlightList from './GameHighlightList.vue'

enableAutoUnmount(afterEach)
async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/game/:id', component: { template: '<div />' } },
      { path: '/pipeline/decisions', component: { template: '<div />' } },
    ],
  })
  await router.push('/game/game-a')
  const global = {
    plugins: [router, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
  }
  return { router, global }
}
it('opens the canonical decision workbench from the game result', async () => {
  const { router, global } = await setup()
  const wrapper = mount(GameResultDialog, {
    props: { gameId: 'game-a', modelValue: true, winner: null },
    global: {
      ...global,
      stubs: { UiDialog: { template: '<div><slot /><slot name="footer" /></div>' } },
    },
  })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === zhCN.game.viewDecisions)!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/pipeline/decisions')
  expect(router.currentRoute.value.query).toEqual({ game_id: 'game-a' })
  expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
})
it('preserves the game and exact decision when opening a recorded highlight', async () => {
  const { router, global } = await setup()
  const wrapper = mount(GameHighlightList, {
    props: {
      gameId: 'game-a',
      items: [
        {
          decision_id: 'decision-a',
          player_id: 'p',
          round_number: 3,
          reason: 'bomb',
          action_type: 'PASS',
          cards: [],
        },
      ],
    },
    global,
  })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === zhCN.game.viewDecision)!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/pipeline/decisions')
  expect(router.currentRoute.value.query).toEqual({ game_id: 'game-a', decision_id: 'decision-a' })
})
