import { ref, toValue, onUnmounted } from 'vue'

export function useChapterVersions(novelId, chapterNumber) {
  const versions = ref([])
  const showVersionHistory = ref(false)
  const previewVersionData = ref(null)
  let controller = null

  onUnmounted(() => controller?.abort())

  async function loadVersions() {
    controller?.abort()
    controller = new AbortController()
    try {
      const res = await fetch(`/api/v1/projects/${toValue(novelId)}/chapters/${toValue(chapterNumber)}/versions`, { signal: controller.signal })
      if (res.ok) {
        versions.value = await res.json()
      }
    } catch (e) {
      if (e.name === 'AbortError') return
    }
  }

  async function previewVersion(ver) {
    try {
      const res = await fetch(`/api/v1/projects/${toValue(novelId)}/chapters/${toValue(chapterNumber)}/versions/${ver.version_number}`, { signal: controller?.signal })
      if (res.ok) {
        previewVersionData.value = await res.json()
      }
    } catch (e) {
      if (e.name === 'AbortError') return
    }
  }

  async function doRollback(versionNumber, loadFn) {
    if (!confirm(`确定回滚到版本 v${versionNumber}？当前未保存的内容将丢失。`)) return
    try {
      const res = await fetch(`/api/v1/projects/${toValue(novelId)}/chapters/${toValue(chapterNumber)}/versions/${versionNumber}/rollback`, {
        method: 'POST',
      })
      if (res.ok) {
        previewVersionData.value = null
        if (loadFn) await loadFn()
        await loadVersions()
      }
    } catch (e) {
      if (e.name === 'AbortError') return
    }
  }

  async function doActivate(versionNumber, loadFn) {
    try {
      const res = await fetch(`/api/v1/projects/${toValue(novelId)}/chapters/${toValue(chapterNumber)}/versions/${versionNumber}/activate`, {
        method: 'POST',
      })
      if (res.ok) {
        previewVersionData.value = null
        if (loadFn) await loadFn()
        await loadVersions()
      }
    } catch (e) {
      if (e.name === 'AbortError') return
    }
  }

  return {
    versions,
    showVersionHistory,
    previewVersionData,
    loadVersions,
    previewVersion,
    doRollback,
    doActivate,
  }
}
