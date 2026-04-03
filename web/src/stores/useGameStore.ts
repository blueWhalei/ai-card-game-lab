import { ref } from 'vue'
import { defineStore } from 'pinia'
import { gameApi } from '@/api/gameApi'
import type { GameItem } from '@/api/gameApi'

export const useGameStore = defineStore('game', () => {
  const games = ref<GameItem[]>([])
  const currentGame = ref<GameItem | null>(null)
  const isLoading = ref(false)
  const total = ref(0)

  async function fetchGames(params?: Record<string, string | number>): Promise<void> {
    isLoading.value = true
    try {
      const res = await gameApi.list(params)
      games.value = res.data.items
      total.value = res.data.total
    } finally {
      isLoading.value = false
    }
  }

  return { games, currentGame, isLoading, total, fetchGames }
})
