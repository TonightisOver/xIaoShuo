import { ref } from 'vue'
import { useApi } from './useApi.js'

/**
 * useReview — 封装人工审核（HITL）相关 API 调用。
 *
 * 端点约定：
 *   GET  /api/v1/tasks/{taskId}/review        获取当前任务的审核数据
 *   POST /api/v1/tasks/{taskId}/review         提交审核决策
 *
 * 提交 payload 形如（与后端 ReviewRequest 契约对齐）：
 *   { approval_status: 'approved' | 'rejected' | 'revision', revision_instructions?: string }
 *
 * 注意：枚举值是 'revision'（不是 'revise'）；意见字段是 revision_instructions。
 */
export function useReview() {
  const { apiGet, apiPost } = useApi()

  const reviewData = ref(null)
  const loading = ref(false)
  const submitting = ref(false)
  const error = ref(null)

  /**
   * 拉取某任务的审核快照。
   * @param {string|number} taskId
   * @returns {Promise<object|null>}
   */
  async function fetchReview(taskId) {
    if (!taskId) return null
    loading.value = true
    error.value = null
    try {
      const data = await apiGet(`/api/v1/tasks/${taskId}/review`)
      reviewData.value = data
      return data
    } catch (e) {
      error.value = e
      reviewData.value = null
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * 提交审核决策。
   * @param {string|number} taskId
   * @param {object} payload  { status, instructions }
   *   - status: 'approved' | 'rejected' | 'revision'（注意是 revision 不是 revise）
   *   - instructions: 可选，驳回/修改时的人工意见
   * @returns {Promise<object>}
   */
  async function submitReview(taskId, payload) {
    if (!taskId) throw new Error('taskId is required')
    const body = {
      approval_status: payload?.status,
      revision_instructions: payload?.instructions ?? '',
    }
    submitting.value = true
    error.value = null
    try {
      const res = await apiPost(`/api/v1/tasks/${taskId}/review`, body)
      return res
    } catch (e) {
      error.value = e
      throw e
    } finally {
      submitting.value = false
    }
  }

  function reset() {
    reviewData.value = null
    error.value = null
    loading.value = false
    submitting.value = false
  }

  return {
    reviewData,
    loading,
    submitting,
    error,
    fetchReview,
    submitReview,
    reset,
  }
}
