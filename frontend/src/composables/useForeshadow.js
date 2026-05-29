import { computed, ref, unref } from 'vue'

export function useForeshadow(novelId) {
  const foreshadowData = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function loadForeshadows() {
    const id = unref(novelId)
    if (!id) return

    loading.value = true
    error.value = null

    try {
      const response = await fetch(`/api/v1/novels/${encodeURIComponent(id)}/foreshadow-tracker`)
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to load foreshadow data')
      }
      foreshadowData.value = await response.json()
    } catch (err) {
      error.value = err.message || 'Failed to load foreshadow data'
    } finally {
      loading.value = false
    }
  }

  const resolutionPercent = computed(() => {
    const rate = foreshadowData.value?.resolution_rate || 0
    return Math.round(rate * 100)
  })

  const danglingCount = computed(() => (foreshadowData.value?.dangling || []).length)

  const totalCount = computed(() => {
    const dataTotal = foreshadowData.value?.total_foreshadows
    if (typeof dataTotal === 'number') return dataTotal

    return [
      ...(foreshadowData.value?.planted || []),
      ...(foreshadowData.value?.resolved || []),
      ...(foreshadowData.value?.dangling || []),
    ].length
  })

  return {
    foreshadowData,
    loading,
    error,
    loadForeshadows,
    resolutionPercent,
    danglingCount,
    totalCount,
  }
}
