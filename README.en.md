# CardLab

[中文](README.md) | English

Local AI card-game research tool: form hypotheses, inspect decisions, compare game results and record conclusions. LoRA fine-tuning is an optional improvement path.

After saving a comparison, cite individual decisions and append conclusion revisions with observations, interpretation and limitations. Export a research report containing the snapshot and selected evidence. Source changes or deletion do not rewrite saved evidence.

> **About models**: This project **calls** third-party LLM APIs (or local Ollama) for card-playing decisions—it does **not** distill or replicate any large model. LoRA fine-tuning uses game-play trajectory data (the user's own recorded games), not third-party API outputs for training competing models. All API calls comply with each provider's terms of service. The project itself **does not bundle any model weights**; users configure their own API keys or local models.

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Vue 3 · TypeScript · Vite · Tailwind v4 · Reka UI |
| Backend | Python 3.11+ · FastAPI · WebSocket |
| LLM | OpenAI · Ollama · DashScope · DeepSeek · Kimi · Zhipu · Yi · Baichuan · MiniMax |
| Storage | SQLite index + JSONL archive |
| Training | PEFT LoRA (`poetry install --with training`; CPU quick check without GPU; optional 4-bit QLoRA needs bitsandbytes) |

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

Open http://localhost:5173 . Home walks you through provider → players → experiment. Create **Player configs** first (Dou Dizhu needs 3). Set at least one API key or local Ollama in `.env`. No key? Use **Load demo experiment** on the home page — it seeds a main + control pair and opens the **verdict** stage. Importable packs live in [`examples/`](examples/) (baseline vs LLM, prompt A/B skeleton, pre-finetune baseline).

## Main loop

1. **Configure players** — choose models, policies and sampling parameters.
2. **Define an experiment** — select players and record a hypothesis with evaluation criteria. Creating it does not start games.
3. **Run and review** — watch or replay games, then review all decisions, including failures and records excluded from training. Trainable means structurally valid; it does not measure decision quality.
4. **Compare** — compare existing experiments or create a control using registered players and source deal seeds. Check protocol differences and effective sample sizes before interpreting results.
5. **Record conclusions** — keep working notes on experiment detail; save a comparison snapshot, then cite decisions and append conclusion revisions under Conclusions and evidence.

**Optional training:** use Analyze → Training to export/register decision datasets, fine-tune and register a player. Training is not a prerequisite for review, comparison or control creation. Opening a control with `?collect=1` only opens start confirmation; games require an explicit submission.

Comparison now shows frozen protocol differences and effective shared seeds, excluding ambiguous duplicate runs. Declare allowed Solver changes and compare again. Save a named snapshot to reopen or export its frozen results later. Declarations are retrospective; research reports include selected evidence, while full runnable reproduction packages remain planned.

Benchmark mode uses fixed deal seeds (up to 50 games); the detail page shows **this run’s** metrics under the current phase (landlord WR, parse, trainable, latency, tokens/game). Trial games live at `/game` (not tied to experiments). Decisions, traces, data, and training are under **Analyze** (`/pipeline/…`, `?experiment_id=`). Export an experiment pack from detail (no API keys) and import it on the home page to reproduce on another machine. Usage guide: header book icon → `/guide`.

Script loop: `.\scripts\e2e_pipeline.ps1 all -Count 1` — see [E2E guide](docs/E2E_PIPELINE.md).

## Screenshots

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="screenshots/en/experiment-configs.png" alt="Player configs: model, sampling, win rate">
      <p><strong>Player configs</strong> — model and sampling per seat; import / export packs. Packs do not include API keys.</p>
    </td>
    <td width="50%" valign="top">
      <img src="screenshots/en/games.png" alt="Trial games list">
      <p><strong>Trial games</strong> — one-off matches outside experiments; or load a demo and watch.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="screenshots/en/data.png" alt="Analyze · data overview: games, rounds, tokens, role wins">
      <p><strong>Analyze · Data</strong> — corpus size, completion, landlord / peasant win split.</p>
    </td>
    <td width="50%" valign="top">
      <img src="screenshots/en/decisions.png" alt="Analyze · decision points: hand, legal moves, thinking">
      <p><strong>Analyze · Decisions</strong> — state, legal moves, thinking, train-usable; export ChatML.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="screenshots/en/training.png" alt="Analyze · training tasks">
      <p><strong>Analyze · Training</strong> — PEFT LoRA tasks and the model repo; register a finished tag as a player.</p>
    </td>
    <td width="50%" valign="top">
      <img src="screenshots/en/traces.png" alt="Analyze · traces: parse rate and model thinking">
      <p><strong>Analyze · Traces</strong> — latency, parse rate, tool calls, raw JSON.</p>
    </td>
  </tr>
</table>

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
| https://blueWhalei.github.io/ai-card-game-lab/en/ | Project page |
| http://localhost:5173 | UI |
| http://localhost:8000/docs | API docs |
| http://localhost:8000/api/v1/system/preflight | Preflight (run-ready) |

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
