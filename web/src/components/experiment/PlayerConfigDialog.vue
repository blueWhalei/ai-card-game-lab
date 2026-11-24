<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  experimentConfigApi,
  type ExperimentConfig,
  type CreateExperimentConfigRequest,
  type PlayerPolicyKind,
} from '@/api/experimentConfigApi'
import { systemApi, type ProviderInfo } from '@/api/systemApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { providerName } from '@/utils/systemLabels'
import { policyLabels, isBaselineKind } from '@/utils/playerPolicy'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'

const { t } = useI18n()
const emit = defineEmits<{ saved: [config: ExperimentConfig] }>()
const submitting = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)

const providers = ref<Omit<ProviderInfo, 'configured'>[]>([])
const providerOptions = computed(() =>
  providers.value.map((p) => ({ label: providerName(p.id, p.name), value: p.id })),
)

const policyKindOptions = computed(() =>
  Object.entries(policyLabels).map(([value, key]) => ({ value, label: t(key) })),
)

const defaultModelConfig = () => ({
  provider: 'openai',
  model_name: 'gpt-4o-mini',
  temperature: 0.7,
  top_p: 0.95,
  max_tokens: 1024,
})

const defaultForm = (): CreateExperimentConfigRequest => ({
  id: '',
  name: '',
  notes: '',
  policy_kind: 'llm',
  model_config_data: defaultModelConfig(),
})

const form = ref<CreateExperimentConfigRequest>(defaultForm())
const isBaselineForm = computed(() => isBaselineKind(form.value.policy_kind))

function onProviderChange(val: string) {
  const provider = providers.value.find((p) => p.id === val)
  if (provider?.default_model && form.value.model_config_data) {
    form.value.model_config_data.model_name = provider.default_model
  }
}

function onPolicyKindChange(val: string) {
  const kind = (val as PlayerPolicyKind) || 'llm'
  form.value.policy_kind = kind
  if (
    !isBaselineKind(kind) &&
    (!form.value.model_config_data || form.value.model_config_data.provider === 'baseline')
  ) {
    form.value.model_config_data = defaultModelConfig()
  }
}

async function open(config?: ExperimentConfig) {
  isEditing.value = !!config
  form.value = config
    ? {
        id: config.id,
        name: config.name,
        notes: config.notes,
        policy_kind: config.policy_kind,
        model_config_data: { ...config.model_config },
      }
    : defaultForm()
  dialogVisible.value = true
  try {
    providers.value = (await systemApi.providerOptions()).data
  } catch (error) {
    showApiError(error, t('config.loadFailed'))
  }
}
defineExpose({ open })

async function handleSubmit() {
  const id = form.value.id.trim()
  const name = form.value.name.trim()
  if (!isEditing.value && !id) {
    toast.warning(t('config.needId'))
    return
  }
  if (!name) {
    toast.warning(t('config.needName'))
    return
  }
  const policyKind = form.value.policy_kind ?? 'llm'
  if (submitting.value) return
  submitting.value = true
  try {
    const fields = {
      name,
      notes: form.value.notes,
      policy_kind: policyKind,
      model_config_data: isBaselineKind(policyKind) ? null : form.value.model_config_data,
    }
    const result = isEditing.value
      ? await experimentConfigApi.update(id, fields)
      : await experimentConfigApi.create({ id, ...fields })
    toast.success(t(isEditing.value ? 'config.updated' : 'config.created'))
    dialogVisible.value = false
    emit('saved', result.data)
  } catch (e: unknown) {
    showApiError(e, t('error.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UiDialog
    :open="dialogVisible"
    size="lg"
    :title="isEditing ? t('config.editTitle') : t('config.createTitle')"
    @update:open="dialogVisible = $event"
  >
    <div class="space-y-4">
      <div v-if="!isEditing">
        <label class="mb-1.5 block text-body font-medium text-ink-text">
          {{ t('config.playerId') }} <span class="text-ink-danger">*</span>
        </label>
        <UiInput
          v-model="form.id"
          :aria-label="t('config.playerId')"
          :placeholder="t('config.idPlaceholder')"
          class="w-full"
        />
      </div>
      <div>
        <label class="mb-1.5 block text-body font-medium text-ink-text">
          {{ t('common.name') }} <span class="text-ink-danger">*</span>
        </label>
        <UiInput
          v-model="form.name"
          :aria-label="t('common.name')"
          :placeholder="t('config.namePlaceholder')"
          class="w-full"
        />
      </div>
      <div>
        <label class="mb-1.5 block text-body font-medium text-ink-text">{{
          t('common.notes')
        }}</label>
        <UiTextarea
          v-model="form.notes"
          :aria-label="t('common.notes')"
          :rows="2"
          :placeholder="t('config.notesPlaceholder')"
          class="w-full"
        />
      </div>

      <div>
        <label class="mb-1.5 block text-body font-medium text-ink-text">{{
          t('config.policyKind')
        }}</label>
        <UiSelect
          :aria-label="t('config.policyKind')"
          :model-value="form.policy_kind ?? 'llm'"
          :options="policyKindOptions"
          class="w-full"
          @update:model-value="onPolicyKindChange"
        />
        <p v-if="isBaselineForm" class="mt-ink-1 text-caption text-ink-text-muted">
          {{ t('config.policyKindHint') }}
        </p>
      </div>

      <div
        v-if="!isBaselineForm && form.model_config_data"
        class="rounded-ink-md bg-ink-surface-muted p-ink-4"
      >
        <h4 class="mb-ink-3 font-medium text-ink-text">{{ t('config.modelSection') }}</h4>
        <div class="space-y-ink-3">
          <div>
            <label class="mb-1.5 block text-body font-medium text-ink-text">{{
              t('config.provider')
            }}</label>
            <UiSelect
              v-model="form.model_config_data.provider"
              :aria-label="t('config.provider')"
              :options="providerOptions"
              class="w-full"
              @update:model-value="onProviderChange"
            />
          </div>
          <div>
            <label class="mb-1.5 block text-body font-medium text-ink-text">{{
              t('config.modelName')
            }}</label>
            <UiInput
              v-model="form.model_config_data.model_name"
              :aria-label="t('config.modelName')"
              placeholder="gpt-4o-mini"
              class="w-full"
            />
          </div>
          <div class="grid grid-cols-1 gap-ink-3 sm:grid-cols-3">
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">Temperature</label>
              <UiInputNumber
                :model-value="form.model_config_data.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                class="w-full"
                @update:model-value="(v) => (form.model_config_data!.temperature = v ?? 0.7)"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">Top P</label>
              <UiInputNumber
                :model-value="form.model_config_data.top_p"
                :min="0"
                :max="1"
                :step="0.05"
                class="w-full"
                @update:model-value="(v) => (form.model_config_data!.top_p = v ?? 0.95)"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">Max Tokens</label>
              <UiInputNumber
                :model-value="form.model_config_data.max_tokens"
                :min="64"
                :max="4096"
                :step="64"
                class="w-full"
                @update:model-value="(v) => (form.model_config_data!.max_tokens = v ?? 1024)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <UiButton variant="secondary" @click="dialogVisible = false">{{
        t('common.cancel')
      }}</UiButton>
      <UiButton :loading="submitting" @click="handleSubmit">{{
        isEditing ? t('common.save') : t('common.create')
      }}</UiButton>
    </template>
  </UiDialog>
</template>
