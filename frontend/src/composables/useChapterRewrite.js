import { ref, toValue, onUnmounted } from 'vue'

export function useChapterRewrite(novelId, chapterNumber, content) {
  const showRewriteModal = ref(false)
  const rewriteInstruction = ref('')
  const rewriting = ref(false)
  const rewriteResult = ref(null)
  const rewriteError = ref('')
  const selectionText = ref('')
  const selectionStart = ref(0)
  const selectionEnd = ref(0)
  let controller = null

  onUnmounted(() => controller?.abort())

  function openRewriteModal() {
    rewriteInstruction.value = ''
    rewriteResult.value = null
    rewriteError.value = ''
    showRewriteModal.value = true
  }

  function closeRewriteModal() {
    showRewriteModal.value = false
    rewriteResult.value = null
    rewriteError.value = ''
  }

  async function doRewrite() {
    if (!rewriteInstruction.value.trim()) return
    controller?.abort()
    controller = new AbortController()
    rewriting.value = true
    rewriteError.value = ''
    try {
      const res = await fetch(`/api/v1/projects/${toValue(novelId)}/chapters/${toValue(chapterNumber)}/rewrite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          full_content: toValue(content),
          selected_text: selectionText.value,
          selection_start: selectionStart.value,
          selection_end: selectionEnd.value,
          instruction: rewriteInstruction.value,
        }),
      })
      if (res.status === 504) {
        rewriteError.value = 'AI 改写超时，请稍后重试'
      } else if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        rewriteError.value = data.detail || '改写失败，请重试'
      } else {
        const data = await res.json()
        rewriteResult.value = { original: data.original_text, rewritten: data.rewritten_text }
      }
    } catch (e) {
      if (e.name === 'AbortError') return
      rewriteError.value = '网络错误，请重试'
    } finally {
      rewriting.value = false
    }
  }

  async function acceptRewrite(loadVersionsFn) {
    if (!rewriteResult.value) return
    const currentContent = toValue(content)
    const newContent = currentContent.slice(0, selectionStart.value) + rewriteResult.value.rewritten + currentContent.slice(selectionEnd.value)
    if (typeof content === 'object') {
      content.value = newContent
    }
    showRewriteModal.value = false
    selectionText.value = ''

    try {
      await fetch(`/api/v1/projects/${toValue(novelId)}/chapters/${toValue(chapterNumber)}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: newContent,
          source: 'ai_rewrite',
          rewrite_instruction: rewriteInstruction.value,
        }),
      })
      if (loadVersionsFn) await loadVersionsFn()
    } catch (e) {
      if (e.name === 'AbortError') return
    }
  }

  return {
    showRewriteModal,
    rewriteInstruction,
    rewriting,
    rewriteResult,
    rewriteError,
    selectionText,
    selectionStart,
    selectionEnd,
    openRewriteModal,
    closeRewriteModal,
    doRewrite,
    acceptRewrite,
  }
}
