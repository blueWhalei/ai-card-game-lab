# AI Card Game Lab

[中文](README.md) | English

A local lab for AI-vs-AI card games: watch model decisions, collect play data, and distill a smaller specialist model.

## What it does

- **Experiment workbench**: an experiment is first-class — player count comes from the engine min/max. Collect, watch, register training, start a control run, and compare experiments from the detail page.
- **Shared game engine**: common card-game pieces so new titles plug in quickly (first game: Dou Dizhu).
- **Live chain-of-thought**: WebSocket streams AI reasoning, including streamed tokens and usage.
- **Collect loop**: full JSONL archive plus SQLite indexes; decision points export to ChatML, filterable by experiment.
- **Data dashboard**: tokens, game quality, AI performance, latency, and more.
- **Distillation**: PEFT LoRA (CPU smoke when there is no GPU). A finished model can be registered as an Ollama player and used in a control experiment.

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Vue 3 + TypeScript + Vite + Tailwind CSS v4 + Reka UI (Ink Lab dual shell) |
| Backend | Python 3.11+ / FastAPI + WebSocket |
| LLM | OpenAI / Ollama / DashScope / DeepSeek / Kimi / ZhipuAI / Yi / Baichuan / MiniMax |
| Metadata | SQLite (index / query / stats) |
| Archive | Local JSONL files |
| Training | `poetry install --with training` enables PEFT LoRA (Transformers); CPU smoke without a GPU |

## Quick start

### Requirements

- Python 3.11+
- Node.js 20.19+ or 22.12+
- Poetry
- Optional: Ollama (local models, no cloud key)

### Install and run

```bash
# 1. Clone
git clone https://github.com/blueWhalei/ai-card-game-lab.git
cd ai-card-game-lab

# 2. Copy env
cp .env.example .env          # macOS / Linux
# copy .env.example .env      # Windows cmd
# Edit .env: add at least one cloud API key, or use local Ollama
# Create player configs in the Experiment Configs UI; there is no YAML seed

# 3. Python deps
cd server
poetry install

# 4. Backend
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Frontend (new terminal)
cd ../web
npm install
npm run dev
```

### First-run checklist

1. `.env` is copied, and you have either a cloud API key or local Ollama.
2. Open **Experiment Configs** and create as many players as the engine needs (Dou Dizhu needs 3). The list starts empty — use the empty-state button.
3. After the backend starts, see http://localhost:8000/api/v1/system/startup-check for warnings.
4. Collecting games checks the selected config’s API key; a missing key is rejected up front, not after kickoff.
5. Training needs `cd server && poetry install --with training`. Missing deps block task creation; no GPU uses CPU smoke.
6. With no key, use **Load demo game** on the home page to try watch and replay (demo games are not tied to an experiment).

### Researcher path (recommended)

Open http://localhost:5173 — the home page is the **experiment list**.

1. **Create player configs** on Experiment Configs (model / temperature / …) for each engine slot
2. **Create an experiment**: pick configs + target game count → open detail (**does not** start games, so you do not burn a key by accident)
3. **Collect / start n more**: batch-start from the detail page; watch live games, replay finished ones
4. **Register and train**: when trainable decisions > 0, register ChatML and create a training task (register-only if training deps are missing)
5. **Training · model repo**: export a deploy bundle → (local GGUF + `ollama create`) → **Register as player**
6. **Control experiment**: pick the new player plus the same number of baselines as engine slots → collect again; **Compare experiments** for win-rate CI / latency / tokens

The Games sidebar still creates scatter games. Experiment detail tabs cover **games / players / decisions / traces / training** (`?tab=decisions`, etc.). Sidebar Decision / Trace / Data / Training pages also accept `?experiment_id=` and show a context bar back to the experiment.

You can also run the script loop (not via an experiment object):

```powershell
.\scripts\e2e_pipeline.ps1 guide
.\scripts\e2e_pipeline.ps1 check
.\scripts\e2e_pipeline.ps1 all -Count 1   # collect → export → real train (needs training extras)
```

Full notes: [end-to-end pipeline](docs/E2E_PIPELINE.md).

### URLs

- UI: http://localhost:5173 (dev)
  - **Ink Lab dual shell**: experiment list by default; `/experiments/:id` is the workbench; `/game/:id` is fullscreen watch (`GenericBoard`)
- API docs: http://localhost:8000/docs (Swagger)
- Alternate docs: http://localhost:8000/redoc (ReDoc)

### Player configs

Configs live only in **SQLite** and are created or edited on the Experiment Configs page. There is no YAML seed: the table is empty on first boot. Create enough configs for the engine slots before you create an experiment.

### API keys

Edit `.env` at the repo root:

```bash
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# or OpenAI / local Ollama
OPENAI_API_KEY=sk-your-openai-key
OLLAMA_BASE_URL=http://localhost:11434
```

### Scatter games (optional)

The Games page can still create 1–50 games that are not tied to an experiment. They still feed decisions and the dashboard. Prefer experiment-detail collect when you want filtering and controls.

### Watching

- **Live**: WebSocket pushes decisions and reasoning
- **Table**: `GenericBoard` list view; step replay after the game ends

### Provider field examples

Fill these on the Experiment Configs page:

| provider | example model_name |
|----------|--------------------|
| `openai` | `gpt-4o-mini` |
| `deepseek` | `deepseek-v4-flash` |
| `ollama` | `qwen2.5:7b` |
| `dashscope` | `qwen-plus` |

Sampling uses `temperature`, `top_p`, and `max_tokens`. Put intent in `notes` (e.g. high-temperature control).

## Docs

| Doc | Role |
|-----|------|
| [CLAUDE.md](CLAUDE.md) | Agent / developer entry (English, kept with the code) |
| [End-to-end pipeline](docs/E2E_PIPELINE.md) | ~1 hour collect → train → deploy + scripts |
| [Architecture](docs/ARCHITECTURE.md) | Layers and core flows |
| [Project structure](docs/PROJECT_STRUCTURE.md) | Directory map |
| [Coding standards](docs/CODING_STANDARDS.md) | Python / TypeScript / Vue |
| [API design](docs/API_DESIGN.md) | REST + WebSocket |
| [Examples](docs/EXAMPLES.md) | New engine / provider / event handler |

## Roadmap

### Phase 1 — core loop
- [x] FastAPI + Vue 3 skeleton
- [x] Dou Dizhu engine
- [x] Unified LLM client (OpenAI + Ollama + 8 domestic providers)
- [x] Collector (JSONL + SQLite)
- [x] Observer (WebSocket + replay)

### Phase 2 — data and training
- [x] Stats dashboard
- [x] Dataset filter / export
- [x] Decision `train_usable` filter + ChatML export (thinking off by default)
- [x] Training task UI (PEFT LoRA / CPU smoke)
- [x] Model repo
- [x] Real SFT (`training` extra: Transformers + PEFT)
- [x] Deploy bundle (merge + Modelfile + llama.cpp GGUF scripts) + Ollama verify / smoke game
- [x] One-shot scripts (`scripts/e2e_pipeline.*`)

### Phase 3 — experiments
- [x] List / detail workbench (collect, summary, in-detail decisions/traces, deep links + context bar)
- [x] Per-experiment decision export + register-and-train
- [x] Register a trained model as an Ollama player + control experiment
- [x] Workbench density (KPI strip, compact lists, compare matrix) + prompts / scatter games / configs aligned

> **Note**: `quality_score` on a decision is an **outcome** score (win 0.8 / loss 0.3 / draw 0.5), not a move-quality score. SFT filtering uses `train_usable`. Register-and-train lives on the experiment detail page (and on Decisions). Export defaults to `include_thinking=false`.
>
> **Real training**: `cd server && poetry install --with training`. Output is `models/<task_id>/adapter/` LoRA weights. No GPU clamps steps and samples (CPU smoke).
>
> **Local deploy**:
> 1. Export deploy bundle from the training page → `models/<id>/deploy/`
> 2. Set `LLAMA_CPP_DIR` and run the convert script for `model.gguf`
> 3. `ollama create <tag> -f Modelfile` (tag matches “register as player”, e.g. `acgl-…`)
> 4. Register as player → control experiment on the detail page
>
> **Script loop**: [docs/E2E_PIPELINE.md](docs/E2E_PIPELINE.md)

### Phase 4 — more (ongoing)
- [x] Compare experiments (`/experiments/compare` + `GET /api/v1/experiments/compare`)
- [x] One-click merge → GGUF → `ollama create` (needs `LLAMA_CPP_DIR`)
- [ ] More engines (e.g. Sanguosha)
- [ ] Stronger training (e.g. PPO)

## License

[MIT](LICENSE)
