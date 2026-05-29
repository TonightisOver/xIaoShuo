import { computed, ref, unref } from 'vue'

export function useReadingProgress(novelId) {
  const progress = ref(null)
  let throttleTimer = null
  let pendingProgress = null

  function getStorageKey() {
    const id = unref(novelId)
    return id ? `reading_progress_${id}` : null
  }

  function loadProgress() {
    const key = getStorageKey()
    if (!key) {
      progress.value = null
      return null
    }

    try {
      const saved = localStorage.getItem(key)
      progress.value = saved ? JSON.parse(saved) : null
    } catch {
      progress.value = null
    }

    return progress.value
  }

  function saveProgress(chapterNumber, scrollPercent) {
    const key = getStorageKey()
    if (!key) return

    const value = {
      chapter: Number(chapterNumber),
      scrollPercent: Number(scrollPercent),
      timestamp: new Date().toISOString(),
    }

    progress.value = value
    pendingProgress = value

    if (throttleTimer) return

    throttleTimer = setTimeout(() => {
      const latestKey = getStorageKey()
      if (latestKey && pendingProgress) {
        localStorage.setItem(latestKey, JSON.stringify(pendingProgress))
      }
      pendingProgress = null
      throttleTimer = null
    }, 500)
  }

  function clearProgress() {
    const key = getStorageKey()
    if (key) localStorage.removeItem(key)

    progress.value = null
    pendingProgress = null

    if (throttleTimer) {
      clearTimeout(throttleTimer)
      throttleTimer = null
    }
  }

  loadProgress()

  const hasProgress = computed(() => progress.value !== null)

  return {
    saveProgress,
    loadProgress,
    clearProgress,
    hasProgress,
  }
}
