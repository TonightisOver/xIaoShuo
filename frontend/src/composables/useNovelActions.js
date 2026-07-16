import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setActiveTaskId } from '../utils/taskState.js'
import { authHeaders } from './useApi.js'

export function useNovelActions(novelId, chapters) {
  const router = useRouter()
  const generating = ref(false)
  const fullGenerating = ref(false)
  const deleteTargetUnassigned = ref(null)

  async function generate() {
    generating.value = true
    try {
      const id = typeof novelId === 'object' ? novelId.value : novelId
      const res = await fetch(`/api/v1/projects/${id}/generate`, {
        method: 'POST',
        headers: { ...authHeaders() },
      })
      if (res.ok) {
        const data = await res.json()
        setActiveTaskId(data.task_id)
        router.push(`/task/${data.task_id}`)
      } else {
        const err = await res.json().catch(() => ({}))
        alert(err.detail || `生成失败（HTTP ${res.status}）`)
      }
    } catch (e) {
      alert(e.message || '生成失败，请检查网络后重试。')
    } finally {
      generating.value = false
    }
  }

  async function fullGenerate() {
    fullGenerating.value = true
    try {
      const id = typeof novelId === 'object' ? novelId.value : novelId
      const res = await fetch(`/api/v1/projects/${id}/generate-full`, {
        method: 'POST',
        headers: { ...authHeaders() },
      })
      if (res.ok) {
        const data = await res.json()
        setActiveTaskId(data.task_id)
        router.push(`/task/${data.task_id}`)
      } else if (res.status === 409) {
        const err = await res.json()
        const msg = err.detail || '冲突'
        if (msg.includes('已有正在运行')) {
          alert(msg)
        } else if (msg.includes('已有') && msg.includes('有效章节')) {
          const confirmed = confirm(`${msg}\n\n确定要覆盖重新生成吗？此操作不可撤销！`)
          if (confirmed) {
            const forceRes = await fetch(`/api/v1/projects/${id}/generate-full?force=true`, {
              method: 'POST',
              headers: { ...authHeaders() },
            })
            if (forceRes.ok) {
              const data = await forceRes.json()
              setActiveTaskId(data.task_id)
              router.push(`/task/${data.task_id}`)
            } else {
              const forceErr = await forceRes.json()
              alert(forceErr.detail || '生成失败')
            }
          }
        } else {
          alert(msg)
        }
      } else {
        const err = await res.json().catch(() => ({}))
        alert(err.detail || `生成失败（HTTP ${res.status}）`)
      }
    } catch (e) {
      alert(e.message || '生成失败，请检查网络后重试。')
    } finally {
      fullGenerating.value = false
    }
  }

  async function startConversation() {
    const id = typeof novelId === 'object' ? novelId.value : novelId
    const topic = prompt('对话主题（如：讨论主角设定、情节走向）')
    if (!topic) return
    const res = await fetch(`/api/v1/projects/${id}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic }),
    })
    if (res.ok) {
      const data = await res.json()
      router.push(`/novels/${id}/conversations/${data.id}`)
    }
  }

  async function handleGenerateVolume(volumeNumber) {
    const id = typeof novelId === 'object' ? novelId.value : novelId
    const res = await fetch(`/api/v1/projects/${id}/generate-volume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ volume_number: volumeNumber }),
    })
    if (res.ok) {
      const data = await res.json()
      setActiveTaskId(data.task_id)
      router.push(`/task/${data.task_id}`)
    }
  }

  async function handleGenerateChapters({ chapter_start, chapter_end }) {
    const id = typeof novelId === 'object' ? novelId.value : novelId
    const res = await fetch(`/api/v1/projects/${id}/generate-chapters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chapter_start, chapter_end }),
    })
    if (res.ok) {
      const data = await res.json()
      setActiveTaskId(data.task_id)
      router.push(`/task/${data.task_id}`)
    }
  }

  function confirmDeleteUnassigned(ch) {
    deleteTargetUnassigned.value = ch
  }

  async function doDeleteUnassigned() {
    const ch = deleteTargetUnassigned.value
    if (!ch) return
    const id = typeof novelId === 'object' ? novelId.value : novelId
    try {
      const res = await fetch(`/api/v1/projects/${id}/chapters/${ch.chapter_number}`, { method: 'DELETE' })
      if (res.ok) {
        chapters.value = chapters.value.filter(c => c.chapter_number !== ch.chapter_number)
      }
    } finally {
      deleteTargetUnassigned.value = null
    }
  }

  async function cleanupFailedChapters() {
    if (!confirm('将删除所有字数少于100字的失败章节，确定继续？')) return
    const id = typeof novelId === 'object' ? novelId.value : novelId
    try {
      const res = await fetch(`/api/v1/projects/${id}/chapters/cleanup?min_words=100`, { method: 'DELETE' })
      if (res.ok) {
        const data = await res.json()
        if (data.deleted_count > 0) {
          chapters.value = chapters.value.filter(c => (c.word_count || 0) >= 100)
          alert(`已清理 ${data.deleted_count} 个失败章节`)
        } else {
          alert('没有需要清理的失败章节')
        }
      }
    } catch (e) {
      console.error('Cleanup failed', e)
    }
  }

  return {
    generating,
    fullGenerating,
    deleteTargetUnassigned,
    generate,
    fullGenerate,
    startConversation,
    handleGenerateVolume,
    handleGenerateChapters,
    confirmDeleteUnassigned,
    doDeleteUnassigned,
    cleanupFailedChapters,
  }
}
