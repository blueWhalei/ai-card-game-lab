# Config directory

- `experiment_configs.yaml` — **seed / backup only**. Runtime experiment configs live in
  SQLite (`experiment_configs` table). On first boot with an empty table, configs are
  imported from this file. Edit them in the Experiment Configs UI afterwards.
- Application settings come from environment variables / `.env` via
  `server/app/config.py` (not from a YAML settings file).
