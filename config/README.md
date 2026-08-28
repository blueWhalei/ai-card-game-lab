# Config directory

- `experiment_configs.yaml` — **seed / backup only**. Runtime experiment configs live in SQLite
  (`experiment_configs` table). On first boot with an empty table, configs are imported
  from this file. Prefer editing via the 实验配置 UI.
- Application settings come from environment variables / `.env` via
  `server/app/config.py` (not from a YAML settings file).
