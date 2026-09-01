<p align="center">
  <img src="web/public/logo.png" alt="CardLab" width="88">
</p>

# CardLab

[中文](README.md) | English

Local AI card-game research tool: experiments as the unit—watch decisions, collect games, LoRA fine-tune, and validate with controls.

Repo: [`ai-card-game-lab`](https://github.com/blueWhalei/ai-card-game-lab) (GitHub repository name unchanged).

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Vue 3 · TypeScript · Vite · Tailwind v4 · Reka UI |
| Backend | Python 3.11+ · FastAPI · WebSocket |
| LLM | OpenAI · Ollama · DashScope · DeepSeek · Kimi · Zhipu · Yi · Baichuan · MiniMax |
| Storage | SQLite index + JSONL archive |
| Training | PEFT LoRA (`poetry install --with training`; CPU smoke without GPU) |

## Quick start

**Requires**: Python 3.11+ · Node 20.19+ / 22.12+ · Poetry · (optional) Ollama

```bash
git clone https://github.com/blueWhalei/ai-card-game-lab.git
cd ai-card-game-lab
cp .env.example .env    # Windows: copy .env.example .env
```

Start in two terminals:

| Platform | Backend (:8000) | Frontend (:5173) |
|----------|-----------------|------------------|
| Windows | `scripts\start-backend.bat` | `scripts\start-frontend.bat` |
| macOS / Linux | `chmod +x scripts/*.sh` then `./scripts/start-backend.sh` | `./scripts/start-frontend.sh` |

Or manually: `cd server && poetry install && poetry run uvicorn ...` · `cd web && npm install && npm run dev`.

Open http://localhost:5173 . Create **Player configs** first (Dou Dizhu needs 3). Set at least one API key or local Ollama in `.env`. No key? Use **Load demo game** on the home page.

## Main loop

1. **Player configs** — model and sampling  
2. **New experiment** — pick players and target games (does not auto-start)  
3. **Start games** — collect from experiment detail; watch and replay  
4. **Register & train** — export ChatML when trainable decisions are ready  
5. **Model repo** — push to Ollama or register as player  
6. **Control / compare** — control run and compare win rates and latency  

Benchmark mode uses fixed deal seeds (up to 50 games). Trial games live at `/game` (not tied to experiments). Decisions, traces, data, and training are under **Data & training** (`?experiment_id=`). Usage guide: header book icon → `/guide`.

Script loop: `.\scripts\e2e_pipeline.ps1 all -Count 1` — see [E2E guide](docs/E2E_PIPELINE.md).

## Config

`.env` at repo root:

```bash
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
# or OPENAI_API_KEY / OLLAMA_BASE_URL=http://localhost:11434
```

| provider | example model |
|----------|----------------|
| `openai` | `gpt-4o-mini` |
| `deepseek` | `deepseek-v4-flash` |
| `ollama` | `qwen2.5:7b` |
| `dashscope` | `qwen-plus` |

## Links

| URL | |
|-----|---|
| http://localhost:5173 | UI |
| http://localhost:8000/docs | API docs |
| http://localhost:8000/api/v1/system/preflight | Preflight (run-ready) |
| http://localhost:8000/api/v1/system/startup-check | Startup check (compat) |

## Docs

| Doc | |
|-----|---|
| [E2E pipeline](docs/E2E_PIPELINE.md) | Collect → train → deploy |
| [Architecture](docs/ARCHITECTURE.md) | Layers and flows |
| [API design](docs/API_DESIGN.md) | REST + WebSocket |
| [Project structure](docs/PROJECT_STRUCTURE.md) | Directory map |
| [Coding standards](docs/CODING_STANDARDS.md) | Python / Vue / i18n |
| [Examples](docs/EXAMPLES.md) | New engine / provider |
| [CLAUDE.md](CLAUDE.md) | Agent entry |

## License

[MIT](LICENSE)
