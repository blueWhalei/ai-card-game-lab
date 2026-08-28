# Config directory

- `ai_players.yaml` — **seed / backup only**. Runtime AI players live in SQLite
  (`ai_players` table). On first boot with an empty table, players are imported
  from this file. Prefer editing via the AI 角色 UI.
- Application settings come from environment variables / `.env` via
  `server/app/config.py` (not from a YAML settings file).
