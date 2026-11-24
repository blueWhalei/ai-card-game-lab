/** @vitest-environment happy-dom */
import { expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { ExperimentProtocol, ExperimentValidation } from '@/api/experimentApi'
import zhCN from '@/i18n/locales/zh-CN'
import ExperimentMetaPanel from './ExperimentMetaPanel.vue'

it('shows actual phase versions and links without calling uncollected runs validation in progress', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push('/')
  const validation = {
    control_experiment_ids: [],
    validation_ready: false,
    paired_n: 0,
  } as unknown as ExperimentValidation
  const wrapper = mount(ExperimentMetaPanel, {
    props: {
      validation,
      protocol: {
        prompt_version: 'initial',
        prompt_keys: { playing: 'play', bidding: 'bid' },
        prompt_versions: { play: 'followup', bid: 'v3' },
        prompt_hashes: { play: 'hash-play', bid: 'hash-bid' },
      } as unknown as ExperimentProtocol,
      protocolPlayers: [],
      protocolDrift: false,
      shortExperimentId: (id) => id,
    },
    global: {
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  expect(wrapper.text()).toContain('提示词版本 · 出牌阶段: followup')
  expect(wrapper.text()).toContain('提示词版本 · 叫地主阶段: v3')
  expect(wrapper.text()).toContain('提示词哈希 · 叫地主阶段: hash-bid')
  expect(wrapper.text()).not.toMatch(/initial|对照进行中|配对局 0/)
  await wrapper.setProps({ validation: { ...validation, control_experiment_ids: ['b'] } })
  expect(wrapper.text()).toContain('关联对照运行')
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'b')!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/experiments/b')
  wrapper.unmount()
})
