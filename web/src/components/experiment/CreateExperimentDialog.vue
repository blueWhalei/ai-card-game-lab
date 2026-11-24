<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { experimentApi, type CollectMode } from '@/api/experimentApi'
import type { ExperimentConfig } from '@/api/experimentConfigApi'
import type { Study } from '@/api/studyApi'
import {
  isValidPlayerSelection,
  maxSelectable,
  playerCountLabel,
  supportsBenchmark,
  type EngineInfo,
} from '@/utils/engineSlots'
import { isBaselineKind, policyLabels } from '@/utils/playerPolicy'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import UiDialog from '@/components/ui/Dialog.vue'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiInput from '@/components/ui/Input.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import PlayerConfigDialog from './PlayerConfigDialog.vue'
import SeatReadiness from './SeatReadiness.vue'

const props = defineProps<{
  configs: ExperimentConfig[]
  engines: EngineInfo[]
  study: Study | null
  initialLineup: 'offline' | 'custom' | 'prompt-baseline'
}>()
const emit = defineEmits<{
  close: []
  created: [id: string]
  playerSaved: [config: ExperimentConfig]
}>()
const { t } = useI18n()
const offlineAvailable = props.engines.some((e) => e.id === 'doudizhu' && supportsBenchmark(e))
const offline = ref(offlineAvailable && props.initialLineup === 'offline')
const currentEngine = computed(() => props.engines[0])
const slotsLabel = computed(() => playerCountLabel(currentEngine.value))
const maxPlayers = computed(() => maxSelectable(currentEngine.value))
const canUseBenchmark = computed(() => supportsBenchmark(currentEngine.value))
const editor = ref<InstanceType<typeof PlayerConfigDialog>>()
const creating = ref(false)
const formName = ref('')
const formNotes = ref('')
const formHypothesis = ref(props.study?.question ?? '')
const formTags = ref('')
const formCollectMode = ref<CollectMode>('free')
const formPromptVersion = ref('v3')
const formTarget = ref(10)
const selectedConfigIds = ref(props.configs.slice(0, maxPlayers.value).map((c) => c.id))
const selectedPlayers = computed(() =>
  selectedConfigIds.value.flatMap((id) => props.configs.find((c) => c.id === id) ?? []),
)
const canSubmit = computed(
  () =>
    offline.value ||
    (!!formName.value.trim() &&
      isValidPlayerSelection(selectedConfigIds.value.length, currentEngine.value) &&
      Number.isInteger(formTarget.value) &&
      formTarget.value >= 1 &&
      formTarget.value <= 50),
)

function setCollectMode(mode: CollectMode): void {
  formCollectMode.value = mode
  if (mode === 'benchmark') {
    const n = currentEngine.value?.benchmark_seed_count ?? 50
    formTarget.value = Math.min(50, Math.max(1, n))
  }
}

if (props.initialLineup === 'prompt-baseline' && canUseBenchmark.value) {
  setCollectMode('benchmark')
}

function toggleConfig(id: string, checked: boolean): void {
  if (checked) {
    if (selectedConfigIds.value.includes(id)) return
    if (selectedConfigIds.value.length >= maxPlayers.value) {
      toast.warning(t('experiment.needExactPlayers', { n: slotsLabel.value }))
      return
    }
    selectedConfigIds.value = [...selectedConfigIds.value, id]
    return
  }
  selectedConfigIds.value = selectedConfigIds.value.filter((x) => x !== id)
}

function savePlayer(config: ExperimentConfig) {
  emit('playerSaved', config)
  if (
    selectedConfigIds.value.length < maxPlayers.value &&
    !selectedConfigIds.value.includes(config.id)
  ) {
    selectedConfigIds.value = [...selectedConfigIds.value, config.id]
  }
}

async function submitCreate() {
  if (!canSubmit.value || creating.value) return
  creating.value = true
  try {
    const fields = {
      study_id: props.study?.id,
      name: formName.value.trim() || t('runSetup.offlineName'),
      hypothesis: formHypothesis.value.trim(),
    }
    const { data } = offline.value
      ? await experimentApi.createOffline(fields)
      : await experimentApi.create({
          ...fields,
          game_type: currentEngine.value?.id,
          player_ids: selectedConfigIds.value,
          target_games: formTarget.value,
          collect_mode: formCollectMode.value,
          prompt_version: formPromptVersion.value.trim() || undefined,
          notes: formNotes.value.trim(),
          tags: formTags.value
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean)
            .slice(0, 20),
        })
    toast.success(t('experiment.created'))
    emit('created', data.id)
  } catch (e) {
    showApiError(e, t('experiment.createFailed'))
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <UiDialog
    :open="true"
    size="lg"
    :title="t('experiment.createTitle')"
    :description="t('study.runCreateHint')"
    @update:open="
      (value) => {
        if (!value && !creating) emit('close')
      }
    "
  >
    <div class="space-y-ink-4">
      <div class="flex flex-wrap gap-ink-2" role="group" :aria-label="t('runSetup.lineup')">
        <UiButton
          size="sm"
          :variant="offline ? 'primary' : 'secondary'"
          :aria-pressed="offline"
          :disabled="!offlineAvailable"
          @click="offline = true"
          >{{ t('runSetup.offline') }}</UiButton
        >
        <UiButton
          size="sm"
          :variant="!offline ? 'primary' : 'secondary'"
          :aria-pressed="!offline"
          @click="offline = false"
          >{{ t('runSetup.custom') }}</UiButton
        >
      </div>
      <p v-if="offline" class="text-body text-ink-text-secondary">
        {{ t('runSetup.offlineHint') }}
      </p>
      <label v-if="!offline || formHypothesis || study?.question" class="block space-y-2">
        <span class="text-body font-medium">{{ t('experiment.hypothesis') }}</span>
        <UiTextarea
          v-model="formHypothesis"
          :rows="2"
          :maxlength="10000"
          :placeholder="t('experiment.hypothesisPlaceholder')"
        />
      </label>
      <label class="block space-y-2">
        <span class="text-body font-medium">{{ t('common.name') }}</span>
        <UiInput
          v-model="formName"
          :maxlength="120"
          :placeholder="offline ? t('runSetup.offlineName') : t('experiment.namePlaceholder')"
          class="w-full"
        />
      </label>
      <template v-if="!offline">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h3 class="text-body font-medium">
            {{ t('experiment.pickPlayers', { n: slotsLabel }) }} · {{ selectedConfigIds.length }}/{{
              maxPlayers
            }}
          </h3>
          <UiButton size="sm" variant="secondary" @click="editor?.open()">{{
            t('config.add')
          }}</UiButton>
        </div>
        <p v-if="!currentEngine" role="alert" class="text-caption">{{ t('runSetup.noEngine') }}</p>
        <p
          v-else-if="!isValidPlayerSelection(selectedConfigIds.length, currentEngine)"
          class="text-caption text-ink-text-secondary"
        >
          {{
            t('runSetup.needSeats', {
              count: Math.max(0, currentEngine.min_players - selectedConfigIds.length),
            })
          }}
        </p>
        <div v-if="configs.length" class="grid max-h-56 gap-ink-2 overflow-y-auto sm:grid-cols-2">
          <div
            v-for="cfg in configs"
            :key="cfg.id"
            class="flex items-start gap-ink-2 rounded-ink border border-ink-border px-ink-3 py-ink-2 hover:bg-ink-surface-muted"
          >
            <UiCheckbox
              :model-value="selectedConfigIds.includes(cfg.id)"
              class="mt-0.5"
              :label="cfg.name"
              @update:model-value="(v) => toggleConfig(cfg.id, Boolean(v))"
            />
            <span class="min-w-0 flex-1 pt-0.5 text-caption text-ink-text-muted">
              {{
                isBaselineKind(cfg.policy_kind)
                  ? t(policyLabels[cfg.policy_kind])
                  : [cfg.model_config.provider, cfg.model_config.model_name].join(' / ')
              }}
            </span>
          </div>
        </div>

        <p
          v-if="
            initialLineup === 'prompt-baseline' &&
            !selectedPlayers.some((player) => !isBaselineKind(player.policy_kind))
          "
          class="text-caption text-ink-text-secondary"
        >
          {{ t('promptDesign.issues.model_player_required') }}
        </p>
        <SeatReadiness :players="selectedPlayers" @edit="(player) => editor?.open(player)" />
        <details class="text-body">
          <summary class="cursor-pointer">
            {{ t('experiment.createMoreFields') }} · {{ t('experiment.targetGames') }}
            {{ formTarget }}
          </summary>
          <div class="mt-ink-3 grid gap-ink-4 sm:grid-cols-2">
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">
                {{ t('experiment.targetGames') }}
              </label>
              <UiInputNumber v-model="formTarget" :min="1" :max="50" />
            </div>
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{
                t('experiment.collectMode')
              }}</label>
              <div class="flex flex-wrap gap-ink-2">
                <UiButton
                  size="sm"
                  :variant="formCollectMode === 'free' ? 'primary' : 'secondary'"
                  type="button"
                  @click="setCollectMode('free')"
                >
                  {{ t('experiment.collectModeFree') }}
                </UiButton>
                <UiButton
                  size="sm"
                  :variant="formCollectMode === 'benchmark' ? 'primary' : 'secondary'"
                  type="button"
                  :disabled="!canUseBenchmark"
                  @click="setCollectMode('benchmark')"
                >
                  {{ t('experiment.collectModeBenchmark') }}
                </UiButton>
              </div>
              <p
                v-if="formCollectMode === 'benchmark'"
                class="mt-1.5 text-caption text-ink-text-secondary"
              >
                {{ t('experiment.collectModeBenchmarkHint') }}
              </p>
            </div>
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">
                {{ t('experiment.promptVersion') }}
              </label>
              <UiInput
                v-model="formPromptVersion"
                :placeholder="t('experiment.promptVersionPlaceholder')"
              />
              <p class="mt-1.5 text-caption text-ink-text-secondary">
                {{ t('experiment.promptVersionHint') }}
              </p>
            </div>
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{
                t('common.notes')
              }}</label>
              <UiTextarea
                v-model="formNotes"
                :rows="3"
                :placeholder="t('experiment.notesPlaceholder')"
                class="w-full"
              />
            </div>
            <div class="sm:col-span-2">
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{
                t('experiment.tags')
              }}</label>
              <UiInput
                v-model="formTags"
                :placeholder="t('experiment.tagsPlaceholder')"
                class="w-full"
              />
            </div>
          </div>
        </details>
        <PlayerConfigDialog ref="editor" @saved="savePlayer" />
      </template>
    </div>
    <template #footer>
      <UiButton variant="secondary" :disabled="creating" @click="emit('close')">{{
        t('common.cancel')
      }}</UiButton>
      <UiButton :disabled="!canSubmit" :loading="creating" @click="submitCreate">{{
        t('experiment.createAndOpen')
      }}</UiButton>
    </template>
  </UiDialog>
</template>
