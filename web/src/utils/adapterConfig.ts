/** Shared naming for LoRA → Ollama experiment-config registration. */

export function ollamaTagForModel(modelId: string): string {
  const short = modelId.replace(/[^a-zA-Z0-9]/g, '').slice(0, 12) || 'model'
  return `acgl-${short}`
}

export function configIdForModel(modelId: string): string {
  const short = modelId.replace(/[^a-zA-Z0-9_]/g, '_').slice(0, 40) || 'model'
  return `lora_${short}`
}

export function configNameForModel(taskName: string): string {
  const base = taskName.trim() || 'adapter'
  return `${base.slice(0, 50)}-adapter`
}
