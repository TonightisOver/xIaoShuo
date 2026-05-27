import { ref } from 'vue'
import { useRouter } from 'vue-router'

export function useChapterContent(novelId, chapterNumber) {
  const router = useRouter()
  const chapter = ref(null)
  const content = ref('')
  const saving = ref(false)
  const saved = ref(false)
  const regenerating = ref(false)

  function _id() { return typeof novelId === 'object' ? novelId.value : novelId }
  function _num() { return typeof chapterNumber === 'object' ? chapterNumber.value : chapterNumber }

  async function load() {
    const res = await fetch(`/api/v1/projects/${_id()}/chapters/${_num()}`)
    if (res.ok) {
      chapter.value = await res.json()
      content.value = chapter.value.content || ''
    } else {
      chapter.value = null
      content.value = ''
    }
  }

  async function save() {
    saving.value = true
    saved.value = false
    await fetch(`/api/v1/projects/${_id()}/chapters/${_num()}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: content.value, title: chapter.value.title }),
    })
    saving.value = false
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  }

  async function regenerate() {
    if (!confirm('重新生成将覆盖当前内容，确定吗？')) return
    regenerating.value = true
    try {
      const res = await fetch(`/api/v1/projects/${_id()}/generate-chapters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter_start: parseInt(_num()), chapter_end: parseInt(_num()) }),
      })
      if (res.ok) {
        const data = await res.json()
        router.push(`/task/${data.task_id}`)
      } else {
        const err = await res.json().catch(() => ({ detail: '请求失败' }))
        alert(`重新生成失败: ${err.detail || res.statusText}`)
      }
    } catch (e) {
      alert(`重新生成失败: 网络错误`)
    }
    regenerating.value = false
  }

  async function deleteChapter() {
    if (!confirm('确定删除本章？此操作不可恢复。')) return
    await fetch(`/api/v1/projects/${_id()}/chapters/${_num()}`, { method: 'DELETE' })
    router.push(`/novels/${_id()}`)
  }

  return {
    chapter,
    content,
    saving,
    saved,
    regenerating,
    load,
    save,
    regenerate,
    deleteChapter,
  }
}
