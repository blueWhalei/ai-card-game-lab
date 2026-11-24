import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

test('freezes the observed player and displays every seat sharing the changed prompt', async ({
  page,
  request,
}) => {
  const tag = randomUUID().slice(0, 8)
  const players: string[] = []
  for (const [name, policy] of [
    ['North', 'llm'],
    ['East', 'heuristic'],
    ['South', 'llm'],
  ] as const) {
    const id = `cfg_${tag}_${name}`
    const created = await request.post('/api/v1/experiment-configs', {
      data: {
        id,
        name,
        policy_kind: policy,
        model_config_data:
          policy === 'llm' ? { provider: 'ollama', model_name: 'test-model' } : null,
      },
    })
    expect(created.status()).toBe(201)
    players.push(id)
  }
  const baseline = await request.post('/api/v1/experiments', {
    data: {
      name: 'Prompt baseline',
      hypothesis: 'How does North’s team perform?',
      player_ids: players,
      target_games: 2,
      collect_mode: 'benchmark',
    },
  })
  expect(baseline.status()).toBe(201)
  const a = (await baseline.json()).data
  const key = a.protocol.engine.prompt_keys.playing
  const version = `test-${tag}`
  const template = await request.post('/api/v1/prompts', {
    data: {
      template_key: key,
      version,
      content: a.protocol.solver.prompts[key].content + '\nReview legal moves.',
    },
  })
  expect(template.status()).toBe(201)

  await page.addInitScript(() => localStorage.setItem('ink-locale', 'en'))
  await page.goto(`/research/${a.study_id}/prompt-ab`)
  await page.locator('#baseline').selectOption(a.id)
  await page.getByRole('button', { name: 'Next', exact: true }).click()
  await page.locator('#phase').selectOption(key)
  await page.locator('#version').selectOption(version)
  const next = page.getByRole('button', { name: 'Next', exact: true })
  await expect(next).toBeDisabled()
  const outcome = page.locator('#primary-metric')
  await expect(outcome.getByRole('option', { name: /East/ })).toHaveCount(0)
  await outcome.selectOption({ label: 'Team win rate for #1 North' })
  await expect(page.getByText(/Several seats change prompts together/)).toBeVisible()
  await next.click()
  await expect(
    page.getByText(/Seats using the changed phase prompt: #1 North, #3 South/),
  ).toBeVisible()
  const saving = page.waitForResponse((response) => response.url().endsWith('/prompt-variant'))
  await page.getByRole('button', { name: /create B/i }).click()
  const response = await saving
  expect(response.status()).toBe(201)
  const b = (await response.json()).data
  await expect(page).toHaveURL(new RegExp(`/experiments/${b.id}$`))
  expect(b.protocol.design.primary_metric).toEqual({
    kind: 'seat_team_win_rate',
    player_id: players[0],
  })
  expect(b.protocol.design.affected_player_ids).toEqual([players[0], players[2]])
  expect(b.games).toEqual([])
})
