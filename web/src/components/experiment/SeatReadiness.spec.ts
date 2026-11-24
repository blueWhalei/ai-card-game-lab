/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import {
  experimentConfigApi,
  type ExperimentConfig,
  type SeatModelCheck,
} from '@/api/experimentConfigApi'
import en from '@/i18n/locales/en'
import SeatReadiness from './SeatReadiness.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())

function player(id: string): ExperimentConfig {
  return {
    id,
    name: id,
    notes: '',
    policy_kind: 'llm',
    model_config: {
      provider: 'openai',
      model_name: id,
      temperature: 0,
      top_p: 1,
      max_tokens: 100,
    },
  }
}

function result(id: string, status: SeatModelCheck['status']) {
  return {
    code: 0,
    message: '',
    data: {
      config_file: 'config.env',
      checks: [
        {
          player_id: id,
          model: id,
          provider: 'openai',
          setting: '',
          status,
        },
      ],
    },
  }
}

it('does not probe automatically or show a late connection result on another lineup', async () => {
  const checks = vi.spyOn(experimentConfigApi, 'readiness')
  let finish!: (value: ReturnType<typeof result>) => void
  checks.mockImplementation(async ([id], connect) =>
    connect
      ? new Promise((resolve) => {
          finish = resolve
        })
      : result(id!, 'configured'),
  )
  const one = player('one')
  const wrapper = mount(SeatReadiness, {
    props: { players: [one] },
    global: { plugins: [createI18n({ legacy: false, locale: 'en', messages: { en } })] },
  })
  await flushPromises()
  expect(checks.mock.calls).toEqual([[['one'], false]])
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Check model connection')!
    .trigger('click')
  expect(checks).toHaveBeenCalledWith(['one'], true)
  await wrapper.setProps({ players: [player('two')] })
  finish(result('one', 'listed'))
  await flushPromises()
  expect(wrapper.text()).toContain('two')
  expect(wrapper.text()).toContain('Connection unchecked')
  expect(wrapper.text()).not.toContain('The model is listed')
  checks.mockClear()
  await wrapper.setProps({ players: [{ ...one, policy_kind: 'heuristic' }] })
  expect(wrapper.text()).toContain('run locally')
  expect(checks).not.toHaveBeenCalled()
})
