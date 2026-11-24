<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  experimentConfigApi,
  type ExperimentConfig,
  type SeatModelCheck,
} from '@/api/experimentConfigApi'
import { isBaselineKind } from '@/utils/playerPolicy'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{ players: ExperimentConfig[] }>()
const emit = defineEmits<{ edit: [player: ExperimentConfig] }>()
const { t } = useI18n()
const modelSeats = computed(() =>
  props.players.filter((player) => !isBaselineKind(player.policy_kind)),
)
const checks = ref<SeatModelCheck[]>([])
const configFile = ref('')
const busy = ref(false)
const failed = ref(false)
let request = 0

async function check(connect = false) {
  const version = ++request
  const ids = modelSeats.value.map((seat) => seat.id)
  checks.value = []
  busy.value = ids.length > 0
  failed.value = false
  configFile.value = ''
  if (!ids.length) return
  try {
    const { data } = await experimentConfigApi.readiness(ids, connect)
    if (request !== version) return
    checks.value = data.checks
    configFile.value = data.config_file
  } catch {
    if (request === version) failed.value = true
  } finally {
    if (request === version) busy.value = false
  }
}
watch(modelSeats, () => void check(), { immediate: true })
const rows = computed(() =>
  modelSeats.value.map((player) => ({
    player,
    check: checks.value.find((item) => item.player_id === player.id),
  })),
)
const canProbe = computed(() =>
  checks.value.some(
    (check) =>
      !['missing_key', 'unknown_provider', 'invalid_model', 'invalid_url'].includes(check.status),
  ),
)
</script>

<template>
  <section v-if="players.length" class="space-y-2 rounded-ink border border-ink-border p-ink-3">
    <h3 class="text-body font-medium">{{ t('runSetup.conditions') }}</h3>
    <div
      aria-live="polite"
      :aria-busy="busy"
      class="space-y-2 text-caption text-ink-text-secondary"
    >
      <p v-if="!modelSeats.length">{{ t('runSetup.offlineReady') }}</p>
      <p v-else-if="busy">{{ t('common.loading') }}</p>
      <p v-else-if="failed">{{ t('runSetup.checkFailed') }}</p>
      <template v-else>
        <div v-for="{ player, check: result } in rows" :key="player.id">
          <template v-if="result">
            <button
              type="button"
              class="font-medium text-ink-primary hover:underline"
              @click="emit('edit', player)"
            >
              {{ player.name }}
            </button>
            · {{ result.provider }} / {{ result.model }}
            <p>
              {{
                t(
                  `runSetup.status.${result.provider === 'ollama' && result.status === 'not_listed' ? 'not_installed' : result.status}`,
                  { setting: result.setting },
                )
              }}
            </p>
          </template>
        </div>
        <p
          v-if="
            checks.some(
              (row) =>
                row.setting || row.status === 'access_denied' || row.status === 'unreachable',
            )
          "
          class="break-words"
        >
          {{ t('runSetup.configFile', { path: configFile }) }}
        </p>
      </template>
    </div>
    <template v-if="modelSeats.length">
      <UiButton v-if="failed" size="sm" variant="secondary" @click="check()">{{
        t('common.retry')
      }}</UiButton>
      <UiButton v-else-if="canProbe" size="sm" variant="secondary" @click="check(true)">{{
        t('runSetup.probe')
      }}</UiButton>
      <p class="text-caption text-ink-text-muted">{{ t('runSetup.probeHint') }}</p>
    </template>
  </section>
</template>
