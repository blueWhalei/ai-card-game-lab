/** Game type display name mapping */
export const GAME_TYPE_MAP: Record<string, string> = {
  doudizhu: '斗地主',
}

/** Game status → { label, type } mapping */
export const GAME_STATUS_MAP: Record<string, { label: string; type: string }> = {
  created: { label: '待启动', type: 'info' },
  running: { label: '进行中', type: 'success' },
  paused: { label: '已暂停', type: 'warning' },
  finished: { label: '已结束', type: 'danger' },
}

/** Training task status → { label, type } mapping */
export const TRAINING_STATUS_MAP: Record<string, { label: string; type: string }> = {
  pending: { label: '等待中', type: 'info' },
  exporting: { label: '导出数据', type: 'warning' },
  training: { label: '训练中', type: '' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
}

/** Prompt template key labels */
export const TEMPLATE_KEY_LABELS: Record<string, string> = {
  game_instruction: '游戏指令',
  player_prompt: '玩家提示',
  system_prompt: '系统提示',
  game_summary: '游戏总结',
}

/** Prompt template key options for select dropdowns */
export const TEMPLATE_KEY_OPTIONS = [
  { value: 'game_instruction', label: '游戏指令 (game_instruction)' },
  { value: 'player_prompt', label: '玩家提示 (player_prompt)' },
  { value: 'system_prompt', label: '系统提示 (system_prompt)' },
  { value: 'game_summary', label: '游戏总结 (game_summary)' },
] as const
