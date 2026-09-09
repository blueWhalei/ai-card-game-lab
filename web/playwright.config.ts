import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const e2eDataDir = path.join(rootDir, 'data', 'e2e-playwright')
const isCi = !!process.env.CI

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: isCi,
  retries: isCi ? 1 : 0,
  workers: 1,
  reporter: isCi ? 'github' : 'list',
  timeout: 90_000,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: 'poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: path.join(rootDir, 'server'),
      url: 'http://127.0.0.1:8000/api/v1/system/health',
      reuseExistingServer: !isCi,
      timeout: 120_000,
      env: {
        ...process.env,
        // Isolate from the developer's main SQLite so first-run / demo UI is deterministic.
        SQLITE_PATH: path.join(e2eDataDir, 'app.db'),
        DATA_DIR: e2eDataDir,
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !isCi,
      timeout: 120_000,
    },
  ],
})
