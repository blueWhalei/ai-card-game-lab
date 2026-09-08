# Experiment packs

Importable `cardlab.experiment_pack` JSON for CardLab (home → Import, or API `POST /api/v1/experiments/import`).

| File | Intent |
|------|--------|
| `baseline-vs-llm.json` | 1× Ollama LLM + 2× heuristic; benchmark seeds |
| `prompt-ab.json` | Same-model seats for manual prompt A/B (import rebuilds protocol; clone + edit prompts) |
| `finetune-before-after.json` | Pre-finetune baseline; notes describe control with `lora_*` after train |

Packs never include API keys. Existing player ids are reused, not overwritten.
