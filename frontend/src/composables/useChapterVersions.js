import { ref } from 'vue'

export function useChapterVersions(novelId, chapterNumber) {
  const versions = ref([])
  const showVersionHistory = ref(false)
  const previewVersionData = ref(null)

  function _id() { return typeof novelId === 'object' ? novelId.value : novelId }
  function _num() { return typeof chapterNumber === 'object' ? chapterNumber.value : chapterNumber }

  async function loadVersions() {
    const res = await fetch(`/api/v1/projects/${_id()}/chapters/${_num()}/versions`)
    if (res.ok) {
      versions.value = await res.json()
    }
  }

  async function previewVersion(ver) {
    const res = await fetch(`/api/v1/projects/${_id()}/chapters/${_num()}/versions/${ver.version_number}`)
    if (res.ok) {
      previewVersionData.value = await res.json()
    }
  }

  async function doRollback(versionNumber, loadFn) {
    if (!confirm(`确定回滚到版本 v${versionNumber}？当前未保存的内容将丢失。`)) return
    const res = await fetch(`/api/v1/projects/${_id()}/chapters/${_num()}/versions/${versionNumber}/rollback`, {
      method: 'POST',
    })
    if (res.ok) {
      previewVersionData.value = null
      if (loadFn) await loadFn()
      await loadVersions()
    }
  }

  async function doActivate(versionNumber, loadFn) {
    const res = await fetch(`/api/v1/projects/${_id()}/chapters/${_num()}/versions/${versionNumber}/activate`, {
      method: 'POST',
    })
    if (res.ok) {
      previewVersionData.value = null
      if (loadFn) await loadFn()
      await loadVersions()
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
